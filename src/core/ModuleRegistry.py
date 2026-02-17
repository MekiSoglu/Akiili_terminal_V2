"""
ModuleRegistry - Modül Yöneticisi.

modules/ klasörünü tarar, BaseModule'den türeyen sınıfları
otomatik bulur ve kaydeder.
"""
from __future__ import annotations
import os
import sys
import importlib
import importlib.util
import inspect
import logging
from pathlib import Path
from core.BaseModule import BaseModule

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """
    Modül kayıt ve yönetim merkezi.

    Kullanım:
        registry = ModuleRegistry()
        registry.discover()  # modules/ klasörünü tara
        module = registry.get("file_operations")
        result = module.execute("search_files", {"name": "config"})
    """

    def __init__(self, modules_dir: str = "modules"):
        self.modules_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent / modules_dir
        self._modules: dict[str, BaseModule] = {}

    def discover(self):
        if not self.modules_dir.exists():
            logger.warning(f"Modül dizini bulunamadı: {self.modules_dir}")
            return

        for file in self.modules_dir.rglob("*.py"):
            if file.name.startswith("_"):
                continue
            self._load_module_file(file)

        logger.info(f"{len(self._modules)} modül yüklendi: {list(self._modules.keys())}")

    def _load_module_file(self, file_path: Path):
        """Tek bir dosyadan modül yükle."""
        module_name = file_path.stem

        # Modül dosyasının parent dizinlerini path'e ekle
        project_root = str(file_path.parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        try:
            # dosyayı bul yükle çalıştır
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Dosyadaki tüm sınıfları tara
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseModule) and obj is not BaseModule:
                    instance = obj()
                    self._modules[instance.metadata.name] = instance
                    logger.info(f"Modül yüklendi: {instance.metadata.name}")
        except Exception as e:
            import traceback
            logger.error(f"Modül yükleme hatası ({file_path.name}): {e}")
            logger.error(traceback.format_exc())



    def get(self, module_name: str) -> BaseModule | None:
        """İsme göre modül getir."""
        return self._modules.get(module_name)

    def list_modules(self) -> list[dict]:
        """
        Tüm modüllerin özet bilgisi.
        Router prompt'u için kullanılır.
        """
        return [
            {"name": mod.metadata.name, "description": mod.metadata.description}
            for mod in self._modules.values()
        ]

    def get_module_prompt_data(self, module_name: str, category: str = None) -> dict | None:
        module = self.get(module_name)
        if module:
            return module.to_prompt_dict(category)
        return None

    @property
    def module_names(self) -> list[str]:
        """Kayıtlı modül isimleri."""
        return list(self._modules.keys())

    @property
    def count(self) -> int:
        return len(self._modules)