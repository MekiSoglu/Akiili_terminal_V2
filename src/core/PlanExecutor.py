"""
PlanExecutor - Plan Yürütücü.

LLM'in ürettiği planı adım adım çalıştırır.
Her adımda:
    1. Parametre doğrulama
    2. Tehlike seviyesi kontrolü
    3. Aracı çalıştır
    4. Sonucu doğrula
    5. Başarısızsa dur
"""

import logging
from dataclasses import dataclass, field

from src.core import BaseModule

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Tek adımın sonucu."""
    step_number: int
    tool_name: str
    success: bool
    result: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class PlanResult:
    """Tüm planın sonucu."""
    success: bool
    steps: list[StepResult] = field(default_factory=list)
    stopped_at: int = -1
    message: str = ""


class PlanExecutor:
    """
    Planı alır, adım adım yürütür.
    LLM çağırmaz — tamamen deterministik.
    """

    def __init__(self, confirm_callback=None):
        """
        Args:
            confirm_callback: Tehlikeli işlemlerde kullanıcıya soran fonksiyon.
                              Parametre: (tool_name, params) -> bool
                              None ise tehlikeli işlemler reddedilir.
        """
        self.confirm_callback = confirm_callback

    def execute(self, plan: list[dict], module: BaseModule) -> PlanResult:
        """
        Planı adım adım yürüt.

        Args:
            plan: [{"tool": "search_files", "params": {"name": "x"}}, ...]
            module: Araçları içeren modül

        Returns:
            PlanResult: Tüm adımların sonucu
        """
        plan_result = PlanResult(success=True)

        for i, step in enumerate(plan):
            step_num = i + 1
            tool_name = step.get("tool", "")
            params = step.get("params", {})

            logger.info(f"Adım {step_num}/{len(plan)}: {tool_name}")
            #logger.info(f"Aranan araç: '{tool_name}', Mevcut araçlar: {[t.name for t in module.tools]}")

            # 1. Araç var mı?
            tool_def = module.get_tool(tool_name)
            if not tool_def:
                step_result = StepResult(
                    step_number=step_num,
                    tool_name=tool_name,
                    success=False,
                    error=f"Araç bulunamadı: {tool_name}",
                )
                plan_result.steps.append(step_result)
                plan_result.success = False
                plan_result.stopped_at = step_num
                plan_result.message = f"Adım {step_num}'de bilinmeyen araç: {tool_name}"
                return plan_result

            # 2. Parametre doğrulama
            validation = module.validate_params(tool_name, params)
            if not validation["valid"]:
                step_result = StepResult(
                    step_number=step_num,
                    tool_name=tool_name,
                    success=False,
                    error=str(validation.get("errors", validation.get("error", ""))),
                )
                plan_result.steps.append(step_result)
                plan_result.success = False
                plan_result.stopped_at = step_num
                plan_result.message = f"Adım {step_num}'de parametre hatası"
                return plan_result

            # 3. Tehlike seviyesi kontrolü

            if not self._check_danger_level(tool_def, tool_name, params):
                step_result = StepResult(
                    step_number=step_num,
                    tool_name=tool_name,
                    success=False,
                    error="Kullanıcı işlemi reddetti",
                )
                plan_result.steps.append(step_result)
                plan_result.success = False
                plan_result.stopped_at = step_num
                plan_result.message = f"Adım {step_num} kullanıcı tarafından reddedildi"
                return plan_result

            # 4. Önceki adımın sonucunu parametre olarak aktar
            params = self._inject_previous_result(params, plan_result.steps)

            # 5. Çalıştır
            logger.info(f"Adım {step_num} params: {params}")

            result = module.execute(tool_name, params)
           # logger.info(f"Adım {step_num} sonuç: {result}")

            step_result = StepResult(
                step_number=step_num,
                tool_name=tool_name,
                success=result.get("success", False),
                result=result,
                error=result.get("error", ""),
            )
            plan_result.steps.append(step_result)

            # 6. Başarısızsa dur
            if not step_result.success:
                plan_result.success = False
                plan_result.stopped_at = step_num
                plan_result.message = f"Adım {step_num}'de hata: {step_result.error}"
                return plan_result

            logger.info(f"Adım {step_num} başarılı.")

        plan_result.message = f"Tüm {len(plan)} adım başarıyla tamamlandı."
        return plan_result

    def _check_danger_level(self, tool_def, tool_name: str, params: dict) -> bool:
        """Tehlikeli işlemlerde kullanıcı onayı al."""
        if tool_def.danger_level == "safe":
            return True

        if tool_def.danger_level in ("confirm", "dangerous"):
            if self.confirm_callback:
                return self.confirm_callback(tool_name, params)
            else:
                logger.warning(f"Tehlikeli işlem reddedildi (onay mekanizması yok): {tool_name}")
                return False

        return True

    @staticmethod
    def _inject_previous_result(params: dict, previous_steps: list) -> dict:
        if not previous_steps:
            return params

        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and "$step" in value:
                import re
                # $step2.data.0.full_path gibi referansları bul
                pattern = r'\$step(\d+)\.([a-zA-Z0-9_.]+)'

                def replacer(match):
                    step_idx = int(match.group(1)) - 1
                    field_path = match.group(2)
                    if 0 <= step_idx < len(previous_steps):
                        result = _resolve_nested(previous_steps[step_idx].result, field_path)
                        return str(result) if result is not None else match.group(0)
                    return match.group(0)

                resolved[key] = re.sub(pattern, replacer, value)
            elif isinstance(value, str) and "$prev." in value:
                field_name = value[6:]
                resolved[key] = _resolve_nested(previous_steps[-1].result, field_name)
            else:
                resolved[key] = value

        return resolved







def _resolve_nested(data: dict, path: str):
    """
    Nokta notasyonuyla nested değer çöz.
    "data.0.full_path" -> data["data"][0]["full_path"]
    """
    current = data

    for part in path.split("."):
        if current is None:
            return None

        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None

    return current