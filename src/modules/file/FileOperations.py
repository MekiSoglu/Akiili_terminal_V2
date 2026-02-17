"""
Dosya İşlemleri Modülü.

Dosya arama, kopyalama, taşıma, silme, oluşturma, yeniden adlandırma
ve dizin işlemlerini sağlar.

Bu modül BaseModule'den türer ve otomatik olarak sisteme kaydolur.
"""

import os
import shutil
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

# BaseModule'ü import et
import sys

from core.BaseModule import BaseModule, ModuleMetadata, Tool, ToolParam
from indexing.FileQueryEngine import FileQueryEngine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))



class FileOperationsModule(BaseModule):
    """Dosya sistemi işlemleri modülü."""

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
            description="Dosya arama, kopyalama, taşıma, silme, oluşturma ve dizin işlemleri",
            version="1.0.0",
        )

    @property
    def tools(self) -> list[Tool]:
        return [
            # --- ARAMA ---
            Tool(
                name="search_files",
                description="Dosya ara. İsim, uzantı, dizin, boyut filtrelerini destekler.",
                params=[
                    ToolParam("name", "Dosya adında aranacak metin", "string", required=False),
                    ToolParam("extension", "Dosya uzantısı (.py, .txt vs.)", "string", required=False),
                    ToolParam("directory", "Aranacak dizin adı veya yolu", "string", required=False),
                    ToolParam("min_size_mb", "Minimum boyut (MB)", "number", required=False),
                    ToolParam("max_size_mb", "Maximum boyut (MB)", "number", required=False),
                    ToolParam("limit", "Maksimum sonuç sayısı", "number", required=False, default=20),
                ],
                danger_level="safe",
            ),
            Tool(
                name="search_directories",
                description="Dizin/klasör ara.",
                params=[
                    ToolParam("name", "Dizin adında aranacak metin", "string", required=False),
                    ToolParam("parent_path", "Üst dizin yolu", "string", required=False),
                    ToolParam("limit", "Maksimum sonuç sayısı", "number", required=False, default=20),
                ],
                danger_level="safe",
            ),
            Tool(
                name="find_recently_modified",
                description="Son X gün içinde değiştirilen dosyaları bul.",
                params=[
                    ToolParam("days", "Kaç gün geriye bakılacak", "number", required=True),
                    ToolParam("extension", "Uzantı filtresi", "string", required=False),
                    ToolParam("directory", "Dizin filtresi", "string", required=False),
                ],
                danger_level="safe",
            ),
            Tool(
                name="list_directory_contents",
                description="Bir dizinin içeriğini listele (dosyalar ve alt dizinler).",
                params=[
                    ToolParam("dir_path", "Dizin tam yolu", "string", required=True),
                ],
                danger_level="safe",
            ),

            # --- KOPYALAMA / TAŞIMA ---
            Tool(
                name="copy_file",
                description="Dosyayı bir konumdan başka bir konuma kopyala.",
                params=[
                    ToolParam("source", "Kaynak dosya tam yolu", "string", required=True),
                    ToolParam("destination", "Hedef yol (dizin veya tam dosya yolu)", "string", required=True),
                ],
                danger_level="safe",
            ),
            Tool(
                name="move_file",
                description="Dosyayı taşı (kes-yapıştır).",
                params=[
                    ToolParam("source", "Kaynak dosya tam yolu", "string", required=True),
                    ToolParam("destination", "Hedef yol", "string", required=True),
                ],
                danger_level="confirm",
            ),

            # --- OLUŞTURMA ---
            Tool(
                name="create_file",
                description="Yeni bir boş dosya oluştur.",
                params=[
                    ToolParam("file_path", "Oluşturulacak dosyanın tam yolu", "string", required=True),
                    ToolParam("content", "Dosya içeriği (opsiyonel)", "string", required=False, default=""),
                ],
                danger_level="safe",
            ),
            Tool(
                name="create_directory",
                description="Yeni bir dizin/klasör oluştur.",
                params=[
                    ToolParam("dir_path", "Oluşturulacak dizinin tam yolu", "string", required=True),
                ],
                danger_level="safe",
            ),

            # --- SİLME ---
            Tool(
                name="delete_file",
                description="Dosya sil. DİKKAT: Geri alınamaz!",
                params=[
                    ToolParam("file_path", "Silinecek dosyanın tam yolu", "string", required=True),
                ],
                danger_level="dangerous",
            ),
            Tool(
                name="delete_directory",
                description="Dizin ve içeriğini sil. DİKKAT: Geri alınamaz!",
                params=[
                    ToolParam("dir_path", "Silinecek dizinin tam yolu", "string", required=True),
                ],
                danger_level="dangerous",
            ),

            # --- YENİDEN ADLANDIRMA ---
            Tool(
                name="rename",
                description="Dosya veya dizini yeniden adlandır.",
                params=[
                    ToolParam("path", "Dosya/dizin tam yolu", "string", required=True),
                    ToolParam("new_name", "Yeni ad (sadece isim, yol değil)", "string", required=True),
                ],
                danger_level="confirm",
            ),

            # --- BİLGİ ---
            Tool(
                name="get_file_info",
                description="Dosya hakkında detaylı bilgi getir (boyut, tarih, yol).",
                params=[
                    ToolParam("file_path", "Dosya tam yolu", "string", required=True),
                ],
                danger_level="safe",
            ),
            Tool(
                name="find_directory_size",
                description="Dizinin toplam boyutunu hesapla.",
                params=[
                    ToolParam("dir_path", "Dizin tam yolu", "string", required=True),
                ],
                danger_level="safe",
            ),
            #dosya okuma
            Tool(
                name="read_file",
                description="Dosyanın içeriğini oku ve göster.",
                params=[
                    ToolParam("file_path", "Okunacak dosyanın tam yolu", "string", required=True),
                    ToolParam("max_lines", "Maksimum satır sayısı", "number", required=False, default=50),
                ],
                danger_level="safe",
            ),
            Tool(
                name="find_largest_files",
                description="En büyük dosyaları bul. Uzantı ve dizin filtresi destekler.",
                params=[
                    ToolParam("extension", "Uzantı filtresi", "string", required=False),
                    ToolParam("directory", "Dizin filtresi", "string", required=False),
                    ToolParam("limit", "Kaç dosya getirilsin", "number", required=False, default=10),
                ],
                danger_level="safe",
            ),
            Tool(
                name="search_in_files",
                description="Dosyaların içinde metin veya regex ara.",
                params=[
                    ToolParam("query", "Aranacak metin veya regex", "string", required=True),
                    ToolParam("directory", "Aranacak dizin", "string", required=False),
                    ToolParam("extension", "Uzantı filtresi", "string", required=False),
                    ToolParam("is_regex", "Regex kullan", "boolean", required=False, default=False),
                    ToolParam("limit", "Maks sonuç", "number", required=False, default=20),
                ],
                danger_level="safe",
            ),
            Tool(
                name="append_to_file",
                description="Dosyanın sonuna içerik ekle (mevcut içeriği silmez).",
                params=[
                    ToolParam("file_path", "Dosya tam yolu", "string", required=True),
                    ToolParam("content", "Eklenecek içerik", "string", required=True),
                ],
                danger_level="safe",
            ),
            Tool(
                name="replace_text",
                description="Dosya içindeki metni bul ve değiştir.",
                params=[
                    ToolParam("file_path", "Dosya tam yolu", "string", required=True),
                    ToolParam("old_text", "Değiştirilecek metin", "string", required=True),
                    ToolParam("new_text", "Yeni metin", "string", required=True),
                    ToolParam("is_regex", "Regex kullan", "boolean", required=False, default=False),
                ],
                danger_level="confirm",
            ),
            Tool(
                name="count_lines_words",
                description="Dosyadaki satır, kelime ve karakter sayısını göster.",
                params=[
                    ToolParam("file_path", "Dosya tam yolu", "string", required=True),
                ],
                danger_level="safe",
            ),

            Tool(
                name="find_largest_files",
                description="En büyük dosyaları bul. Boyut filtresi opsiyonel.",
                params=[
                    ToolParam("min_size_mb", "Minimum boyut MB cinsinden (1KB=0.001, 100KB=0.1, 1GB=1000)", "number",
                              required=False),
                    ToolParam("extension", "Uzantı filtresi", "string", required=False),
                    ToolParam("directory", "Dizin filtresi", "string", required=False),
                    ToolParam("limit", "Kaç dosya", "number", required=False, default=10),
                ],
                danger_level="safe",
            ),

            Tool(
                name="find_small_files",
                description="Belirli boyutun altındaki dosyaları bul. Boyutu MB cinsinden ver. Örnek: 1KB=0.001, 100KB=0.1, 1MB=1, 1GB=1000",
                params=[
                    ToolParam("max_size_mb", "Maksimum boyut MB cinsinden (1KB=0.001, 100KB=0.1, 1GB=1000)", "number",
                              required=False, default=1.0),
                    ToolParam("extension", "Uzantı filtresi", "string", required=False),
                    ToolParam("directory", "Dizin filtresi", "string", required=False),
                    ToolParam("limit", "Maks sonuç", "number", required=False, default=20),
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
                    ToolParam("min_count", "Minimum tekrar sayısı", "number", required=False, default=2),
                ],
                danger_level="safe",
            ),
            Tool(
                name="compare_files",
                description="İki dosyayı karşılaştır (aynı mı farklı mı).",
                params=[
                    ToolParam("file_path_1", "Birinci dosya yolu", "string", required=True),
                    ToolParam("file_path_2", "İkinci dosya yolu", "string", required=True),
                ],
                danger_level="safe",
            ),
            Tool(
                name="get_directory_tree",
                description="Dizin ağacını göster.",
                params=[
                    ToolParam("dir_path", "Dizin tam yolu", "string", required=True),
                    ToolParam("max_depth", "Kaç seviye derine in", "number", required=False, default=3),
                ],
                danger_level="safe",
            )
        ]



    # ================================================================
    # ARAMA İŞLEMLERİ
    # ================================================================

    def search_files(self, name=None, extension=None, directory=None,
                     min_size_mb=None, max_size_mb=None, limit=50) -> dict:
        limit = max(limit, 10)

        # Önce tam eşleşme dene
        if name:
            exact = self.query_engine.search_files_by_exact_name(name=name, extension=extension)
            if exact:
                return {"success": True, "data": exact, "count": len(exact)}

        # Tam eşleşme yoksa fuzzy ara
        results = self.query_engine.search_files(
            name=name, extension=extension, directory=directory,
            min_size_mb=min_size_mb, max_size_mb=max_size_mb, limit=limit,
        )
        return {"success": True, "data": results, "count": len(results)}

    def search_directories(self, name=None, parent_path=None, limit=20) -> dict:
        results = self.query_engine.search_directories(
            name=name, parent_path=parent_path, limit=limit,
        )
        return {"success": True, "data": results, "count": len(results)}

    def find_recently_modified(self, days=7, extension=None, directory=None) -> dict:
        results = self.query_engine.find_recently_modified(
            days=days, extension=extension, directory=directory,
        )
        return {"success": True, "data": results, "count": len(results)}

    def list_directory_contents(self, dir_path: str) -> dict:
        dir_path = self._resolve_dir_path(dir_path)
        if not dir_path:
            return {"success": False, "error": "Dizin bulunamadı"}

        results = self.query_engine.get_directory_contents(dir_path)
        if "error" in results:
            return {"success": False, "error": results["error"]}
        return {"success": True, "data": results}

    # ================================================================
    # KOPYALAMA / TAŞIMA
    # ================================================================

    def copy_file(self, source: str, destination: str) -> dict:
        src = Path(source)
        if not src.exists():
            return {"success": False, "error": f"Kaynak dosya bulunamadı: {source}"}
        if not src.is_file():
            return {"success": False, "error": f"Kaynak bir dosya değil: {source}"}

        dst = Path(destination)
        # Göreceli yolsa, kaynak dosyanın dizinine göre çöz
        if not dst.is_absolute():
            # "arabam_com_exel/cleaned_passat2.xlsx" gibi göreceli yolda
            # ilk parça zaten kaynak dizinse, tekrarı önle
            if dst.parts[0] == src.parent.name:
                dst = src.parent / Path(*dst.parts[1:])
            else:
                dst = src.parent / dst

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

    def move_file(self, source: str, destination: str) -> dict:
        src = Path(source)
        if not src.exists():
            return {"success": False, "error": f"Kaynak bulunamadı: {source}"}

        dst = Path(destination)
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

    def create_file(self, file_path: str, content: str = "") -> dict:
        path = Path(file_path)

        if path.exists():
            return {"success": False, "error": f"Dosya zaten var: {file_path}"}

        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            path.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "file_path": str(path),
                "message": f"Dosya oluşturuldu: {path.name}",
            }
        except Exception as e:
            return {"success": False, "error": f"Oluşturma hatası: {str(e)}"}

    def create_directory(self, dir_path: str) -> dict:
        path = Path(dir_path)

        if path.exists():
            return {"success": False, "error": f"Dizin zaten var: {dir_path}"}

        try:
            path.mkdir(parents=True, exist_ok=True)
            return {
                "success": True,
                "dir_path": str(path),
                "message": f"Dizin oluşturuldu: {path.name}",
            }
        except Exception as e:
            return {"success": False, "error": f"Oluşturma hatası: {str(e)}"}

    # ================================================================
    # SİLME
    # ================================================================

    def delete_file(self, file_path: str) -> dict:
        path = Path(file_path)

        if not path.exists():
            return {"success": False, "error": f"Dosya bulunamadı: {file_path}"}

        try:
            path.unlink()
            return {
                "success": True,
                "file_path": str(path),
                "message": f"Dosya silindi: {path.name}",
            }
        except Exception as e:
            return {"success": False, "error": f"Silme hatası: {str(e)}"}

    def delete_directory(self, dir_path: str) -> dict:
        path = Path(dir_path)

        if not path.exists():
            return {"success": False, "error": f"Dizin bulunamadı: {dir_path}"}

        try:
            shutil.rmtree(str(path))
            return {
                "success": True,
                "dir_path": str(path),
                "message": f"Dizin silindi: {path.name}",
            }
        except Exception as e:
            return {"success": False, "error": f"Silme hatası: {str(e)}"}

    # ================================================================
    # YENİDEN ADLANDIRMA
    # ================================================================

    def rename(self, path: str, new_name: str) -> dict:
        src = Path(path)

        if not src.exists():
            return {"success": False, "error": f"Bulunamadı: {path}"}

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

    def get_file_info(self, file_path: str) -> dict:
        path = Path(file_path)

        if not path.exists():
            return {"success": False, "error": f"Bulunamadı: {file_path}"}

        stat = path.stat()
        size = stat.st_size

        return {
            "success": True,
            "data": {
                "name": path.name,
                "extension": path.suffix,
                "full_path": str(path),
                "directory": str(path.parent),
                "size_bytes": size,
                "size_human": self._human_size(size),
                "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M"),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "is_file": path.is_file(),
                "is_dir": path.is_dir(),
            },
        }

    def _resolve_dir_path(self, dir_path: str):
        if Path(dir_path).is_absolute() and Path(dir_path).exists():
            return dir_path
        dirs = self.query_engine.search_directories(name=dir_path, limit=1)
        if dirs:
            return dirs[0]["full_path"]
        return None

    def find_directory_size(self, dir_path: str) -> dict:
        dir_path = self._resolve_dir_path(dir_path)
        if not dir_path:
            return {"success": False, "error": "Dizin bulunamadı"}

        dir_path = self._resolve_dir_path(dir_path)
        if not dir_path:
            return {"success": False, "error": f"Dizin bulunamadı: {dir_path}"}
        result = self.query_engine.get_directory_size(dir_path)
        return {"success": True, "data": result}

    def read_file(self, file_path: str, max_lines: int = 50) -> dict:
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": f"Dosya bulunamadı: {file_path}"}
        if not path.is_file():
            return {"success": False, "error": f"Bu bir dosya değil: {file_path}"}
        try:
            content = path.read_text(encoding="utf-8")
            lines = content.splitlines()
            truncated = len(lines) > max_lines
            if truncated:
                lines = lines[:max_lines]
            return {
                "success": True,
                "content": "\n".join(lines),
                "total_lines": len(content.splitlines()),
                "truncated": truncated,
                "message": f"{path.name} okundu ({len(content.splitlines())} satır)",
            }
        except UnicodeDecodeError:
            return {"success": False, "error": "Dosya metin formatında değil (binary olabilir)"}
        except Exception as e:
            return {"success": False, "error": f"Okuma hatası: {str(e)}"}



    def search_in_files(self, query: str, directory=None, extension=None,
                        is_regex=False, limit=20) -> dict:
        import re
        results = []
        search_files = self.query_engine.search_files(
            extension=extension, directory=directory, limit=500
        )
        pattern = re.compile(query) if is_regex else None

        for f in search_files:
            try:
                path = Path(f["full_path"])
                content = path.read_text(encoding="utf-8", errors="ignore")
                matches = []
                for i, line in enumerate(content.splitlines(), 1):
                    if pattern:
                        if pattern.search(line):
                            matches.append({"line": i, "text": line.strip()})
                    else:
                        if query.lower() in line.lower():
                            matches.append({"line": i, "text": line.strip()})
                if matches:
                    results.append({
                        "file": f["full_path"],
                        "name": f"{f['name']}{f['extension']}",
                        "matches": matches[:5],
                        "total_matches": len(matches),
                    })
                    if len(results) >= limit:
                        break
            except Exception:
                continue

        return {"success": True, "data": results, "count": len(results)}

    def append_to_file(self, file_path: str, content: str) -> dict:
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": f"Dosya bulunamadı: {file_path}"}
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(content + "\n")
            return {"success": True, "message": f"İçerik eklendi: {path.name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def replace_text(self, file_path: str, old_text: str, new_text: str,
                     is_regex=False) -> dict:
        import re
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": f"Dosya bulunamadı: {file_path}"}
        try:
            content = path.read_text(encoding="utf-8")
            if is_regex:
                new_content = re.sub(old_text, new_text, content)
                count = len(re.findall(old_text, content))
            else:
                count = content.count(old_text)
                new_content = content.replace(old_text, new_text)
            if count == 0:
                return {"success": False, "error": f"'{old_text}' bulunamadı"}
            path.write_text(new_content, encoding="utf-8")
            return {"success": True, "message": f"{count} değişiklik yapıldı: {path.name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def count_lines_words(self, file_path: str) -> dict:
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": f"Dosya bulunamadı: {file_path}"}
        try:
            content = path.read_text(encoding="utf-8")
            lines = content.splitlines()
            words = content.split()
            return {
                "success": True,
                "data": {
                    "file": path.name,
                    "lines": len(lines),
                    "words": len(words),
                    "characters": len(content),
                },
                "message": f"{path.name}: {len(lines)} satır, {len(words)} kelime, {len(content)} karakter",
            }
        except UnicodeDecodeError:
            return {"success": False, "error": "Dosya metin formatında değil"}

    def find_largest_files(self, min_size_mb=None, extension=None, directory=None, limit=10) -> dict:
        results = self.query_engine.find_largest_files(extension=extension, directory=directory, limit=limit)
        if min_size_mb is not None:
            min_bytes = int(min_size_mb * 1024 * 1024)
            results = [r for r in results if r.get("size_bytes", 0) >= min_bytes]
        return {"success": True, "data": results, "count": len(results)}


    def find_small_files(self, max_size_mb=None, extension=None, directory=None, limit=20) -> dict:
        results = self.query_engine.find_small_files(extension=extension, directory=directory, limit=limit)
        if max_size_mb is not None:
            min_bytes = int(max_size_mb * 1024 * 1024)
            results = [r for r in results if r.get("size_bytes", 0) >= min_bytes]
        return {"success": True, "data": results, "count": len(results)}

    def find_empty_files(self, directory=None) -> dict:
        results = self.query_engine.find_empty_files(directory=directory)
        return {"success": True, "data": results, "count": len(results)}

    def find_empty_directories(self) -> dict:
        results = self.query_engine.find_empty_directories()
        return {"success": True, "data": results, "count": len(results)}

    def get_extension_stats(self, directory=None) -> dict:
        results = self.query_engine.get_extension_stats(directory=directory)
        return {"success": True, "data": results, "count": len(results)}

    def find_duplicate_names(self, extension=None, min_count=2, name=None) -> dict:
        results = self.query_engine.find_duplicate_names(extension=extension, min_count=min_count)
        if name:
            results = [r for r in results if name.lower() in r["name"].lower()]
        return {"success": True, "data": results, "count": len(results)}

    def compare_files(self, file_path_1: str, file_path_2: str) -> dict:
        import hashlib
        p1, p2 = Path(file_path_1), Path(file_path_2)
        if not p1.exists():
            return {"success": False, "error": f"Bulunamadı: {file_path_1}"}
        if not p2.exists():
            return {"success": False, "error": f"Bulunamadı: {file_path_2}"}
        s1, s2 = p1.stat().st_size, p2.stat().st_size
        if s1 != s2:
            return {"success": True, "data": {"identical": False, "reason": f"Boyut farklı: {s1} vs {s2}"}}
        h1 = hashlib.md5(p1.read_bytes()).hexdigest()
        h2 = hashlib.md5(p2.read_bytes()).hexdigest()
        identical = h1 == h2
        return {
            "success": True,
            "data": {"identical": identical, "reason": "Aynı dosya" if identical else "İçerik farklı",
                     "hash_1": h1, "hash_2": h2},
            "message": "Dosyalar aynı" if identical else "Dosyalar farklı",
        }

    def get_directory_tree(self, dir_path: str, max_depth=3) -> dict:
        dir_path = self._resolve_dir_path(dir_path)
        if not dir_path:
            return {"success": False, "error": "Dizin bulunamadı"}
        # Tam yol değilse DB'den bul
        if not Path(dir_path).is_absolute():
            dirs = self.query_engine.search_directories(name=dir_path, limit=1)
            if dirs:
                dir_path = dirs[0]["full_path"]
            else:
                return {"success": False, "error": f"Dizin bulunamadı: {dir_path}"}
        result = self.query_engine.get_directory_tree(dir_path, max_depth=max_depth)
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