"""
DAGExecutor - DAG Yürütücü.

LLM'in ürettiği DAG JSON'ı adım adım çalıştırır.
PlanExecutor'ın yerini alır.

Destekler:
    - $tN.output referans çözümleme
    - foreach döngü
    - depends_on ile topolojik sıralama
    - Cross-module (dosya + ağ aynı DAG'da)
    - Tehlike seviyesi kontrolü
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
# Sonuç Veri Yapıları (PlanExecutor uyumlu)
# ══════════════════════════════════════════════════════


@dataclass
class StepResult:
    """Tek adımın sonucu."""

    step_number: int
    tool_name: str
    success: bool
    result: dict = field(default_factory=dict)
    error: str = ""
    is_foreach: bool = False


@dataclass
class DAGResult:
    """Tüm DAG'ın sonucu. OutputFormatter PlanResult bekliyor, aynı arayüz."""

    success: bool
    steps: list[StepResult] = field(default_factory=list)
    stopped_at: int = -1
    message: str = ""


class DAGExecutor:
    """
    DAG JSON'ı alır, topolojik sırayla çalıştırır.

    Kullanım:
        executor = DAGExecutor(registry, tool_registry_list, confirm_callback)
        result = executor.execute(dag_json)
    """

    def __init__(
        self,
        module_registry,
        tool_registry_list: list[dict],
        confirm_callback: Optional[Callable] = None,
    ):
        """
        Args:
            module_registry: ModuleRegistry instance — modülleri getirir
            tool_registry_list: TOOL_REGISTRY listesi — araç→modül eşlemesi
            confirm_callback: (tool_name, params) -> bool — tehlike onayı
        """
        self.registry = module_registry
        self.confirm_callback = confirm_callback

        # Araç ID → {module, name, params} hızlı eşleme tablosu
        self._tool_map = {}
        for tool in tool_registry_list:
            self._tool_map[tool["id"]] = {
                "module": tool["module"],
                "name": tool["name"],
            }

    # ══════════════════════════════════════════════════════
    # ANA ÇALIŞTIRMA
    # ══════════════════════════════════════════════════════

    def execute(self, dag: dict) -> DAGResult:
        """
        DAG'ı çalıştır.

        Args:
            dag: {"tasks": [
                {"id":"t1", "tool":"ping", "params":{...}, "depends_on":[], "desc":"..."},
                {"id":"t2", "type":"foreach", "items":"$t1.output", "tool":"dns_lookup", ...},
            ]}

        Returns:
            DAGResult — OutputFormatter ile uyumlu
        """
        tasks = dag.get("tasks", [])
        if not tasks:
            return DAGResult(success=False, message="DAG boş — görev yok.")

        # Her adımın çıktısını tutacak
        context = {}  # {"t1": <result_dict>, "t2": <result_dict>, ...}

        dag_result = DAGResult(success=True)
        sorted_tasks = self._topological_sort(tasks)

        for step_num, task in enumerate(sorted_tasks, 1):
            task_id = task.get("id", f"t{step_num}")
            tool_name = task.get("tool", "")
            params = task.get("params", {})
            depends_on = task.get("depends_on", [])
            task_type = task.get("type", "")
            desc = task.get("desc", tool_name)

            logger.info(
                f"Adım {step_num}/{len(sorted_tasks)}: {task_id} → {tool_name} ({desc})"
            )

            # ── Bağımlılık kontrolü ──
            for dep in depends_on:
                if dep not in context:
                    return self._fail(
                        dag_result,
                        step_num,
                        tool_name,
                        f"Bağımlılık tamamlanmadı: {dep}",
                    )

            # ── Parametrelerdeki referansları çöz ──
            resolved_params = self._resolve_params(params, context)

            # ── DEBUG: Çözümlenmiş parametreleri göster ──
            self._debug_params(task_id, tool_name, params, resolved_params)

            # ── Çalıştır (foreach veya tekil) ──
            if task_type == "foreach":
                step_result = self._run_foreach(
                    task, resolved_params, context, step_num
                )
            else:
                step_result = self._run_single(
                    task_id, tool_name, resolved_params, step_num
                )

            dag_result.steps.append(step_result)

            # ── DEBUG: Adım sonucunu göster ──
            self._debug_result(task_id, tool_name, step_result)

            # ── Sonucu context'e kaydet veya dur ──
            if step_result.success:
                context[task_id] = step_result.result
                logger.info(f"  ✅ {task_id} tamamlandı")
            else:
                dag_result.success = False
                dag_result.stopped_at = step_num
                dag_result.message = (
                    f"Adım {task_id} ({tool_name}): {step_result.error}"
                )
                return dag_result

        dag_result.message = f"Tüm {len(sorted_tasks)} adım başarıyla tamamlandı."
        return dag_result

    # ══════════════════════════════════════════════════════
    # TEKİL ADIM
    # ══════════════════════════════════════════════════════

    def _run_single(
        self, task_id: str, tool_name: str, params: dict, step_num: int
    ) -> StepResult:
        """Tek bir aracı çalıştır."""

        # Modülü bul
        module, err = self._get_module(tool_name)
        if err:
            return StepResult(
                step_number=step_num, tool_name=tool_name, success=False, error=err
            )

        # Tehlike kontrolü
        tool_def = module.get_tool(tool_name)
        if tool_def and not self._check_danger(tool_def, tool_name, params):
            return StepResult(
                step_number=step_num,
                tool_name=tool_name,
                success=False,
                error="Kullanıcı işlemi reddetti",
            )

        # ── Parametre tipi düzeltme ──
        # Tool tanımına göre string beklenen yere liste geldiyse akıllıca çevir
        if tool_def:
            params = self._coerce_param_types(params, tool_def)

        # Çalıştır
        try:
            result = module.execute(tool_name, params)
            success = (
                result.get("success", False)
                if isinstance(result, dict)
                else bool(result)
            )
            error = result.get("error", "") if isinstance(result, dict) else ""
            return StepResult(
                step_number=step_num,
                tool_name=tool_name,
                success=success,
                result=result,
                error=error,
            )
        except Exception as e:
            return StepResult(
                step_number=step_num,
                tool_name=tool_name,
                success=False,
                error=f"Çalışma hatası: {e}",
            )

    # ══════════════════════════════════════════════════════
    # FOREACH
    # ══════════════════════════════════════════════════════

    def _run_foreach(
        self, task: dict, resolved_params: dict, context: dict, step_num: int
    ) -> StepResult:
        """foreach tipindeki görevi çalıştır."""
        tool_name = task.get("tool", "")
        items_ref = task.get("items", "")

        # items referansını çöz
        items = self._resolve_value(items_ref, context)
        items = self._coerce_to_list(items)

        if items is None:
            return StepResult(
                step_number=step_num,
                tool_name=tool_name,
                success=False,
                error=f"foreach items çözümlenemedi: {items_ref}",
                is_foreach=True,
            )

        if not items:
            return StepResult(
                step_number=step_num,
                tool_name=tool_name,
                success=True,
                is_foreach=True,
                result={"success": True, "data": [], "message": "foreach: boş liste"},
            )

        logger.info(f" foreach: {len(items)} öğe × {tool_name}")

        # Modülü bul
        module, err = self._get_module(tool_name)
        if err:
            return StepResult(
                step_number=step_num,
                tool_name=tool_name,
                success=False,
                error=err,
                is_foreach=True,
            )

        # Her öğe için çalıştır
        all_results = []
        errors = []

        for i, item in enumerate(items):
            # $item → gerçek değer
            item_params = {}
            for k, v in resolved_params.items():
                if isinstance(v, str) and "$item" in v:
                    item_params[k] = v.replace("$item", str(item))
                else:
                    item_params[k] = v

            try:
                result = module.execute(tool_name, item_params)
                all_results.append(result)
                if not result.get("success", False):
                    errors.append(f"[{i + 1}] {result.get('error', '?')}")
            except Exception as e:
                errors.append(f"[{i + 1}] {e}")

        success = len(errors) == 0
        return StepResult(
            step_number=step_num,
            tool_name=tool_name,
            success=success,
            is_foreach=True,
            result={
                "success": success,
                "data": all_results,
                "message": f"foreach: {len(all_results) - len(errors)}/{len(items)} başarılı",
                "errors": errors or None,
            },
        )

    # ══════════════════════════════════════════════════════
    # REFERANS ÇÖZÜMLEME ($tN.output)
    # ══════════════════════════════════════════════════════

    # Path beklenen parametreler — bunlara content gelirse file_path çıkar
    _PATH_PARAMS = {
        "path",
        "file_path",
        "file_path_1",
        "file_path_2",
        "source",
        "destination",
        "dir_path",
    }

    def _resolve_params(self, params: dict, context: dict) -> dict:
        """Params dict'teki tüm $tN.output referanslarını çöz."""
        if not params:
            return {}
        resolved = {}
        for key, value in params.items():
            resolved_val = self._resolve_value(value, context)

            # Path parametresine dosya içeriği geldiyse → orijinal sonuçtan file_path çıkar
            if (
                key in self._PATH_PARAMS
                and isinstance(resolved_val, str)
                and isinstance(value, str)
                and "$t" in value
            ):
                # Çok satırlı veya çok uzun string → dosya yolu değil, içerik
                if "\n" in resolved_val or len(resolved_val) > 260:
                    # Orijinal context'ten file_path çıkarmayı dene
                    match = re.match(r"\$t(\d+)\.output", value.strip())
                    if match:
                        task_id = f"t{match.group(1)}"
                        if task_id in context:
                            raw = context[task_id]
                            if isinstance(raw, dict):
                                for fk in ("file_path", "full_path", "path"):
                                    if fk in raw:
                                        resolved_val = raw[fk]
                                        break

            resolved[key] = resolved_val
        return resolved

    def _resolve_value(self, value: Any, context: dict) -> Any:
        """Tek bir değerdeki $tN.output referanslarını çöz.

        Desteklenen formatlar:
            $t1.output          → adımın tüm çıktısı
            $t1.output.field    → çıktıdan belirli alan (dict ise)
            $item               → foreach içinde mevcut öğe
        """
        if not isinstance(value, str) or "$t" not in value:
            return value

        # Nested alan: $t1.output.directory, $t1.output.files
        nested_pattern = r"\$t(\d+)\.output\.(\w+)"
        nested_full = re.fullmatch(nested_pattern, value.strip())
        if nested_full:
            task_id = f"t{nested_full.group(1)}"
            field = nested_full.group(2)
            if task_id in context:
                data = self._extract_data(context[task_id])
                if isinstance(data, dict) and field in data:
                    return data[field]
                # Alan bulunamadı — tüm veriyi döndür
                return data
            return value

        # Tam eşleşme — $t1.output
        pattern = r"\$t(\d+)\.output"
        full = re.fullmatch(pattern, value.strip())
        if full:
            task_id = f"t{full.group(1)}"
            if task_id in context:
                return self._extract_data(context[task_id])
            return value

        # Kısmi eşleşme — string interpolation
        def replacer_nested(match):
            task_id = f"t{match.group(1)}"
            field = match.group(2)
            if task_id in context:
                data = self._extract_data(context[task_id])
                if isinstance(data, dict) and field in data:
                    return str(data[field])
                return str(data)
            return match.group(0)

        def replacer_simple(match):
            task_id = f"t{match.group(1)}"
            if task_id in context:
                data = self._extract_data(context[task_id])
                return str(data)
            return match.group(0)

        # Önce nested ($t1.output.field), sonra basit ($t1.output)
        result = re.sub(r"\$t(\d+)\.output\.(\w+)", replacer_nested, value)
        result = re.sub(r"\$t(\d+)\.output(?!\.)", replacer_simple, result)
        return result

    @staticmethod
    def _extract_data(result: Any) -> Any:
        """
        Bir adım sonucundan asıl veriyi çıkar.
        Modüller {"success": True, "data": ..., "content": ..., "message": ...} döner.

        Akıllı çözümleme:
            - {"data": ["tek_eleman"]} → "tek_eleman" (string olarak)
            - {"data": ["a", "b"]}     → ["a", "b"] (liste olarak)
            - {"content": "metin"}     → "metin"
        """
        if isinstance(result, dict):
            # Öncelik: data > content > message > tamamı
            if "data" in result:
                data = result["data"]
                # Tek elemanlı liste → doğrudan o elemanı döndür
                if isinstance(data, list) and len(data) == 1:
                    return data[0]
                return data
            if "content" in result:
                return result["content"]
            if "message" in result:
                return result["message"]
            return result
        return result

    # ══════════════════════════════════════════════════════
    # DEBUG YARDIMCILARI
    # ══════════════════════════════════════════════════════

    @staticmethod
    def _debug_params(
        task_id: str, tool_name: str, raw_params: dict, resolved_params: dict
    ):
        """Her adımın giriş parametrelerini ekrana yaz."""
        for key, value in resolved_params.items():
            raw_val = raw_params.get(key, "?")
            resolved_val = value

            raw_str = DAGExecutor._shorten(raw_val, 100)
            resolved_str = DAGExecutor._shorten(resolved_val, 100)

            if str(raw_val) != str(resolved_val):
                print(f" {task_id}.{key}: {raw_str} → {resolved_str}")
            else:
                print(f" {task_id}.{key}: {resolved_str}")

    @staticmethod
    def _debug_result(task_id: str, tool_name: str, step_result):
        """Her adımın çıktısını ekrana yaz."""
        if not step_result.success:
            print(f"  {task_id} HATA: {step_result.error}")
            return

        r = step_result.result
        if not isinstance(r, dict):
            print(f" {task_id} → {DAGExecutor._shorten(r, 150)}")
            return

        shown = False
        for key in ("data", "content", "message"):
            if key in r and r[key]:
                val = r[key]
                print(f" {task_id}.{key}: {DAGExecutor._shorten(val, 200)}")
                shown = True
        if not shown:
            print(f"  {task_id}: (sonuç boş)")

    @staticmethod
    def _shorten(value, max_len: int = 80) -> str:
        """Değeri okunabilir şekilde kısalt. (scipy _truncate çakışmasını önler)"""
        s = str(value)
        if len(s) > max_len:
            return s[:max_len] + "..."
        return s

    # ══════════════════════════════════════════════════════
    # YARDIMCI
    # ══════════════════════════════════════════════════════

    @staticmethod
    def _coerce_to_list(items: Any) -> Optional[list]:
        """Çeşitli tipleri listeye çevir."""
        if items is None:
            return None
        if isinstance(items, list):
            # List of dict ise → her dict'ten path/name çıkar
            if items and isinstance(items[0], dict):
                _KEYS = ("full_path", "path", "name", "ip", "domain", "host", "url")
                extracted = []
                for item in items:
                    for k in _KEYS:
                        if k in item:
                            extracted.append(item[k])
                            break
                    else:
                        extracted.append(str(item))
                return extracted
            return items
        if isinstance(items, str):
            lines = [l.strip() for l in items.split("\n") if l.strip()]
            return lines if lines else [items]
        if isinstance(items, dict):
            # Sırasıyla: data, files, items, results alanlarını dene
            for key in ("data", "files", "items", "results"):
                val = items.get(key)
                if isinstance(val, list):
                    return DAGExecutor._coerce_to_list(val)
            # Tek değer olarak dön
            return [str(items)]
        return [items]

    def _get_module(self, tool_name: str):
        """Araç adından modülü bul. (module_instance, error_str) döner."""
        tool_info = self._tool_map.get(tool_name)
        if not tool_info:
            return None, f"Araç registry'de yok: {tool_name}"

        module_name = tool_info["module"]
        # _internal modüller (foreach vs.) atlanır
        if module_name == "_internal":
            return None, f"Internal araç doğrudan çalıştırılamaz: {tool_name}"

        module = self.registry.get(module_name)
        if not module:
            return None, f"Modül bulunamadı: {module_name}"
        return module, ""

    # Parametre adı → dict'ten hangi alan çıkarılacak (öncelik sırasıyla)
    _PARAM_FIELD_MAP = {
        "path": ["full_path", "path", "directory", "name"],
        "dir_path": ["directory", "full_path", "path"],
        "directory": ["directory", "full_path", "path"],
        "source": ["full_path", "path", "source"],
        "destination": ["full_path", "path", "destination"],
        "file1": ["full_path", "path"],
        "file2": ["full_path", "path"],
        "file_path_1": ["full_path", "path", "name"],
        "file_path_2": ["full_path", "path", "name"],
        "host": ["ip", "host", "domain", "address"],
        "domain": ["domain", "host", "name"],
        "ip_address": ["ip", "ip_address", "host"],
        "target_ip": ["ip", "ip_address", "host"],
        "url": ["url", "full_path", "path"],
        "text": ["content", "text", "message", "data"],
        "content": ["content", "text", "message"],
        "query": ["content", "text", "query", "name"],
        "name": ["name", "title"],
        "new_name": ["name", "new_name"],
    }

    @staticmethod
    def _extract_field_from_dict(d: dict, field_priorities: list) -> str:
        """Dict'ten öncelik sırasına göre alan çıkar."""
        for field in field_priorities:
            if field in d:
                return str(d[field])
        # Hiçbiri yoksa ilk string değeri döndür
        for v in d.values():
            if isinstance(v, str):
                return v
        return str(d)

    @staticmethod
    def _coerce_param_types(params: dict, tool_def) -> dict:
        """
        Tool tanımına göre parametre tiplerini akıllıca düzelt.

        Dict veya list of dict geldiğinde parametre adına göre
        uygun alanı otomatik çıkarır.
        """
        if not tool_def or not tool_def.params:
            return params

        expected_types = {}
        for p in tool_def.params:
            expected_types[p.name] = p.param_type

        coerced = {}
        for key, value in params.items():
            expected = expected_types.get(key, None)

            if expected == "string" and isinstance(value, list):
                if len(value) == 0:
                    coerced[key] = ""
                elif len(value) == 1:
                    item = value[0]
                    if isinstance(item, dict):
                        fields = DAGExecutor._PARAM_FIELD_MAP.get(
                            key, ["name", "path", "value"]
                        )
                        coerced[key] = DAGExecutor._extract_field_from_dict(
                            item, fields
                        )
                    else:
                        coerced[key] = str(item)
                else:
                    if isinstance(value[0], dict):
                        fields = DAGExecutor._PARAM_FIELD_MAP.get(
                            key, ["name", "path", "value"]
                        )
                        extracted = [
                            DAGExecutor._extract_field_from_dict(item, fields)
                            for item in value
                        ]
                        coerced[key] = "\n".join(extracted)
                    else:
                        coerced[key] = "\n".join(str(v) for v in value)

            elif expected == "string" and isinstance(value, dict):
                fields = DAGExecutor._PARAM_FIELD_MAP.get(
                    key, ["message", "data", "content", "name"]
                )
                coerced[key] = DAGExecutor._extract_field_from_dict(value, fields)

            elif expected == "number" and isinstance(value, str):
                try:
                    coerced[key] = float(value) if "." in value else int(value)
                except (ValueError, TypeError):
                    coerced[key] = value
            else:
                coerced[key] = value

        return coerced

    def _check_danger(self, tool_def, tool_name: str, params: dict) -> bool:
        """Tehlike seviyesi kontrolü."""
        if tool_def.danger_level == "safe":
            return True
        if tool_def.danger_level in ("confirm", "dangerous"):
            if self.confirm_callback:
                return self.confirm_callback(tool_name, params)
            logger.warning(f"Tehlikeli işlem reddedildi (onay yok): {tool_name}")
            return False
        return True

    @staticmethod
    def _topological_sort(tasks: list[dict]) -> list[dict]:
        """Bağımlılıklara göre topolojik sıralama."""
        task_map = {t["id"]: t for t in tasks}
        visited = set()
        order = []

        def visit(tid):
            if tid in visited:
                return
            visited.add(tid)
            task = task_map.get(tid)
            if not task:
                return
            for dep in task.get("depends_on", []):
                visit(dep)
            order.append(task)

        for t in tasks:
            visit(t["id"])
        return order

    @staticmethod
    def _fail(
        dag_result: DAGResult, step_num: int, tool_name: str, error: str
    ) -> DAGResult:
        """Hata durumunda DAGResult'ı doldur ve döndür."""
        dag_result.steps.append(
            StepResult(
                step_number=step_num, tool_name=tool_name, success=False, error=error
            )
        )
        dag_result.success = False
        dag_result.stopped_at = step_num
        dag_result.message = error
        return dag_result
