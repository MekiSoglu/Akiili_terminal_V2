"""
Dosya İşlemleri Modülü — Dinamik & Esnek v2.

Tüm metotlar minimum veri ile çalışır:
  - Tam yol verilmezse dosya adından otomatik arama yapar
  - Parametre isimleri esnektir (path, file_path, name hepsi kabul edilir)
  - Dizin yolları da otomatik çözümlenir

Bu modül BaseModule'den türer ve otomatik olarak sisteme kaydolur.
"""

import os
import shutil
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Union

import sys

from core.BaseModule import BaseModule, ModuleMetadata, Tool, ToolParam
from indexing.FileQueryEngine import FileQueryEngine

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class FileOperationsModule(BaseModule):
    """Dosya sistemi işlemleri modülü — Dinamik parametre çözümleme destekli."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.query_engine = FileQueryEngine(config_path)

    # ================================================================
    # METADATA & TOOLS
    # ================================================================

    @property
    def metadata(self) -> ModuleMetadata:
        return ModuleMetadata(
            name="file_operations",
            description="Dosya arama, okuma, kopyalama, taşıma, silme, oluşturma ve dizin işlemleri",
            version="2.0.0",
        )

    @property
    def tools(self) -> list[Tool]:
        return [
            # --- ARAMA ---
            Tool(
                name="search_files",
                description="Dosya ara. İsim, uzantı, dizin, boyut filtrelerini destekler.",
                params=[
                    ToolParam(
                        "name", "Dosya adında aranacak metin", "string", required=False
                    ),
                    ToolParam(
                        "extension",
                        "Dosya uzantısı (.py, .txt vs.)",
                        "string",
                        required=False,
                    ),
                    ToolParam(
                        "directory",
                        "Aranacak dizin adı veya yolu",
                        "string",
                        required=False,
                    ),
                    ToolParam(
                        "min_size_mb", "Minimum boyut (MB)", "number", required=False
                    ),
                    ToolParam(
                        "max_size_mb", "Maximum boyut (MB)", "number", required=False
                    ),
                    ToolParam(
                        "limit",
                        "Maksimum sonuç sayısı",
                        "number",
                        required=False,
                        default=20,
                    ),
                ],
                danger_level="safe",
            ),
            Tool(
                name="search_directories",
                description="Dizin/klasör ara.",
                params=[
                    ToolParam(
                        "name", "Dizin adında aranacak metin", "string", required=False
                    ),
                    ToolParam(
                        "parent_path", "Üst dizin yolu", "string", required=False
                    ),
                    ToolParam(
                        "limit",
                        "Maksimum sonuç sayısı",
                        "number",
                        required=False,
                        default=20,
                    ),
                ],
                danger_level="safe",
            ),
            Tool(
                name="find_recently_modified",
                description="Son X gün içinde değiştirilen dosyaları bul.",
                params=[
                    ToolParam(
                        "days", "Kaç gün geriye bakılacak", "number", required=True
                    ),
                    ToolParam("extension", "Uzantı filtresi", "string", required=False),
                    ToolParam("directory", "Dizin filtresi", "string", required=False),
                ],
                danger_level="safe",
            ),
            Tool(
                name="list_directory_contents",
                description="Bir dizinin içeriğini listele (dosyalar ve alt dizinler).",
                params=[
                    ToolParam(
                        "path",
                        "Dizin yolu veya ismi (tam yol veya sadece isim)",
                        "string",
                        required=True,
                    ),
                ],
                danger_level="safe",
            ),
            # --- OKUMA ---
            Tool(
                name="read_file",
                description="Dosyanın içeriğini oku ve göster. Tam yol veya sadece dosya adı verilebilir.",
                params=[
                    ToolParam(
                        "path",
                        "Dosya yolu veya adı (ör: test.txt veya /home/user/test.txt)",
                        "string",
                        required=True,
                    ),
                    ToolParam(
                        "max_lines",
                        "Maksimum satır sayısı",
                        "number",
                        required=False,
                        default=50,
                    ),
                ],
                danger_level="safe",
            ),
            # --- YAZMA ---
            Tool(
                name="write_file",
                description="Dosyaya metin yaz. Dosya varsa üzerine yazar, yoksa oluşturur.",
                params=[
                    ToolParam("path", "Dosya yolu veya adı", "string", required=True),
                    ToolParam("content", "Yazılacak içerik", "string", required=True),
                ],
                danger_level="safe",
            ),
            # --- METİN ANALİZ ---
            Tool(
                name="find_in_text",
                description="Metin içinde URL, IP adresi, e-posta, domain veya özel kalıp arar. Pattern: url, ip, email, domain veya regex.",
                params=[
                    ToolParam(
                        "text",
                        "Aranacak metin (veya önceki adımın çıktısı)",
                        "string",
                        required=True,
                    ),
                    ToolParam(
                        "pattern",
                        "Aranacak kalıp tipi: url, ip, email, domain veya regex ifadesi",
                        "string",
                        required=True,
                    ),
                ],
                danger_level="safe",
            ),
            # --- KOPYALAMA / TAŞIMA ---
            Tool(
                name="copy_file",
                description="Dosyayı bir konumdan başka bir konuma kopyala.",
                params=[
                    ToolParam(
                        "source", "Kaynak dosya yolu veya adı", "string", required=True
                    ),
                    ToolParam(
                        "destination",
                        "Hedef yol (dizin veya tam dosya yolu)",
                        "string",
                        required=True,
                    ),
                ],
                danger_level="safe",
            ),
            Tool(
                name="move_file",
                description="Dosyayı taşı (kes-yapıştır).",
                params=[
                    ToolParam(
                        "source", "Kaynak dosya yolu veya adı", "string", required=True
                    ),
                    ToolParam("destination", "Hedef yol", "string", required=True),
                ],
                danger_level="confirm",
            ),
            # --- OLUŞTURMA ---
            Tool(
                name="create_file",
                description="Yeni bir boş dosya oluştur.",
                params=[
                    ToolParam(
                        "path", "Oluşturulacak dosyanın yolu", "string", required=True
                    ),
                    ToolParam(
                        "content",
                        "Dosya içeriği (opsiyonel)",
                        "string",
                        required=False,
                        default="",
                    ),
                ],
                danger_level="safe",
            ),
            Tool(
                name="create_directory",
                description="Yeni bir dizin/klasör oluştur.",
                params=[
                    ToolParam(
                        "path", "Oluşturulacak dizinin yolu", "string", required=True
                    ),
                ],
                danger_level="safe",
            ),
            # --- SİLME ---
            Tool(
                name="delete_file",
                description="Dosya sil. DİKKAT: Geri alınamaz!",
                params=[
                    ToolParam(
                        "path", "Silinecek dosya yolu veya adı", "string", required=True
                    ),
                ],
                danger_level="dangerous",
            ),
            Tool(
                name="delete_directory",
                description="Dizin ve içeriğini sil. DİKKAT: Geri alınamaz!",
                params=[
                    ToolParam(
                        "path", "Silinecek dizin yolu veya adı", "string", required=True
                    ),
                ],
                danger_level="dangerous",
            ),
            # --- YENİDEN ADLANDIRMA ---
            Tool(
                name="rename",
                description="Dosya veya dizini yeniden adlandır.",
                params=[
                    ToolParam(
                        "path", "Dosya/dizin yolu veya adı", "string", required=True
                    ),
                    ToolParam(
                        "new_name",
                        "Yeni ad (sadece isim, yol değil)",
                        "string",
                        required=True,
                    ),
                ],
                danger_level="confirm",
            ),
            # --- BİLGİ ---
            Tool(
                name="get_file_info",
                description="Dosya hakkında detaylı bilgi getir (boyut, tarih, yol).",
                params=[
                    ToolParam("path", "Dosya yolu veya adı", "string", required=True),
                ],
                danger_level="safe",
            ),
            Tool(
                name="find_directory_size",
                description="Dizinin toplam boyutunu hesapla.",
                params=[
                    ToolParam("path", "Dizin yolu veya adı", "string", required=True),
                ],
                danger_level="safe",
            ),
            # --- İÇERİK İŞLEMLERİ ---
            Tool(
                name="search_in_files",
                description="Dosyaların içinde metin veya regex ara.",
                params=[
                    ToolParam(
                        "query", "Aranacak metin veya regex", "string", required=True
                    ),
                    ToolParam("directory", "Aranacak dizin", "string", required=False),
                    ToolParam("extension", "Uzantı filtresi", "string", required=False),
                    ToolParam(
                        "is_regex",
                        "Regex kullan",
                        "boolean",
                        required=False,
                        default=False,
                    ),
                    ToolParam(
                        "limit", "Maks sonuç", "number", required=False, default=20
                    ),
                ],
                danger_level="safe",
            ),
            Tool(
                name="append_to_file",
                description="Dosyanın sonuna içerik ekle (mevcut içeriği silmez).",
                params=[
                    ToolParam("path", "Dosya yolu veya adı", "string", required=True),
                    ToolParam("content", "Eklenecek içerik", "string", required=True),
                ],
                danger_level="safe",
            ),
            Tool(
                name="replace_text",
                description="Dosya içindeki metni bul ve değiştir.",
                params=[
                    ToolParam("path", "Dosya yolu veya adı", "string", required=True),
                    ToolParam(
                        "old_text", "Değiştirilecek metin", "string", required=True
                    ),
                    ToolParam("new_text", "Yeni metin", "string", required=True),
                    ToolParam(
                        "is_regex",
                        "Regex kullan",
                        "boolean",
                        required=False,
                        default=False,
                    ),
                ],
                danger_level="confirm",
            ),
            Tool(
                name="count_lines_words",
                description="Dosyadaki satır, kelime ve karakter sayısını göster.",
                params=[
                    ToolParam("path", "Dosya yolu veya adı", "string", required=True),
                ],
                danger_level="safe",
            ),
            # --- BÜYÜK/KÜÇÜK DOSYALAR ---
            Tool(
                name="find_largest_files",
                description="En büyük dosyaları bul. Boyut filtresi opsiyonel.",
                params=[
                    ToolParam(
                        "min_size_mb",
                        "Minimum boyut MB cinsinden",
                        "number",
                        required=False,
                    ),
                    ToolParam("extension", "Uzantı filtresi", "string", required=False),
                    ToolParam("directory", "Dizin filtresi", "string", required=False),
                    ToolParam(
                        "limit", "Kaç dosya", "number", required=False, default=10
                    ),
                ],
                danger_level="safe",
            ),
            Tool(
                name="find_small_files",
                description="Belirli boyutun altındaki dosyaları bul.",
                params=[
                    ToolParam(
                        "max_size_mb",
                        "Maksimum boyut MB cinsinden",
                        "number",
                        required=False,
                        default=1.0,
                    ),
                    ToolParam("extension", "Uzantı filtresi", "string", required=False),
                    ToolParam("directory", "Dizin filtresi", "string", required=False),
                    ToolParam(
                        "limit", "Maks sonuç", "number", required=False, default=20
                    ),
                ],
                danger_level="safe",
            ),
            Tool(
                name="find_empty_files",
                description="Boş (0 byte) dosyaları bul.",
                params=[
                    ToolParam("directory", "Dizin filtresi", "string", required=False),
                ],
                danger_level="safe",
            ),
            Tool(
                name="find_empty_directories",
                description="Boş klasörleri bul (dosya ve alt klasör içermeyen).",
                params=[],
                danger_level="safe",
            ),
            Tool(
                name="get_extension_stats",
                description="Uzantı bazlı istatistikler (kaç dosya, toplam boyut).",
                params=[
                    ToolParam("directory", "Dizin filtresi", "string", required=False),
                ],
                danger_level="safe",
            ),
            Tool(
                name="find_duplicate_names",
                description="Aynı isimde birden fazla konumda olan dosyaları bul.",
                params=[
                    ToolParam("name", "Dosya adı filtresi", "string", required=False),
                    ToolParam("extension", "Uzantı filtresi", "string", required=False),
                    ToolParam(
                        "min_count",
                        "Minimum tekrar sayısı",
                        "number",
                        required=False,
                        default=2,
                    ),
                ],
                danger_level="safe",
            ),
            Tool(
                name="compare_files",
                description="İki dosyayı karşılaştır (aynı mı farklı mı).",
                params=[
                    ToolParam(
                        "file_path_1",
                        "Birinci dosya yolu veya adı",
                        "string",
                        required=True,
                    ),
                    ToolParam(
                        "file_path_2",
                        "İkinci dosya yolu veya adı",
                        "string",
                        required=True,
                    ),
                ],
                danger_level="safe",
            ),
            Tool(
                name="get_directory_tree",
                description="Dizin ağacını göster.",
                params=[
                    ToolParam("path", "Dizin yolu veya adı", "string", required=True),
                    ToolParam(
                        "max_depth",
                        "Kaç seviye derine in",
                        "number",
                        required=False,
                        default=3,
                    ),
                ],
                danger_level="safe",
            ),
        ]

    # ================================================================
    # DİNAMİK YOL ÇÖZÜMLEME (Tüm metotların kullandığı çekirdek)
    # ================================================================

    def _resolve_file_path(self, identifier: str) -> Optional[str]:
        """
        Verilen herhangi bir tanımlayıcıdan (isim, kısmi yol, tam yol) dosyanın
        gerçek tam yolunu bul.

        Çözümleme sırası:
            1. Tam yol ve dosya mevcutsa → doğrudan döndür
            2. Göreceli yol olarak mevcut dizinde kontrol
            3. Dosya adı olarak tam eşleşme ara (DB'de)
            4. Fuzzy arama ile bul
            5. Bulunamazsa → None

        Örnekler:
            "test.txt"           → "/home/user/Documents/test.txt"
            "/home/user/test.txt" → "/home/user/test.txt" (doğrudan)
            "config"             → "/etc/myapp/config.json" (fuzzy)
        """
        if not identifier:
            return None

        identifier = identifier.strip().strip('"').strip("'")

        # 1) Tam yol kontrolü
        p = Path(identifier)
        if p.is_absolute() and p.exists() and p.is_file():
            return str(p)

        # 2) Göreceli yol olarak mevcut dizinde kontrol
        if p.exists() and p.is_file():
            return str(p.resolve())

        # 3) DB'den tam eşleşme ile ara
        name_part = p.stem  # "test" from "test.txt"
        ext_part = p.suffix  # ".txt" from "test.txt"

        # Önce tam isim ile dene (uzantı dahil)
        if ext_part:
            exact = self.query_engine.search_files_by_exact_name(
                name=name_part, extension=ext_part
            )
            if exact:
                return exact[0]["full_path"]

        # 4) Uzantısız isim ile dene
        exact_no_ext = self.query_engine.search_files_by_exact_name(name=identifier)
        if exact_no_ext:
            return exact_no_ext[0]["full_path"]

        # 5) Fuzzy arama
        results = self.query_engine.search_files(
            name=name_part, extension=ext_part or None, limit=5
        )
        if results:
            # Tam isim eşleşmesini tercih et
            full_name = f"{name_part}{ext_part}" if ext_part else name_part
            for r in results:
                r_full = f"{r.get('name', '')}{r.get('extension', '')}"
                if r_full.lower() == full_name.lower():
                    return r["full_path"]
            # Tam eşleşme yoksa ilk sonucu döndür
            return results[0]["full_path"]

        return None

    def _resolve_dir_path(self, identifier: str) -> Optional[str]:
        """
        Verilen herhangi bir tanımlayıcıdan dizinin gerçek tam yolunu bul.

        Çözümleme sırası:
            1. Tam yol ve dizin mevcutsa → doğrudan döndür
            2. Göreceli yol kontrol
            3. Dizin adı olarak DB'de ara
            4. Bulunamazsa → None
        """
        if not identifier:
            return None

        identifier = identifier.strip().strip('"').strip("'")

        # 1) Tam yol kontrolü
        p = Path(identifier)
        if p.is_absolute() and p.exists() and p.is_dir():
            return str(p)

        # 2) Göreceli yol
        if p.exists() and p.is_dir():
            return str(p.resolve())

        # 3) DB'den ara
        dirs = self.query_engine.search_directories(name=identifier, limit=5)
        if dirs:
            # Tam isim eşleşmesi tercih et
            for d in dirs:
                if d.get("name", "").lower() == identifier.lower():
                    return d["full_path"]
            return dirs[0]["full_path"]

        return None

    def _extract_path_param(self, kwargs: dict) -> Optional[str]:
        """
        LLM'den gelen parametrelerden dosya yolunu çıkar.
        Birden fazla olası parametre adını destekler.

        Desteklenen parametre isimleri:
            path, file_path, filepath, name, file_name, filename, dosya, file
        """
        for key in (
            "path",
            "file_path",
            "filepath",
            "name",
            "file_name",
            "filename",
            "dosya",
            "file",
        ):
            if key in kwargs and kwargs[key]:
                return kwargs[key]
        return None

    def _extract_dir_param(self, kwargs: dict) -> Optional[str]:
        """
        LLM'den gelen parametrelerden dizin yolunu çıkar.

        Desteklenen parametre isimleri:
            path, dir_path, dirpath, directory, klasor, dizin, folder
        """
        for key in (
            "path",
            "dir_path",
            "dirpath",
            "directory",
            "klasor",
            "dizin",
            "folder",
        ):
            if key in kwargs and kwargs[key]:
                return kwargs[key]
        return None

    # ================================================================
    # ARAMA İŞLEMLERİ
    # ================================================================

    def search_files(
        self,
        name=None,
        extension=None,
        directory=None,
        min_size_mb=None,
        max_size_mb=None,
        limit=50,
        **kwargs,
    ) -> dict:
        """Dosya ara. Esnek parametre kabul eder."""
        if not name:
            name = kwargs.get("query") or kwargs.get("search") or kwargs.get("dosya")

        limit = max(limit, 10)

        # LLM bazen name'e "*.py" gibi wildcard gönderir — temizle
        if name:
            name = name.strip().strip("*").strip()
            if not name or name.startswith("."):
                if name and not extension:
                    extension = name if name.startswith(".") else f".{name}"
                name = None

        # extension normalize
        if extension and not extension.startswith("."):
            extension = f".{extension}"

        # Önce tam eşleşme dene
        if name:
            exact = self.query_engine.search_files_by_exact_name(
                name=name, extension=extension
            )
            if exact:
                return {"success": True, "data": exact, "count": len(exact)}

        # Tam eşleşme yoksa fuzzy ara
        results = self.query_engine.search_files(
            name=name,
            extension=extension,
            directory=directory,
            min_size_mb=min_size_mb,
            max_size_mb=max_size_mb,
            limit=limit,
        )
        return {"success": True, "data": results, "count": len(results)}

    def search_directories(
        self, name=None, parent_path=None, limit=20, **kwargs
    ) -> dict:
        """Dizin ara."""
        if not name:
            name = kwargs.get("query") or kwargs.get("search")

        results = self.query_engine.search_directories(
            name=name,
            parent_path=parent_path,
            limit=limit,
        )
        return {"success": True, "data": results, "count": len(results)}

    def find_recently_modified(
        self, days=7, extension=None, directory=None, **kwargs
    ) -> dict:
        results = self.query_engine.find_recently_modified(
            days=days,
            extension=extension,
            directory=directory,
        )
        return {"success": True, "data": results, "count": len(results)}

    def list_directory_contents(
        self, path=None, dir_path=None, extension=None, ext=None, filter=None, **kwargs
    ) -> dict:
        """Dizin içeriğini listele. Opsiyonel uzantı filtresi.

        Args:
            path/dir_path: Dizin yolu
            extension/ext/filter: Uzantı filtresi (.py, .txt, py, txt)
        """
        raw = path or dir_path or self._extract_dir_param(kwargs)
        if not raw:
            return {"success": False, "error": "Dizin belirtilmedi"}

        resolved = self._resolve_dir_path(raw)
        if not resolved:
            return {"success": False, "error": f"Dizin bulunamadı: {raw}"}

        results = self.query_engine.get_directory_contents(resolved)
        if "error" in results:
            return {"success": False, "error": results["error"]}

        # Uzantı filtresi
        ext_filter = extension or ext or filter
        if ext_filter:
            # ".py" veya "py" ikisini de kabul et
            if not ext_filter.startswith("."):
                ext_filter = "." + ext_filter
            ext_filter = ext_filter.lower()

            filtered = [
                f
                for f in results.get("files", [])
                if f.get("extension", "").lower() == ext_filter
            ]
            results["files"] = filtered
            results["filter"] = ext_filter

        return {"success": True, "data": results}

    # ================================================================
    # DOSYA OKUMA
    # ================================================================

    def read_file(
        self, path=None, file_path=None, name=None, max_lines: int = 50, **kwargs
    ) -> dict:
        """
        Dosya oku — DİNAMİK.

        Kabul edilen parametreler:
            path="test.txt"              → DB'den bulup okur
            file_path="/full/path.txt"   → doğrudan okur
            name="config"               → DB'den arayıp okur

        LLM path=, file_path=, name= ne gönderirse göndersin çalışır.
        """
        raw = path or file_path or name or self._extract_path_param(kwargs)

        if not raw:
            return {
                "success": False,
                "error": "Dosya belirtilmedi. Bir dosya adı veya yolu verin.",
            }

        # Dinamik yol çözümleme
        resolved = self._resolve_file_path(raw)
        if not resolved:
            return {
                "success": False,
                "error": f"Dosya bulunamadı: '{raw}'. "
                f"Lütfen dosyanın tam yolunu veya doğru adını verin.",
            }

        resolved_path = Path(resolved)
        if not resolved_path.is_file():
            return {"success": False, "error": f"Bu bir dosya değil: {resolved}"}

        try:
            content = resolved_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            truncated = len(lines) > max_lines
            if truncated:
                lines = lines[:max_lines]
            return {
                "success": True,
                "content": "\n".join(lines),
                "total_lines": len(content.splitlines()),
                "truncated": truncated,
                "file_path": resolved,
                "message": f"{resolved_path.name} okundu ({len(content.splitlines())} satır)",
            }
        except UnicodeDecodeError:
            return {
                "success": False,
                "error": "Dosya metin formatında değil (binary olabilir)",
            }
        except Exception as e:
            return {"success": False, "error": f"Okuma hatası: {str(e)}"}

    def write_file(self, path=None, file_path=None, content="", **kwargs) -> dict:
        """
        Dosyaya yaz — DİNAMİK.
        Dosya varsa üzerine yazar, yoksa oluşturur.
        create_file'dan farkı: mevcut dosyanın üzerine yazabilir.
        """
        raw = path or file_path or self._extract_path_param(kwargs)
        content = content or kwargs.get("text", "")

        if not raw:
            return {"success": False, "error": "Dosya yolu belirtilmedi"}

        # Eğer sadece isim geldiyse ve dosya mevcutsa, önce bul
        p = Path(raw)
        if not p.is_absolute():
            # Yol içinde dizin var mı? (projeler/yedek.txt)
            if "/" in raw or "\\" in raw:
                parts = Path(raw)
                dir_part = str(parts.parent)  # "projeler"
                file_part = parts.name  # "yedek.txt"
                # Dizini çözümle
                resolved_dir = self._resolve_dir_path(dir_part)
                if resolved_dir:
                    p = Path(resolved_dir) / file_part
                else:
                    # Dizin bulunamazsa mevcut dizinde oluştur
                    resolved = self._resolve_file_path(raw)
                    if resolved:
                        p = Path(resolved)
            else:
                resolved = self._resolve_file_path(raw)
                if resolved:
                    p = Path(resolved)
                # Bulunamazsa yeni dosya olarak oluştur (mevcut dizinde)

        p.parent.mkdir(parents=True, exist_ok=True)

        try:
            p.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "file_path": str(p),
                "message": f"Dosyaya yazıldı: {p.name}",
            }
        except Exception as e:
            return {"success": False, "error": f"Yazma hatası: {str(e)}"}

    def find_in_text(self, text=None, pattern=None, **kwargs) -> dict:
        """
        Metin içinde URL, IP, e-posta, domain veya özel kalıp arar.

        Desteklenen pattern türleri:
            "url"     → HTTP/HTTPS URL'leri bulur
            "ip"      → IPv4 adresleri bulur (bulamazsa domain'e fallback)
            "email"   → E-posta adresleri bulur
            "domain"  → Domain adları bulur
            "address" / "adres" → Önce IP, sonra domain, sonra URL arar (akıllı)
            "line:X"  → X metnini içeren satırları bulur
            <regex>   → Özel regex kalıbı

        Parametre esnekliği:
            text/content/data → aranacak metin
            pattern/type/find → aranacak kalıp
        """
        import re

        # Esnek parametre çözümleme
        text = (
            text or kwargs.get("content") or kwargs.get("data") or kwargs.get("input")
        )
        pattern = (
            pattern
            or kwargs.get("type")
            or kwargs.get("find")
            or kwargs.get("query")
            or kwargs.get("search")
        )

        if not text:
            return {"success": False, "error": "Aranacak metin belirtilmedi"}
        if not pattern:
            return {
                "success": False,
                "error": "Aranacak kalıp (pattern) belirtilmedi. Örn: url, ip, email veya regex",
            }

        # Eğer text aslında bir dict ise (önceki adımın çıktısı), içinden metni çıkar
        if isinstance(text, dict):
            text = (
                text.get("content")
                or text.get("data")
                or text.get("message")
                or str(text)
            )
        if isinstance(text, list):
            text = "\n".join(str(item) for item in text)

        text = str(text)

        # Önceden tanımlı regex kalıpları
        RE_IP = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
        RE_DOMAIN = r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b"
        RE_URL = r'https?://[^\s<>"\']+'

        PATTERNS = {
            "url": RE_URL,
            "ip": RE_IP,
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "domain": RE_DOMAIN,
            "ipv6": r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}",
            "mac": r"(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}",
            "phone": r"[\+]?[\d\s\-\(\)]{7,15}",
            "path": r'[A-Za-z]:\\(?:[^\\\/:*?"<>|\r\n]+\\)*[^\\\/:*?"<>|\r\n]*|/(?:[^/\0]+/)*[^/\0]+',
        }

        pattern_lower = pattern.lower().strip()

        # ── Birleşik/belirsiz pattern'ları "address"e yönlendir ──
        # LLM bazen "ip|url|domain", "ip,domain", "ip veya url" gibi gönderir
        _ADDRESS_ALIASES = {
            "address",
            "adres",
            "addr",
            "host",
            "hedef",
            "sunucu",
            "server",
            "site",
            "adress",
        }
        # Birden fazla tip içeriyorsa → address
        _MULTI_PATTERN = {"ip", "url", "domain", "host", "adres", "address"}
        pattern_tokens = set(re.split(r"[|,\s/]+", pattern_lower))
        if len(pattern_tokens & _MULTI_PATTERN) >= 2:
            pattern_lower = "address"

        if pattern_lower in _ADDRESS_ALIASES:
            return self._find_address_smart(text, RE_IP, RE_DOMAIN, RE_URL)

        # ── Satır bazlı arama: "line:kelime" ──
        if pattern_lower.startswith("line:"):
            search_term = pattern[5:].strip()
            matches = []
            for i, line in enumerate(text.splitlines(), 1):
                if search_term.lower() in line.lower():
                    matches.append({"line": i, "text": line.strip()})
            return {
                "success": True,
                "data": matches,
                "count": len(matches),
                "pattern_type": "line_search",
                "message": f"'{search_term}' için {len(matches)} satır eşleşti",
            }

        # ── Bilinen pattern tipi mi? ──
        if pattern_lower in PATTERNS:
            regex = PATTERNS[pattern_lower]
            pattern_type = pattern_lower
        else:
            # Özel regex olarak kullan
            try:
                re.compile(pattern)
                regex = pattern
                pattern_type = "custom_regex"
            except re.error:
                # Regex değilse düz metin araması yap
                matches = []
                for i, line in enumerate(text.splitlines(), 1):
                    if pattern.lower() in line.lower():
                        matches.append({"line": i, "text": line.strip()})
                return {
                    "success": True,
                    "data": [line["text"] for line in matches] if matches else [],
                    "count": len(matches),
                    "pattern_type": "text_search",
                    "message": f"'{pattern}' için {len(matches)} eşleşme bulundu",
                }

        # ── Regex ile bul ──
        found = re.findall(regex, text)
        unique = list(dict.fromkeys(found))

        # ── IP bulunamadıysa domain'e fallback ──
        if not unique and pattern_lower == "ip":
            domain_found = re.findall(RE_DOMAIN, text)
            domain_unique = list(dict.fromkeys(domain_found))
            if domain_unique:
                return {
                    "success": True,
                    "data": domain_unique,
                    "count": len(domain_unique),
                    "pattern_type": "domain (ip bulunamadı, domain'e geçildi)",
                    "message": f"IP bulunamadı, {len(domain_unique)} domain bulundu",
                }

        # ── URL bulunamadıysa domain'e fallback ──
        if not unique and pattern_lower == "url":
            domain_found = re.findall(RE_DOMAIN, text)
            domain_unique = list(dict.fromkeys(domain_found))
            if domain_unique:
                return {
                    "success": True,
                    "data": domain_unique,
                    "count": len(domain_unique),
                    "pattern_type": "domain (url bulunamadı, domain'e geçildi)",
                    "message": f"URL bulunamadı, {len(domain_unique)} domain bulundu",
                }

        return {
            "success": True,
            "data": unique,
            "count": len(unique),
            "total_with_duplicates": len(found),
            "pattern_type": pattern_type,
            "message": f"{len(unique)} benzersiz {pattern_type} bulundu"
            if unique
            else f"Hiç {pattern_type} bulunamadı",
        }

    def _find_address_smart(
        self, text: str, re_ip: str, re_domain: str, re_url: str
    ) -> dict:
        """
        Akıllı adres arama: metin içinde ne tür adres varsa onu bul.
        Öncelik sırası: IP → Domain → URL → satır bazlı fallback
        """
        import re

        all_found = []
        found_types = []

        # 1) IP adresleri
        ips = list(dict.fromkeys(re.findall(re_ip, text)))
        if ips:
            all_found.extend(ips)
            found_types.append(f"{len(ips)} IP")

        # 2) Domain adresleri (IP olmayanlar)
        domains = list(dict.fromkeys(re.findall(re_domain, text)))
        # IP'leri domain listesinden çıkar (çakışmayı önle)
        domains = [d for d in domains if d not in ips]
        if domains:
            all_found.extend(domains)
            found_types.append(f"{len(domains)} domain")

        # 3) URL'ler (zaten domain'e dahil olanları tekrarlama)
        urls = list(dict.fromkeys(re.findall(re_url, text)))
        new_urls = [
            u for u in urls if not any(u.endswith(d) or d in u for d in domains + ips)
        ]
        if new_urls:
            all_found.extend(new_urls)
            found_types.append(f"{len(new_urls)} URL")

        # 4) Hiçbir şey bulunamadıysa → boş dön (eski: tüm satırları döndürüyordu)
        type_summary = ", ".join(found_types) if found_types else "hiçbir şey"

        return {
            "success": True,
            "data": all_found,
            "count": len(all_found),
            "pattern_type": "address_smart",
            "message": f"Bulunan: {type_summary}"
            if all_found
            else "Hiç adres bulunamadı",
        }

    # ================================================================
    # KOPYALAMA / TAŞIMA
    # ================================================================

    def copy_file(self, source=None, destination=None, **kwargs) -> dict:
        """Dosya kopyala — kaynak dinamik çözümlenir."""
        source = source or kwargs.get("src") or kwargs.get("from")
        destination = (
            destination
            or kwargs.get("dest")
            or kwargs.get("to")
            or kwargs.get("target")
        )

        if not source:
            return {"success": False, "error": "Kaynak dosya belirtilmedi"}
        if not destination:
            return {"success": False, "error": "Hedef belirtilmedi"}

        resolved_src = self._resolve_file_path(source)
        if not resolved_src:
            return {"success": False, "error": f"Kaynak dosya bulunamadı: {source}"}

        src = Path(resolved_src)
        dst = Path(destination)

        if not dst.is_absolute():
            resolved_dst_dir = self._resolve_dir_path(destination)
            if resolved_dst_dir:
                dst = Path(resolved_dst_dir) / src.name
            else:
                dst = src.parent / destination

        if dst.is_dir():
            dst = dst / src.name

        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(str(src), str(dst))
            return {
                "success": True,
                "source": str(src),
                "destination": str(dst),
                "message": f"Dosya kopyalandı: {src.name}",
            }
        except Exception as e:
            return {"success": False, "error": f"Kopyalama hatası: {str(e)}"}

    def move_file(self, source=None, destination=None, **kwargs) -> dict:
        """Dosya taşı — kaynak dinamik çözümlenir."""
        source = source or kwargs.get("src") or kwargs.get("from")
        destination = (
            destination
            or kwargs.get("dest")
            or kwargs.get("to")
            or kwargs.get("target")
        )

        if not source:
            return {"success": False, "error": "Kaynak dosya belirtilmedi"}
        if not destination:
            return {"success": False, "error": "Hedef belirtilmedi"}

        resolved_src = self._resolve_file_path(source)
        if not resolved_src:
            return {"success": False, "error": f"Kaynak bulunamadı: {source}"}

        src = Path(resolved_src)
        dst = Path(destination)

        if not dst.is_absolute():
            resolved_dst_dir = self._resolve_dir_path(destination)
            if resolved_dst_dir:
                dst = Path(resolved_dst_dir) / src.name
            else:
                dst = src.parent / destination

        if dst.is_dir():
            dst = dst / src.name

        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.move(str(src), str(dst))
            return {
                "success": True,
                "source": str(src),
                "destination": str(dst),
                "message": f"Dosya taşındı: {src.name}",
            }
        except Exception as e:
            return {"success": False, "error": f"Taşıma hatası: {str(e)}"}

    # ================================================================
    # OLUŞTURMA
    # ================================================================

    def create_file(self, path=None, file_path=None, content="", **kwargs) -> dict:
        """Yeni dosya oluştur — esnek parametre."""
        raw = path or file_path or self._extract_path_param(kwargs)
        if not raw:
            return {"success": False, "error": "Dosya yolu belirtilmedi"}

        content = content or kwargs.get("text", "")
        p = Path(raw)

        # Göreli yolda dizin varsa çözümle (projeler/yeni.txt)
        if not p.is_absolute() and ("/" in raw or "\\" in raw):
            dir_part = str(Path(raw).parent)
            file_part = Path(raw).name
            resolved_dir = self._resolve_dir_path(dir_part)
            if resolved_dir:
                p = Path(resolved_dir) / file_part

        if p.exists():
            return {"success": False, "error": f"Dosya zaten var: {raw}"}

        p.parent.mkdir(parents=True, exist_ok=True)

        try:
            p.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "file_path": str(p),
                "message": f"Dosya oluşturuldu: {p.name}",
            }
        except Exception as e:
            return {"success": False, "error": f"Oluşturma hatası: {str(e)}"}

    def create_directory(self, path=None, dir_path=None, **kwargs) -> dict:
        """Yeni dizin oluştur — esnek parametre."""
        raw = path or dir_path or self._extract_dir_param(kwargs)
        if not raw:
            return {"success": False, "error": "Dizin yolu belirtilmedi"}

        p = Path(raw)

        if p.exists():
            return {"success": False, "error": f"Dizin zaten var: {raw}"}

        try:
            p.mkdir(parents=True, exist_ok=True)
            return {
                "success": True,
                "dir_path": str(p),
                "message": f"Dizin oluşturuldu: {p.name}",
            }
        except Exception as e:
            return {"success": False, "error": f"Oluşturma hatası: {str(e)}"}

    # ================================================================
    # SİLME
    # ================================================================

    def delete_file(self, path=None, file_path=None, **kwargs) -> dict:
        """Dosya sil — dinamik çözümleme."""
        raw = path or file_path or self._extract_path_param(kwargs)
        if not raw:
            return {"success": False, "error": "Silinecek dosya belirtilmedi"}

        resolved = self._resolve_file_path(raw)
        if not resolved:
            return {"success": False, "error": f"Dosya bulunamadı: {raw}"}

        try:
            Path(resolved).unlink()
            return {
                "success": True,
                "file_path": resolved,
                "message": f"Dosya silindi: {Path(resolved).name}",
            }
        except Exception as e:
            return {"success": False, "error": f"Silme hatası: {str(e)}"}

    def delete_directory(self, path=None, dir_path=None, **kwargs) -> dict:
        """Dizin sil — dinamik çözümleme."""
        raw = path or dir_path or self._extract_dir_param(kwargs)
        if not raw:
            return {"success": False, "error": "Silinecek dizin belirtilmedi"}

        resolved = self._resolve_dir_path(raw)
        if not resolved:
            return {"success": False, "error": f"Dizin bulunamadı: {raw}"}

        try:
            shutil.rmtree(resolved)
            return {
                "success": True,
                "dir_path": resolved,
                "message": f"Dizin silindi: {Path(resolved).name}",
            }
        except Exception as e:
            return {"success": False, "error": f"Silme hatası: {str(e)}"}

    # ================================================================
    # YENİDEN ADLANDIRMA
    # ================================================================

    def rename(self, path=None, new_name=None, **kwargs) -> dict:
        """Dosya/dizin yeniden adlandır — dinamik çözümleme."""
        raw = path or self._extract_path_param(kwargs)
        new_name = new_name or kwargs.get("new") or kwargs.get("to")

        if not raw:
            return {"success": False, "error": "Dosya/dizin belirtilmedi"}
        if not new_name:
            return {"success": False, "error": "Yeni isim belirtilmedi"}

        # Önce dosya olarak dene
        resolved = self._resolve_file_path(raw)
        # Dosya bulunamazsa dizin olarak dene
        if not resolved:
            resolved = self._resolve_dir_path(raw)
        if not resolved:
            return {"success": False, "error": f"Bulunamadı: {raw}"}

        src = Path(resolved)
        dst = src.parent / new_name

        if dst.exists():
            return {"success": False, "error": f"Bu isimde zaten var: {new_name}"}

        try:
            src.rename(dst)
            return {
                "success": True,
                "old_path": str(src),
                "new_path": str(dst),
                "message": f"Yeniden adlandırıldı: {src.name} -> {new_name}",
            }
        except Exception as e:
            return {"success": False, "error": f"Yeniden adlandırma hatası: {str(e)}"}

    # ================================================================
    # BİLGİ
    # ================================================================

    def get_file_info(self, path=None, file_path=None, **kwargs) -> dict:
        """Dosya bilgisi — dinamik çözümleme."""
        raw = path or file_path or self._extract_path_param(kwargs)
        if not raw:
            return {"success": False, "error": "Dosya belirtilmedi"}

        resolved = self._resolve_file_path(raw)
        if not resolved:
            return {"success": False, "error": f"Bulunamadı: {raw}"}

        p = Path(resolved)
        stat = p.stat()
        size = stat.st_size

        return {
            "success": True,
            "data": {
                "name": p.name,
                "extension": p.suffix,
                "full_path": str(p),
                "directory": str(p.parent),
                "size_bytes": size,
                "size_human": self._human_size(size),
                "created": datetime.fromtimestamp(stat.st_ctime).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d %H:%M"
                ),
                "is_file": p.is_file(),
                "is_dir": p.is_dir(),
            },
        }

    def find_directory_size(self, path=None, dir_path=None, **kwargs) -> dict:
        """Dizin boyutu — dinamik çözümleme."""
        raw = path or dir_path or self._extract_dir_param(kwargs)
        if not raw:
            return {"success": False, "error": "Dizin belirtilmedi"}

        resolved = self._resolve_dir_path(raw)
        if not resolved:
            return {"success": False, "error": f"Dizin bulunamadı: {raw}"}

        result = self.query_engine.get_directory_size(resolved)
        return {"success": True, "data": result}

    # ================================================================
    # İÇERİK İŞLEMLERİ
    # ================================================================

    def search_in_files(
        self,
        query=None,
        directory=None,
        extension=None,
        is_regex=False,
        limit=20,
        **kwargs,
    ) -> dict:
        """Dosyaların içinde metin ara."""
        import re

        query = (
            query or kwargs.get("text") or kwargs.get("search") or kwargs.get("pattern")
        )
        if not query:
            return {"success": False, "error": "Aranacak metin belirtilmedi"}

        results = []
        search_files = self.query_engine.search_files(
            extension=extension, directory=directory, limit=500
        )
        pattern = re.compile(query) if is_regex else None

        for f in search_files:
            try:
                fpath = Path(f["full_path"])
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                matches = []
                for i, line in enumerate(content.splitlines(), 1):
                    if pattern:
                        if pattern.search(line):
                            matches.append({"line": i, "text": line.strip()})
                    else:
                        if query.lower() in line.lower():
                            matches.append({"line": i, "text": line.strip()})
                if matches:
                    results.append(
                        {
                            "file": f["full_path"],
                            "name": f"{f['name']}{f['extension']}",
                            "matches": matches[:5],
                            "total_matches": len(matches),
                        }
                    )
                    if len(results) >= limit:
                        break
            except Exception:
                continue

        return {"success": True, "data": results, "count": len(results)}

    def append_to_file(self, path=None, file_path=None, content=None, **kwargs) -> dict:
        """Dosyaya içerik ekle — dinamik çözümleme. Dosya yoksa oluşturur."""
        raw = path or file_path or self._extract_path_param(kwargs)
        content = content or kwargs.get("text", "")

        if not raw:
            return {"success": False, "error": "Dosya belirtilmedi"}
        if not content:
            return {"success": False, "error": "Eklenecek içerik belirtilmedi"}

        # Önce mevcut dosyayı bul
        resolved = self._resolve_file_path(raw)

        if not resolved:
            # Dosya yok → write_file gibi oluştur
            p = Path(raw)
            if not p.is_absolute():
                # Dizin yolu varsa çözümle (projeler/birlesik.txt)
                if "/" in raw or "\\" in raw:
                    dir_part = str(Path(raw).parent)
                    file_part = Path(raw).name
                    resolved_dir = self._resolve_dir_path(dir_part)
                    if resolved_dir:
                        p = Path(resolved_dir) / file_part
                # Dizin yolu yoksa mevcut dizinde oluştur
            p.parent.mkdir(parents=True, exist_ok=True)
            resolved = str(p)

        try:
            with open(resolved, "a", encoding="utf-8") as f:
                f.write(content + "\n")
            return {
                "success": True,
                "message": f"İçerik eklendi: {Path(resolved).name}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def replace_text(
        self,
        path=None,
        file_path=None,
        old_text=None,
        new_text=None,
        is_regex=False,
        **kwargs,
    ) -> dict:
        """Dosyada metin bul-değiştir — dinamik çözümleme."""
        import re

        raw = path or file_path or self._extract_path_param(kwargs)
        old_text = old_text or kwargs.get("find") or kwargs.get("search")
        new_text = new_text if new_text is not None else kwargs.get("replace", "")

        if not raw:
            return {"success": False, "error": "Dosya belirtilmedi"}
        if not old_text:
            return {"success": False, "error": "Değiştirilecek metin belirtilmedi"}

        resolved = self._resolve_file_path(raw)
        if not resolved:
            return {"success": False, "error": f"Dosya bulunamadı: {raw}"}

        try:
            p = Path(resolved)
            content = p.read_text(encoding="utf-8")
            if is_regex:
                new_content = re.sub(old_text, new_text, content)
                count = len(re.findall(old_text, content))
            else:
                count = content.count(old_text)
                new_content = content.replace(old_text, new_text)
            if count == 0:
                return {"success": False, "error": f"'{old_text}' bulunamadı"}
            p.write_text(new_content, encoding="utf-8")
            return {"success": True, "message": f"{count} değişiklik yapıldı: {p.name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def count_lines_words(self, path=None, file_path=None, **kwargs) -> dict:
        """Satır/kelime/karakter say — dinamik çözümleme."""
        raw = path or file_path or self._extract_path_param(kwargs)
        if not raw:
            return {"success": False, "error": "Dosya belirtilmedi"}

        resolved = self._resolve_file_path(raw)
        if not resolved:
            return {"success": False, "error": f"Dosya bulunamadı: {raw}"}

        try:
            p = Path(resolved)
            content = p.read_text(encoding="utf-8")
            lines = content.splitlines()
            words = content.split()
            return {
                "success": True,
                "data": {
                    "file": p.name,
                    "lines": len(lines),
                    "words": len(words),
                    "characters": len(content),
                },
                "message": f"{p.name}: {len(lines)} satır, {len(words)} kelime, {len(content)} karakter",
            }
        except UnicodeDecodeError:
            return {"success": False, "error": "Dosya metin formatında değil"}

    # ================================================================
    # BÜYÜK / KÜÇÜK / BOŞ DOSYALAR
    # ================================================================

    def find_largest_files(
        self, min_size_mb=None, extension=None, directory=None, limit=10, **kwargs
    ) -> dict:
        results = self.query_engine.find_largest_files(
            extension=extension, directory=directory, limit=limit
        )
        if min_size_mb is not None:
            min_bytes = int(min_size_mb * 1024 * 1024)
            results = [r for r in results if r.get("size_bytes", 0) >= min_bytes]
        return {"success": True, "data": results, "count": len(results)}

    def find_small_files(
        self, max_size_mb=None, extension=None, directory=None, limit=20, **kwargs
    ) -> dict:
        results = self.query_engine.find_small_files(
            extension=extension, directory=directory, limit=limit
        )
        if max_size_mb is not None:
            max_bytes = int(max_size_mb * 1024 * 1024)
            results = [r for r in results if r.get("size_bytes", 0) <= max_bytes]
        return {"success": True, "data": results, "count": len(results)}

    def find_empty_files(self, directory=None, **kwargs) -> dict:
        results = self.query_engine.find_empty_files(directory=directory)
        return {"success": True, "data": results, "count": len(results)}

    def find_empty_directories(self, **kwargs) -> dict:
        results = self.query_engine.find_empty_directories()
        return {"success": True, "data": results, "count": len(results)}

    def get_extension_stats(self, directory=None, **kwargs) -> dict:
        results = self.query_engine.get_extension_stats(directory=directory)
        return {"success": True, "data": results, "count": len(results)}

    def find_duplicate_names(
        self, extension=None, min_count=2, name=None, **kwargs
    ) -> dict:
        results = self.query_engine.find_duplicate_names(
            extension=extension, min_count=min_count
        )
        if name:
            results = [r for r in results if name.lower() in r["name"].lower()]
        return {"success": True, "data": results, "count": len(results)}

    def compare_files(self, file_path_1=None, file_path_2=None, **kwargs) -> dict:
        """İki dosyayı karşılaştır — dinamik çözümleme."""
        import hashlib

        fp1 = file_path_1 or kwargs.get("path1") or kwargs.get("first")
        fp2 = file_path_2 or kwargs.get("path2") or kwargs.get("second")

        if not fp1 or not fp2:
            return {"success": False, "error": "İki dosya belirtilmeli"}

        resolved1 = self._resolve_file_path(fp1)
        resolved2 = self._resolve_file_path(fp2)

        if not resolved1:
            return {"success": False, "error": f"Bulunamadı: {fp1}"}
        if not resolved2:
            return {"success": False, "error": f"Bulunamadı: {fp2}"}

        p1, p2 = Path(resolved1), Path(resolved2)
        s1, s2 = p1.stat().st_size, p2.stat().st_size

        if s1 != s2:
            return {
                "success": True,
                "data": {"identical": False, "reason": f"Boyut farklı: {s1} vs {s2}"},
            }

        h1 = hashlib.md5(p1.read_bytes()).hexdigest()
        h2 = hashlib.md5(p2.read_bytes()).hexdigest()
        identical = h1 == h2

        return {
            "success": True,
            "data": {
                "identical": identical,
                "reason": "Aynı dosya" if identical else "İçerik farklı",
                "hash_1": h1,
                "hash_2": h2,
            },
            "message": "Dosyalar aynı" if identical else "Dosyalar farklı",
        }

    def get_directory_tree(self, path=None, dir_path=None, max_depth=3,
                           **kwargs) -> dict:
        """Dizin ağacı — dinamik çözümleme."""
        raw = path or dir_path or self._extract_dir_param(kwargs)
        if not raw:
            return {"success": False, "error": "Dizin belirtilmedi"}

        resolved = self._resolve_dir_path(raw)
        if not resolved:
            return {"success": False, "error": f"Dizin bulunamadı: {raw}"}

        result = self.query_engine.get_directory_tree(resolved, max_depth=max_depth)
        if "error" in result:
            return {"success": False, "error": result["error"]}
        return {"success": True, "data": result}

    # ================================================================
    # YARDIMCI
    # ================================================================

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        if size_bytes >= 1024**3:
            return f"{size_bytes / 1024**3:.2f} GB"
        elif size_bytes >= 1024**2:
            return f"{size_bytes / 1024**2:.2f} MB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes} B"