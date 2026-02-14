"""
Dosya sistemi indeksleyici.
Config'e göre dosya sistemini tarar ve DB'ye yazar.
Watchdog ile anlık değişiklikleri takip eder.
"""

import os
import json
import time
import fnmatch
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.indexing.Database import Database

logger = logging.getLogger(__name__)


class FileIndexer:
    """Dosya sistemi tarayıcı ve indeksleyici."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        idx_config = config["indexing"]
        self.scan_roots = [Path(p) for p in idx_config["scan_roots"]]
        self.allowed_extensions = set(idx_config.get("allowed_extensions", []))
        self.blacklist_dirs = set(idx_config.get("blacklist_dirs", []))
        self.blacklist_patterns = idx_config.get("blacklist_patterns", [])
        self.max_depth = idx_config.get("max_depth", 15)
        self.index_hidden = idx_config.get("index_hidden_files", False)
        self.follow_symlinks = idx_config.get("follow_symlinks", False)

        self.db = Database(config_path)

        # İndeksleme sayaçları
        self._stats = {"dirs": 0, "files": 0, "skipped": 0, "errors": 0}

    # ================================================================
    # FILTRELEME
    # ================================================================

    def _is_blacklisted_dir(self, dir_name: str, full_path: str) -> bool:
        """Dizin kara listede mi kontrol et."""
        # Direkt isim kontrolü
        if dir_name in self.blacklist_dirs:
            return True
        # Path içinde kara liste dizini var mı
        path_str = full_path.replace("\\", "/")
        for bl in self.blacklist_dirs:
            if f"/{bl}/" in path_str or path_str.endswith(f"/{bl}"):
                return True
        return False

    def _is_blacklisted_file(self, file_name: str) -> bool:
        """Dosya kara liste pattern'ına uyuyor mu."""
        name_lower = file_name.lower()
        for pattern in self.blacklist_patterns:
            if fnmatch.fnmatch(name_lower, pattern.lower()):
                return True
        return False

    def _is_hidden(self, name: str) -> bool:
        """Gizli dosya/klasör mü."""
        return name.startswith(".")

    def _should_index_file(self, file_name: str, extension: str) -> bool:
        """Dosya indekslenmeli mi."""
        if self._is_blacklisted_file(file_name):
            return False
        if not self.index_hidden and self._is_hidden(file_name):
            return False
        # Uzantı filtresi - boşsa tüm dosyaları al
        if self.allowed_extensions and extension.lower() not in self.allowed_extensions:
            return False
        return True

    # ================================================================
    # TAM TARAMA (FULL SCAN)
    # ================================================================

    def full_scan(self):
        """
        Tüm dosya sistemini baştan tarar.
        Mevcut kayıtları temizler ve yeniden yazar.
        """
        start_time = time.time()
        self._stats = {"dirs": 0, "files": 0, "skipped": 0, "errors": 0}

        logger.info("Tam tarama başlıyor...")

        with self.db.connect() as conn:
            # Temiz başlangıç
            conn.execute("DELETE FROM files")
            conn.execute("DELETE FROM directories")

            # FTS tablolarını da temizle
            conn.execute("DELETE FROM files_fts")
            conn.execute("DELETE FROM dirs_fts")

            for root_path in self.scan_roots:
                if root_path.exists():
                    logger.info(f"Taranıyor: {root_path}")
                    self._scan_directory(conn, root_path, parent_id=None, depth=0)
                else:
                    logger.warning(f"Kök dizin bulunamadı: {root_path}")

            conn.commit()

        elapsed = time.time() - start_time
        self.db.set_meta("last_full_scan", datetime.now().isoformat())
        self.db.set_meta("last_scan_duration_sec", str(round(elapsed, 2)))

        logger.info(
            f"Tarama tamamlandı: {elapsed:.1f}s | "
            f"Dizin: {self._stats['dirs']} | "
            f"Dosya: {self._stats['files']} | "
            f"Atlanan: {self._stats['skipped']} | "
            f"Hata: {self._stats['errors']}"
        )

        return self._stats

    def _scan_directory(self, conn, dir_path: Path, parent_id: Optional[int], depth: int):
        """Tek bir dizini recursive tarar."""
        if depth > self.max_depth:
            return

        dir_name = dir_path.name or str(dir_path)  # root için (C:/ gibi)
        full_path_str = str(dir_path)

        # Kara liste kontrolü
        if self._is_blacklisted_dir(dir_name, full_path_str):
            self._stats["skipped"] += 1
            return

        # Gizli klasör kontrolü
        if not self.index_hidden and self._is_hidden(dir_name) and parent_id is not None:
            self._stats["skipped"] += 1
            return

        # Dizini DB'ye yaz
        try:
            stat = dir_path.stat(follow_symlinks=self.follow_symlinks)
            cur = conn.execute(
                """INSERT OR IGNORE INTO directories
                   (name, full_path, parent_id, depth, created_at, modified_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    dir_name,
                    full_path_str,
                    parent_id,
                    depth,
                    stat.st_ctime,
                    stat.st_mtime,
                )
            )
            dir_id = cur.lastrowid

            # IGNORE durumunda lastrowid 0 döner, mevcut ID'yi al
            if dir_id == 0:
                row = conn.execute(
                    "SELECT id FROM directories WHERE full_path = ?",
                    (full_path_str,)
                ).fetchone()
                dir_id = row["id"] if row else None
                if not dir_id:
                    return

            self._stats["dirs"] += 1

        except (PermissionError, OSError) as e:
            self._stats["errors"] += 1
            logger.debug(f"Dizin erişim hatası: {dir_path} -> {e}")
            return

        # Dizin içeriğini tara
        try:
            entries = list(dir_path.iterdir())
        except (PermissionError, OSError) as e:
            self._stats["errors"] += 1
            logger.debug(f"Dizin okuma hatası: {dir_path} -> {e}")
            return

        # Batch insert için dosyaları topla
        file_batch = []

        for entry in entries:
            try:
                if entry.is_symlink() and not self.follow_symlinks:
                    continue

                if entry.is_dir():
                    self._scan_directory(conn, entry, parent_id=dir_id, depth=depth + 1)

                elif entry.is_file():
                    ext = entry.suffix.lower()
                    file_name = entry.stem  # uzantısız ad

                    if not self._should_index_file(entry.name, ext):
                        self._stats["skipped"] += 1
                        continue

                    try:
                        fstat = entry.stat(follow_symlinks=self.follow_symlinks)
                        file_batch.append((
                            file_name,
                            ext,
                            str(entry),
                            dir_id,
                            fstat.st_size,
                            fstat.st_ctime,
                            fstat.st_mtime,
                            1 if self._is_hidden(entry.name) else 0
                        ))
                    except (PermissionError, OSError):
                        self._stats["errors"] += 1

            except (PermissionError, OSError) as e:
                self._stats["errors"] += 1
                logger.debug(f"Giriş hatası: {entry} -> {e}")

        # Batch insert - çok daha hızlı
        if file_batch:
            conn.executemany(
                """INSERT OR IGNORE INTO files
                   (name, extension, full_path, directory_id, size_bytes,
                    created_at, modified_at, is_hidden)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                file_batch
            )
            self._stats["files"] += len(file_batch)

        # Belirli aralıklarla commit (bellek yönetimi)
        if self._stats["files"] % 10000 == 0 and self._stats["files"] > 0:
            conn.commit()
            logger.info(f"İlerleme: {self._stats['files']} dosya indekslendi...")

    # ================================================================
    # INCREMENTAL GÜNCELLEME
    # ================================================================

    def update_file(self, file_path: str):
        """Tek dosyayı güncelle veya ekle."""
        path = Path(file_path)
        if not path.exists():
            self.remove_file(file_path)
            return

        if not path.is_file():
            return

        ext = path.suffix.lower()
        if not self._should_index_file(path.name, ext):
            return

        # Önce parent dizinin DB'de olduğundan emin ol
        dir_id = self._ensure_directory(path.parent)
        if not dir_id:
            return

        try:
            stat = path.stat()
            with self.db.connect() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO files
                       (name, extension, full_path, directory_id, size_bytes,
                        created_at, modified_at, is_hidden)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        path.stem,
                        ext,
                        str(path),
                        dir_id,
                        stat.st_size,
                        stat.st_ctime,
                        stat.st_mtime,
                        1 if self._is_hidden(path.name) else 0,
                    )
                )
        except (PermissionError, OSError) as e:
            logger.error(f"Dosya güncelleme hatası: {file_path} -> {e}")

    def remove_file(self, file_path: str):
        """Dosyayı DB'den sil."""
        with self.db.connect() as conn:
            conn.execute("DELETE FROM files WHERE full_path = ?", (file_path,))

    def update_directory(self, dir_path: str):
        """Dizini güncelle veya ekle."""
        path = Path(dir_path)
        if not path.exists():
            self.remove_directory(dir_path)
            return
        self._ensure_directory(path)

    def remove_directory(self, dir_path: str):
        """Dizini ve altındaki her şeyi DB'den sil."""
        with self.db.connect() as conn:
            # Önce dizin ID'sini bul
            row = conn.execute(
                "SELECT id FROM directories WHERE full_path = ?", (dir_path,)
            ).fetchone()

            if row:
                dir_id = row["id"]
                # Alt dizinleri recursive bul (CTE)
                sub_dirs = conn.execute("""
                    WITH RECURSIVE sub AS (
                        SELECT id FROM directories WHERE id = ?
                        UNION ALL
                        SELECT d.id FROM directories d JOIN sub s ON d.parent_id = s.id
                    )
                    SELECT id FROM sub
                """, (dir_id,)).fetchall()

                dir_ids = [r["id"] for r in sub_dirs]

                if dir_ids:
                    placeholders = ",".join("?" * len(dir_ids))
                    conn.execute(f"DELETE FROM files WHERE directory_id IN ({placeholders})", dir_ids)
                    conn.execute(f"DELETE FROM directories WHERE id IN ({placeholders})", dir_ids)

    def _ensure_directory(self, dir_path: Path) -> Optional[int]:
        """Dizinin DB'de var olmasını garanti et, yoksa oluştur."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id FROM directories WHERE full_path = ?", (str(dir_path),)
            ).fetchone()

            if row:
                return row["id"]

            # Parent'ı recursive oluştur
            parent_id = None
            if dir_path.parent != dir_path:
                parent_id = self._ensure_directory(dir_path.parent)

            try:
                stat = dir_path.stat()
                depth = len(dir_path.parts) - 1
                cur = conn.execute(
                    """INSERT OR IGNORE INTO directories
                       (name, full_path, parent_id, depth, created_at, modified_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        dir_path.name or str(dir_path),
                        str(dir_path),
                        parent_id,
                        depth,
                        stat.st_ctime,
                        stat.st_mtime,
                    )
                )
                return cur.lastrowid or conn.execute(
                    "SELECT id FROM directories WHERE full_path = ?",
                    (str(dir_path),)
                ).fetchone()["id"]
            except (PermissionError, OSError):
                return None