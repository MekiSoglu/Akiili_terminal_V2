"""
BaseModule - Tüm modüllerin temel sınıfı.

Yeni modül eklemek için:
    1. modules/ klasöründe yeni dosya oluştur
    2. BaseModule'den türet
    3. metadata ve tools tanımla
    4. Otomatik olarak sisteme dahil olur
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolParam:
    """Bir aracın tek parametresi."""
    name: str
    description: str
    param_type: str  # "string", "number", "boolean"
    required: bool = True
    default: Any = None


@dataclass
class Tool:
    """Bir modülün sunduğu araç."""
    name: str
    description: str
    params: list[ToolParam] = field(default_factory=list)
    danger_level: str = "safe"  # "safe", "confirm", "dangerous"


@dataclass
class ModuleMetadata:
    """Modül kimlik kartı."""
    name: str
    description: str
    version: str = "1.0.0"


class BaseModule(ABC):
    """
    Tüm modüllerin extend edeceği temel sınıf.

    Her modül şunları tanımlamalı:
        - metadata: Modül adı ve açıklaması
        - tools: Sunduğu araçlar listesi
        - Her araç için aynı isimde bir metot
    """

    @property
    @abstractmethod
    def metadata(self) -> ModuleMetadata:
        """Modül kimlik bilgisi."""
        pass

    @property
    @abstractmethod
    def tools(self) -> list[Tool]:
        """Modülün sunduğu araçlar."""
        pass

    def execute(self, tool_name: str, params: dict) -> dict:
        tool = self.get_tool(tool_name)
        if tool:
            tool_name = tool.name  # Düzeltilmiş adı kullan

        method = getattr(self, tool_name, None)
        if method is None or not callable(method):
            return {"success": False, "error": f"Araç bulunamadı: {tool_name}"}
        try:
            result = method(**params)
            return result
        except TypeError as e:
            return {"success": False, "error": f"Parametre hatası: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Çalışma hatası: {str(e)}"}

    def get_tool(self, tool_name: str) -> Tool | None:
        # Önce tam eşleşme
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        # Bulamazsa benzer isim ara
        for tool in self.tools:
            if tool_name in tool.name or tool.name in tool_name:
                return tool
        return None

    def validate_params(self, tool_name: str, params: dict) -> dict:
        """
        Parametreleri çalıştırmadan önce doğrula.
        Eksik zorunlu parametre var mı? Tip doğru mu?
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return {"valid": False, "error": f"Araç bulunamadı: {tool_name}"}

        errors = []

        for param_def in tool.params:
            if param_def.required and param_def.name not in params:
                errors.append(f"Zorunlu parametre eksik: {param_def.name}")

        if errors:
            return {"valid": False, "errors": errors}

        return {"valid": True}

    def to_prompt_dict(self) -> dict:
        """
        LLM prompt'una gömülecek format.
        Modülün tüm araçlarını ve parametrelerini
        LLM'in anlayacağı formatta döner.
        """
        tools_list = []
        for tool in self.tools:
            tool_dict = {
                "name": tool.name,
                "description": tool.description,
                "parameters": [
                    {
                        "name": p.name,
                        "description": p.description,
                        "type": p.param_type,
                        "required": p.required,
                    }
                    for p in tool.params
                ],
            }
            tools_list.append(tool_dict)

        return {
            "module": self.metadata.name,
            "description": self.metadata.description,
            "tools": tools_list,
        }