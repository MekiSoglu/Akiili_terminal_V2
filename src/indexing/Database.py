"""
Veritabanı şema tanımı ve bağlantı yöneticisi.
SQLite + FTS5 ile dosya sistemi indeksleme altyapısı.
"""

import sqlite3
import json
import os
from pathlib import Path
from contextlib import contextmanager
from typing import Optional


class Database:
    """SQLite bağlantı ve şema yöneticisi."""

    def __init__(self, config_path: str = "config.json"):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        db_config = config["database"]
        self.db_path = Path(db_config["path"])
        self.journal_mode = db_config.get("journal_mode", "WAL")
        self.cache_size_mb = db_config.get("cache_size_mb", 64)
        self.busy_timeout = db_config.get("busy_timeout_ms", 5000)

        # db klasörünü oluştur
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Optimize edilmiş SQLite bağlantısı oluşturur."""
        conn = sqlite3.connect(str(self.db_path), timeout=self.busy_timeout / 1000)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute(f"PRAGMA cache_size = -{self.cache_size_mb * 1024}")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA mmap_size = 268435456")  # 256MB mmap
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def connect(self):
        """Context manager ile güvenli bağlantı."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Tablo, indeks ve FTS5 yapısını oluşturur."""
        with self.connect() as conn:
            cur = conn.cursor()

            # ============================================================
            # ANA TABLOLAR
            # ============================================================

            # Dizinler tablosu - ağaç yapısı (parent_id ile)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS directories (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT    NOT NULL,
                    full_path   TEXT    NOT NULL UNIQUE,
                    parent_id   INTEGER,
                    depth       INTEGER NOT NULL DEFAULT 0,
                    created_at  REAL,
                    modified_at REAL,
                    FOREIGN KEY (parent_id) REFERENCES directories(id) ON DELETE CASCADE
                )
            """)

            # Dosyalar tablosu
            cur.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    name         TEXT    NOT NULL,
                    extension    TEXT    NOT NULL DEFAULT '',
                    full_path    TEXT    NOT NULL UNIQUE,
                    directory_id INTEGER NOT NULL,
                    size_bytes   INTEGER NOT NULL DEFAULT 0,
                    created_at   REAL,
                    modified_at  REAL,
                    is_hidden    INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (directory_id) REFERENCES directories(id) ON DELETE CASCADE
                )
            """)

            # İndeksleme meta bilgisi - son tarama zamanı vs.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS index_meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # ============================================================
            # PERFORMANS İNDEKSLERİ
            # ============================================================

            # files indeksleri
            cur.execute("CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_files_dir_id ON files(directory_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_files_modified ON files(modified_at)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_files_size ON files(size_bytes)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_files_name ON files(name)")
            # Composite indeksler - sık kullanılan sorgu kombinasyonları
            cur.execute("CREATE INDEX IF NOT EXISTS idx_files_ext_modified ON files(extension, modified_at)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_files_dir_ext ON files(directory_id, extension)")

            # directories indeksleri
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dirs_parent ON directories(parent_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dirs_name ON directories(name)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dirs_depth ON directories(depth)")

            # ============================================================
            # FTS5 - TAM METİN ARAMA
            # ============================================================

            # Dosya adı full-text arama
            cur.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                    name,
                    full_path,
                    content=files,
                    content_rowid=id,
                    tokenize='unicode61 remove_diacritics 2'
                )
            """)

            # Dizin adı full-text arama
            cur.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS dirs_fts USING fts5(
                    name,
                    full_path,
                    content=directories,
                    content_rowid=id,
                    tokenize='unicode61 remove_diacritics 2'
                )
            """)

            # ============================================================
            # FTS5 TRIGGER'LARI - otomatik senkronizasyon
            # ============================================================

            # files tablosu değiştiğinde FTS'i güncelle
            cur.executescript("""
                CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
                    INSERT INTO files_fts(rowid, name, full_path)
                    VALUES (new.id, new.name, new.full_path);
                END;

                CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
                    INSERT INTO files_fts(files_fts, rowid, name, full_path)
                    VALUES ('delete', old.id, old.name, old.full_path);
                END;

                CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE ON files BEGIN
                    INSERT INTO files_fts(files_fts, rowid, name, full_path)
                    VALUES ('delete', old.id, old.name, old.full_path);
                    INSERT INTO files_fts(rowid, name, full_path)
                    VALUES (new.id, new.name, new.full_path);
                END;

                CREATE TRIGGER IF NOT EXISTS dirs_ai AFTER INSERT ON directories BEGIN
                    INSERT INTO dirs_fts(rowid, name, full_path)
                    VALUES (new.id, new.name, new.full_path);
                END;

                CREATE TRIGGER IF NOT EXISTS dirs_ad AFTER DELETE ON directories BEGIN
                    INSERT INTO dirs_fts(dirs_fts, rowid, name, full_path)
                    VALUES ('delete', old.id, old.name, old.full_path);
                END;

                CREATE TRIGGER IF NOT EXISTS dirs_au AFTER UPDATE ON directories BEGIN
                    INSERT INTO dirs_fts(dirs_fts, rowid, name, full_path)
                    VALUES ('delete', old.id, old.name, old.full_path);
                    INSERT INTO dirs_fts(rowid, name, full_path)
                    VALUES (new.id, new.name, new.full_path);
                END;
            """)

            conn.commit()

    def get_meta(self, key: str) -> Optional[str]:
        """Meta bilgi oku."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value FROM index_meta WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None

    def set_meta(self, key: str, value: str):
        """Meta bilgi yaz/güncelle."""
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
                (key, value)
            )

    def get_stats(self) -> dict:
        """DB istatistikleri - toplam dosya, dizin sayısı vs."""
        with self.connect() as conn:
            file_count = conn.execute("SELECT COUNT(*) as c FROM files").fetchone()["c"]
            dir_count = conn.execute("SELECT COUNT(*) as c FROM directories").fetchone()["c"]
            total_size = conn.execute("SELECT COALESCE(SUM(size_bytes), 0) as s FROM files").fetchone()["s"]
            last_scan = self.get_meta("last_full_scan")

            return {
                "total_files": file_count,
                "total_directories": dir_count,
                "total_size_bytes": total_size,
                "total_size_gb": round(total_size / (1024**3), 2),
                "last_full_scan": last_scan
            }