"""
BaseModule - Tüm modüllerin temel sınıfı.

Yeni modül eklemek için:
    1. modules/ klasöründe yeni dosya oluştur
    2. BaseModule'den türet
    3. metadata ve tools tanımla
    4. Otomatik olarak sisteme dahil olur

Alt kategorili modüller için:
    - subcategories property'sini override et
    - get_tools_for_category ile kategori bazlı araç döndür
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import cast, Callable, Any


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
    category: str = ""


@dataclass
class Subcategory:
    """Alt kategori tanımı."""
    name: str
    description: str


@dataclass
class ModuleMetadata:
    """Modül kimlik kartı."""
    name: str
    description: str
    version: str = "1.0.0"


class BaseModule(ABC):
    """
    Tüm modüllerin extend edeceği temel sınıf.

    Basit modüller: tools property'si yeterli.
    Alt kategorili modüller: subcategories + get_tools_for_category override edilir.
    """

    @property
    @abstractmethod
    def metadata(self) -> ModuleMetadata:
        pass

    @property
    @abstractmethod
    def tools(self) -> list[Tool]:
        pass

    @property
    def subcategories(self) -> list[Subcategory]:
        """Alt kategoriler. Varsayılan: boş (alt kategori yok)."""
        return []

    @property
    def has_subcategories(self) -> bool:
        return len(self.subcategories) > 0

    def get_tools_for_category(self, category: str) -> list[Tool]:
        """Belirli bir kategorideki araçları döndür."""
        return [t for t in self.tools if t.category == category]

    def execute(self, tool_name: str, params: dict) -> dict:
        """Araç adına göre ilgili metodu çağırır."""
        tool = self.get_tool(tool_name)
        if tool:
            tool_name = tool.name

        method = cast(Callable[..., dict], getattr(self, tool_name, None))

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
     #llm halisülasyon görüp tool isimlerini değişitirise
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
        bir aracın çalışması için olmazsa olmaz (zorunlu)
         olan verilerin kullanıcı tarafından gönderilip gönderilmediği denetlenir
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

    def to_prompt_dict(self, category: str = None) -> dict:
        """
        LLM prompt'una gömülecek format.
        Modülün tüm araçlarını ve parametrelerini
        LLM'in anlayacağı formatta döner.
        category verilirse sadece o kategorinin araçlarını döner.
        """
        if category:
            # category verilirse sadece o kategorinin araçlarını döner. 3 katmanlı llm
            tools = self.get_tools_for_category(category)
        else:
            # alt kategori yoksa var olan tüm araçları dön . 2 katmanlı llm
            tools = self.tools

        tools_list = []
        for tool in tools:
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

    def subcategories_summary(self) -> list[dict]:
        """Alt kategori listesi (router prompt için)."""
        return [
            {"name": sc.name, "description": sc.description}
            for sc in self.subcategories
        ]