"""
Brain - Akıllı Terminal Beyni.

İki aşamalı LLM çağrısı:
    1. Router: Kullanıcı isteğini doğru modüle yönlendir
    2. Planner: Seçilen modülün araçlarıyla plan üret

Brain iş yapmaz, sadece düşünür ve plan üretir.
Planın yürütülmesi PlanExecutor'ın işi.
"""

import logging
from core.ModuleRegistry import ModuleRegistry
from core.PlanExecutor import PlanExecutor
from llm.LLMClient import LLMClient
from llm.PromptManager import PromptManager

from src.core.PlanExecutor import PlanResult

logger = logging.getLogger(__name__)


class Brain:
    """
    Akıllı terminal beyni.

    Kullanım:
        brain = Brain(config_path)
        brain.initialize()
        result = brain.process("src klasöründeki .py dosyalarını bul")
    """

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.llm = LLMClient(config_path)
        self.registry = ModuleRegistry()
        self.prompts = PromptManager()
        self.executor = PlanExecutor(confirm_callback=self._ask_user_confirmation)

    def initialize(self):
        """Modülleri yükle. Uygulama başlangıcında bir kez çağrılır."""
        self.registry.discover()
        logger.info(f"Brain hazır. {self.registry.count} modül aktif.")

    def process(self, user_input: str) -> PlanResult:
        """
        Kullanıcı girdisini al, sonuç döndür.
        Tüm akış burada koordine edilir.
        """
        # Aşama 1: Hangi modül?
        module_name = self._route(user_input)

        if not module_name:
            return PlanResult(
                success=False,
                message="İsteğinizi anlayamadım. Lütfen daha açık ifade edin.",
            )

        module = self.registry.get(module_name)

        if not module:
            return PlanResult(
                success=False,
                message=f"'{module_name}' modülü bulunamadı.",
            )

        logger.info(f"Yönlendirme: {module_name}")

        # Aşama 2: Plan üret
        plan = self._plan(user_input, module_name)

        if not plan:
            return PlanResult(
                success=False,
                message="İşlem planı oluşturulamadı.",
            )

       # logger.info(f"Plan: {len(plan)} adım")

        # Aşama 3: Planı çalıştır
        result = self.executor.execute(plan, module)

        return result

    def _route(self, user_input: str) -> str | None:
        """
        Aşama 1: Kullanıcı isteğini doğru modüle yönlendir.
        Kısa prompt, kısa cevap.
        """
        modules_summary = self.registry.list_modules()

        if not modules_summary:
            logger.error("Hiç modül yüklü değil.")
            return None

        # Tek modül varsa direkt onu seç (LLM çağrısına gerek yok)
        if len(modules_summary) == 1:
            return modules_summary[0]["name"]

        prompt = self.prompts.get_router_prompt(modules_summary, user_input)
        response = self.llm.ask(prompt)
       # logger.info(f"LLM Plan: {response}")

        if response and "module" in response:
            selected = response["module"]
            # Modül gerçekten var mı kontrol et
            if selected in self.registry.module_names:
                return selected
            logger.warning(f"LLM var olmayan modül seçti: {selected}")

        return None

    def _plan(self, user_input: str, module_name: str) -> list[dict] | None:
        """
        Aşama 2: Seçilen modülün araçlarıyla plan üret.
        Detaylı prompt, JSON plan çıktısı.
        """
        tools_data = self.registry.get_module_prompt_data(module_name)

        if not tools_data:
            return None

        prompt = self.prompts.get_planner_prompt(module_name, tools_data, user_input)
        response = self.llm.ask(prompt)
       # logger.info(f"LLM Plan: {response}")

        if not response:
            return None

        # Plan formatı: {"steps": [...]} veya direkt [...]
        if isinstance(response, list):
            return response
        elif isinstance(response, dict) and "steps" in response:
            return response["steps"]

        logger.warning(f"Beklenmeyen plan formatı: {type(response)}")
       # logger.info(f"LLM Plan: {response}")

        return None

    @staticmethod
    def _ask_user_confirmation(tool_name: str, params: dict) -> bool:
        """Tehlikeli işlemlerde kullanıcıya sor."""
        print(f"\n⚠️  Onay gerekli: {tool_name}")
        print(f"   Parametreler: {params}")
        answer = input("   Devam edilsin mi? (e/h): ").strip().lower()
        return answer in ("e", "evet", "y", "yes")