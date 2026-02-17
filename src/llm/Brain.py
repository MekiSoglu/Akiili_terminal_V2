"""
Brain - Akıllı Terminal Beyni.

Akış:
    1. Router: Kullanıcı isteğini modüle yönlendir
    2. Alt Router : Alt kategoriye yönlendir 3 katmanlı llm
    3. Planner: Seçilen araçlarla plan üret

Brain iş yapmaz, sadece düşünür ve plan üretir.
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
        Kullanıcı inputunu al, cevap döndür.
        """
        #  1: Hangi modül
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

        # 2: Alt kategori varsa seç 3 katmanlı llm
        category = None
        if module.has_subcategories:
            category = self._route_subcategory(user_input, module)
            if not category:
                return PlanResult(
                    success=False,
                    message="Alt kategori belirlenemedi.",
                )
            logger.info(f"Alt kategori: {category}")

        #  3: Plan üret
        plan = self._plan(user_input, module_name, category)

        if not plan:
            return PlanResult(
                success=False,
                message="İşlem planı oluşturulamadı.",
            )

        logger.info(f"Plan: {len(plan)} adım")

        # Aşama 4: Planı çalıştır
        result = self.executor.execute(plan, module)

        return result


    def _route(self, user_input: str) -> str | None:
        modules_summary = self.registry.list_modules()

        if not modules_summary:
            logger.error("Hiç modül yüklü değil.")
            return None

        if len(modules_summary) == 1:
            return modules_summary[0]["name"]

        # geçici çözüm
        NETWORK_OVERRIDES = ["hosts", "dns", "ping", "arp", "firewall", "vpn", "proxy", "traceroute"]

        user_lower = user_input.lower()
        for kw in NETWORK_OVERRIDES:
            if kw in user_lower and "network_operations" in self.registry.module_names:
                logger.info(f"Override routing: network_operations ({kw})")
                return "network_operations"

        # Eşleşme yoksa LLM'e sor
        prompt = self.prompts.get_router_prompt(modules_summary, user_input)
        response = self.llm.ask(prompt)

        if response and "module" in response:
            selected = response["module"]
            if selected in self.registry.module_names:
                return selected
            logger.warning(f"LLM var olmayan modül seçti: {selected}")

        return None

    def _route_subcategory(self, user_input: str, module) -> str | None:
        """Alt kategori seçimi. Modülün subcategories'ini kullanır."""
        subcategories = module.subcategories_summary()

        if not subcategories:
            return None

        # Tek kategori varsa direkt seç
        if len(subcategories) == 1:
            return subcategories[0]["name"]

        prompt = self.prompts.get_subcategory_prompt(subcategories, user_input)
        response = self.llm.ask(prompt)

        if response and "category" in response:
            selected = response["category"]
            valid_names = [sc["name"] for sc in subcategories]
            if selected in valid_names:
                return selected
            # Fuzzy eşleşme
            for name in valid_names:
                if selected in name or name in selected:
                    return name
            logger.warning(f"LLM var olmayan kategori seçti: {selected}")

        return None

    def _plan(self, user_input: str, module_name: str, category: str = None) -> list[dict] | None:
        # Önce keyword eşleşmesi dene
        module = self.registry.get(module_name)
        if hasattr(module, 'match_tool_by_keywords'):
            matched = module.match_tool_by_keywords(user_input)
            if matched:
                logger.info(f"Keyword eşleşmesi: {matched}")
                return [{"tool": matched, "params": {}}]

        # Eşleşme yoksa LLM'e sor
        tools_data = self.registry.get_module_prompt_data(module_name, category)

        if not tools_data:
            return None

        prompt_name = f"{module_name}_{category}" if category else module_name
        prompt = self.prompts.get_planner_prompt(prompt_name, tools_data, user_input)
        response = self.llm.ask(prompt)
        logger.info(f"Prompt adı: {prompt_name}")

        if not response:
            return None

        if isinstance(response, list):
            return response
        elif isinstance(response, dict) and "steps" in response:
            return response["steps"]

        logger.warning(f"Beklenmeyen plan formatı: {type(response)}")
        return None

    @staticmethod
    def _ask_user_confirmation(tool_name: str, params: dict) -> bool:
        """Tehlikeli işlemlerde kullanıcıya sor."""
        print(f"\n⚠️  Onay gerekli: {tool_name}")
        print(f"   Parametreler: {params}")
        answer = input("   Devam edilsin mi? (e/h): ").strip().lower()
        return answer in ("e", "evet", "y", "yes")