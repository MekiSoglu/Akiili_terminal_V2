"""
Brain - Akıllı Terminal Beyni v2 (DAG Tabanlı).

ESKİ AKIŞ (3 LLM çağrısı):
    1. Router LLM → hangi modül
    2. Subcategory LLM → hangi alt kategori
    3. Planner LLM → plan üret

YENİ AKIŞ (1 LLM çağrısı):
    1. estimate_complexity() → regex, 0ms
    2. ChromaDB araç ara → embedding, 30ms
    3. LLM DAG üret → 1 çağrı, model otomatik seçilir
    4. DAGExecutor çalıştır
"""

import logging

from src.core.Dagexecutor import DAGExecutor, DAGResult
from src.core.ModuleRegistry import ModuleRegistry
from src.llm.LLMClient import LLMClient
from src.llm.Prompts import build_dag_prompt
from src.tools.Tool_registry import TOOL_REGISTRY
from src.tools.tool_selector import get_tool_selector, estimate_complexity

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
# DAG Prompt Builder — prompts.py'den import
# ══════════════════════════════════════════════════════


def _validate_dag(dag: dict, tool_ids: set) -> dict:
    """DAG doğrulama."""
    issues = []
    warnings = []
    tasks = dag.get("tasks", [])

    if not tasks:
        return {"valid": False, "issues": ["Görev listesi boş"]}

    task_ids = set()
    for task in tasks:
        tid = task.get("id", "?")
        tool = task.get("tool", "")
        task_type = task.get("type", "")

        if tid in task_ids:
            issues.append(f"Tekrar eden ID: {tid}")
        task_ids.add(tid)

        # foreach kontrolü
        if task_type == "foreach":
            if tool and tool not in tool_ids:
                issues.append(f"{tid}: foreach içinde var olmayan araç '{tool}'")
            if not task.get("items"):
                issues.append(f"{tid}: foreach için 'items' eksik")
        elif tool == "foreach":
            warnings.append(f"{tid}: 'foreach' tool yerine type olmalı")
            # Otomatik düzelt
            task["type"] = "foreach"
            task["tool"] = task.get("params", {}).get("tool", "")
        elif tool and tool not in tool_ids:
            issues.append(f"{tid}: Var olmayan araç '{tool}'")

    # Bağımlılık kontrolü
    all_ids = {t.get("id") for t in tasks}
    for task in tasks:
        for dep in task.get("depends_on", []):
            if dep not in all_ids:
                issues.append(f"{task.get('id')}: Bağımlılık '{dep}' mevcut değil")

    return {"valid": len(issues) == 0, "issues": issues, "warnings": warnings}


# ══════════════════════════════════════════════════════
# Brain Sınıfı
# ══════════════════════════════════════════════════════


class Brain:
    """
    Akıllı terminal beyni v2.

    Kullanım:
        brain = Brain(config_path)
        brain.initialize()
        result = brain.process("config.txt oku URL bul ping at")
    """

    # Complexity → Text-Gen-WebUI model eşlemesi
    MODEL_MAP = {
        "7b": "qwen2.5-coder:7b",
        "8b": "deepseek-r1:8b",
        "12b": "gemma3:12b",
    }

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.llm = LLMClient(config_path)
        self.registry = ModuleRegistry()
        self.tool_selector = get_tool_selector()
        self.dag_executor = None

    def initialize(self):
        """Modülleri ve araç seçiciyi yükle. Başlangıçta bir kez çağrılır."""
        # 1. Modülleri yükle
        self.registry.discover()
        logger.info(f"Modüller hazır: {self.registry.count} modül")

        # 2. ChromaDB + embedding modelini yükle
        self.tool_selector.initialize()

        # 3. DAG executor oluştur
        self.dag_executor = DAGExecutor(
            module_registry=self.registry,
            tool_registry_list=TOOL_REGISTRY,
            confirm_callback=self._ask_user_confirmation,
        )

        logger.info("Brain v2 hazır (DAG tabanlı).")

    def process(self, user_input: str) -> DAGResult:
        """
        Kullanıcı inputunu al → DAG üret → çalıştır → sonuç döndür.
        """
        # ── 1. Karmaşıklık tahmin (0ms) ──
        complexity = estimate_complexity(user_input)
        level = complexity["level"]  # simple / medium / hard / complex
        model_key = complexity["model"]  # 1.5b / 4b / 8b / 12b
        model_name = self.MODEL_MAP.get(model_key, self.MODEL_MAP.get("8b", ""))

        d = complexity["details"]
        print(
            f"\n Karmaşıklık: {level} (W:{d['word_score']} S:{d['structural_score']} → {complexity['score']}) → {model_key}"
        )
        flags = []
        if d.get("cross_module"):
            flags.append("çapraz-modül")
        if d.get("dynamic_target"):
            flags.append("dinamik-hedef")
        if d.get("iteration"):
            flags.append("iterasyon")
        if d.get("has_output"):
            flags.append("çıktı-yazma")
        if d.get("has_filter"):
            flags.append("filtreleme")
        if flags:
            print(f" {', '.join(flags)}")

        # ── 2. ChromaDB ile araç bul (30ms) ──
        tools = self.tool_selector.search(user_input, top_k=10)

        if not tools:
            return DAGResult(
                success=False,
                message="Uygun araç bulunamadı. Lütfen daha açık ifade edin.",
            )

        tools_text = self.tool_selector.format_tools_for_llm(tools)
        logger.info(f"ChromaDB: {len(tools)} araç bulundu")

        # ── 3. DAG üret — TEK LLM çağrısı ──
        prompt = build_dag_prompt(user_input, tools_text, level)
        dag = self._generate_dag(prompt, model_name)

        # ── DAG DETAY LOG ──
        if dag:
            tasks = dag.get("tasks", [])
            print(f"\n{'─' * 60}")
            print(f" LLM DAG PLANI ({len(tasks)} adım)")
            print(f"{'─' * 60}")
            for t in tasks:
                tid = t.get("id", "?")
                tool = t.get("tool", "?")
                ttype = t.get("type", "")
                params = t.get("params", {})
                deps = t.get("depends_on", [])
                desc = t.get("desc", "")
                items = t.get("items", "")

                type_str = " [foreach]" if ttype == "foreach" else ""
                deps_str = f" ← {deps}" if deps else ""
                items_str = f" items={items}" if items else ""

                print(f"  {tid}: {tool}{type_str}{deps_str}")
                if params:
                    for k, v in params.items():
                        print(f"      {k}: {v}")
                if items_str:
                    print(f"      {items_str}")
                if desc:
                    print(f"      ({desc})")
            print(f"{'─' * 60}\n")

        if dag is None:
            return DAGResult(
                success=False,
                message="İşlem planı oluşturulamadı.",
            )

        # ── 4. Doğrula ──
        tool_ids = {t["id"] for t in TOOL_REGISTRY}
        validation = _validate_dag(dag, tool_ids)

        if not validation["valid"]:
            logger.warning(f"DAG doğrulama hatası: {validation['issues']}")
            # Retry — bir kez daha dene
            logger.info("Retry: DAG tekrar üretiliyor...")
            dag = self._generate_dag(prompt, model_name)
            if dag:
                validation = _validate_dag(dag, tool_ids)

            if not dag or not validation["valid"]:
                return DAGResult(
                    success=False,
                    message=f"Geçersiz plan: {'; '.join(validation.get('issues', ['?']))}",
                )

        if validation.get("warnings"):
            for w in validation["warnings"]:
                logger.warning(f"DAG uyarı: {w}")

        tasks = dag.get("tasks", [])
        task_tools = [t.get("tool", "?") for t in tasks]
        logger.info(f"DAG: {len(tasks)} adım → {task_tools}")

        # ── 5. DAG çalıştır ──
        result = self.dag_executor.execute(dag)
        return result

    # ══════════════════════════════════════════════════════
    # LLM DAG ÜRETİMİ
    # ══════════════════════════════════════════════════════

    def _generate_dag(self, prompt: str, model_name: str) -> dict | None:
        """LLM'den DAG JSON al."""
        response = self.llm.ask(prompt, model=model_name)

        if not response:
            return None

        # {"tasks": [...]} formatında mı?
        if isinstance(response, dict) and "tasks" in response:
            return response

        # {"steps": [...]} eski format desteği
        if isinstance(response, dict) and "steps" in response:
            return {"tasks": response["steps"]}

        # Liste geldiyse tasks olarak sar
        if isinstance(response, list):
            return {"tasks": response}

        logger.warning(f"Beklenmeyen DAG formatı: {type(response)}")
        return None

    # ══════════════════════════════════════════════════════
    # KULLANICI ONAY
    # ══════════════════════════════════════════════════════

    @staticmethod
    def _ask_user_confirmation(tool_name: str, params: dict) -> bool:
        """Tehlikeli işlemlerde kullanıcıya sor."""
        print(f"\n⚠️  Onay gerekli: {tool_name}")
        print(f"   Parametreler: {params}")
        answer = input("   Devam edilsin mi? (e/h): ").strip().lower()
        return answer in ("e", "evet", "y", "yes")
