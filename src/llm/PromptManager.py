"""
PromptManager - Prompt Şablon Yöneticisi.

Her modülün kendi prompt dosyası vardır (prompts/ klasöründe).
Router prompt'u ve modüle özel planlayıcı prompt'unu yükler.
"""

import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Prompt şablonlarını yönetir.

    prompts/
        router.txt           -> Yönlendirici prompt
        file_operations.txt  -> Dosya modülü prompt
        network.txt          -> Ağ modülü prompt (ileride)
    """

    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent / prompts_dir

    def get_router_prompt(self, modules_summary: list[dict], user_input: str) -> str:
        """
        Router prompt'unu oluşturur.
        Modül listesi + kullanıcı girdisi ile birleştirir.
        """
        template = self._load_template("router")

        modules_text = ""
        for mod in modules_summary:
            modules_text += f'- {mod["name"]}: {mod["description"]}\n'

        return template.format(
            modules=modules_text.strip(),
            user_input=user_input,
        )

    def get_subcategory_prompt(self, subcategories: list[dict], user_input: str) -> str:
        template = self._load_template("subcategory_router")

        categories_text = ""
        for sc in subcategories:
            categories_text += f'- {sc["name"]}: {sc["description"]}\n'

        return template.format(
            categories=categories_text.strip(),
            user_input=user_input,
        )

    def get_planner_prompt(self, prompt_name: str, tools_data: dict, user_input: str) -> str:
        """
        Modüle özel planlayıcı prompt'unu oluşturur.
        Modülün araçları + kullanıcı girdisi ile birleştirir.
        """
        template = self._load_template(prompt_name) # her modülün özel promtunu alır

        tools_text = json.dumps(tools_data["tools"], ensure_ascii=False, indent=2)

        return template.format(
            tools=tools_text,
            user_input=user_input,
        )

    def _load_template(self, name: str) -> str:
        """Prompt dosyasını oku."""
        file_path = self.prompts_dir / f"{name}.txt"

        if not file_path.exists():
            logger.warning(f"Prompt şablonu bulunamadı: {file_path}")
            return self._default_template(name)

        return file_path.read_text(encoding="utf-8")

    @staticmethod
    def _default_template(name: str) -> str:
        """Şablon dosyası yoksa varsayılan."""
        if name == "router":
            return (
                "Mevcut modüller:\n{modules}\n\n"
                "Kullanıcı isteği: {user_input}\n\n"
                'Sadece en uygun modül adını JSON olarak döndür: {{"module": "modül_adı"}}'
            )
        if name == "subcategory_router":
            return (
                "Mevcut kategoriler:\n{categories}\n\n"
                "Kullanıcı isteği: {user_input}\n\n"
                'Sadece en uygun kategori adını JSON olarak döndür: {{"category": "kategori_adı"}}'
            )
        return (
            "Mevcut araçlar:\n{tools}\n\n"
            "Kullanıcı isteği: {user_input}\n\n"
            "Adımları JSON listesi olarak döndür."
        )