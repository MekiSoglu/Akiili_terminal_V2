"""
Dosya sistemi değişiklik izleyici.
Watchdog kütüphanesi ile dosya ekleme/silme/taşıma olaylarını yakalar.
pip install watchdog gerektirir.
"""

import json
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdog kütüphanesi bulunamadı. pip install watchdog")


def _should_ignore(path: str) -> bool:
    """DB dosyaları ve blacklist'tekileri yoksay."""
    ignore_patterns = ["file_index.db", ".db-wal", ".db-shm"]
    for pattern in ignore_patterns:
        if pattern in path:
            return True
    return False


class _IndexEventHandler(FileSystemEventHandler):
    """Dosya sistemi olaylarını yakalar ve indexer'a iletir."""

    def __init__(self, indexer, debounce_sec: float = 2.0):
        super().__init__()
        self.indexer = indexer
        self.debounce_sec = debounce_sec
        self._pending = {}  # path -> timestamp (debounce için)

    def _should_ignore(self, path: str) -> bool:
        """DB dosyaları ve blacklist'tekileri yoksay."""
        ignore_patterns = ["file_index.db", ".db-wal", ".db-shm"]
        for pattern in ignore_patterns:
            if pattern in path:
                return True
        return False

    def _debounce(self, path: str) -> bool:
        """Aynı dosya için çok sık tetiklenmeyi önle."""
        now = time.time()
        last = self._pending.get(path, 0)
        if now - last < self.debounce_sec:
            return False
        self._pending[path] = now
        return True

    def on_created(self, event: FileSystemEvent):
        if self._should_ignore(event.src_path): return
        logger.info(f"WATCHDOG CREATED: {event.src_path}, is_dir={event.is_directory}")
        if not self._debounce(event.src_path):
            return
        try:
            if event.is_directory:
                self.indexer.update_directory(event.src_path)
            else:
                self.indexer.update_file(event.src_path)
            logger.debug(f"Eklendi: {event.src_path}")
        except Exception as e:
            logger.error(f"on_created hatası: {e}")

    def on_deleted(self, event):
        if self._should_ignore(event.src_path): return
        logger.info(f"WATCHDOG DELETED: {event.src_path}")
        if not self._debounce(event.src_path): return
        try:
            self.indexer.remove_file(event.src_path)
            self.indexer.remove_directory(event.src_path)
        except Exception as e:
            logger.error(f"on_deleted: {e}")

    def on_modified(self, event: FileSystemEvent):
        if self._should_ignore(event.src_path): return
        if event.is_directory:
            return  # dizin modification'ı genelde gereksiz
        if not self._debounce(event.src_path):
            return
        try:
            self.indexer.update_file(event.src_path)
            logger.debug(f"Güncellendi: {event.src_path}")
        except Exception as e:
            logger.error(f"on_modified hatası: {e}")

    def on_moved(self, event: FileSystemEvent):
        if self._should_ignore(event.src_path): return
        try:
            # Eski konumdan sil
            if event.is_directory:
                self.indexer.remove_directory(event.src_path)
                self.indexer.update_directory(event.dest_path)
            else:
                self.indexer.remove_file(event.src_path)
                self.indexer.update_file(event.dest_path)
            logger.debug(f"Taşındı: {event.src_path} -> {event.dest_path}")
        except Exception as e:
            logger.error(f"on_moved hatası: {e}")


class FileWatcher:
    """Dosya sistemi değişiklik izleyici servisi."""

    def __init__(self, indexer, config_path: str = "config.json"):
        if not WATCHDOG_AVAILABLE:
            raise ImportError("watchdog kütüphanesi gerekli: pip install watchdog")

        self.indexer = indexer

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        watcher_config = config.get("watcher", {})
        idx_config = config["indexing"]

        self.debounce_sec = watcher_config.get("debounce_seconds", 2)
        self.scan_roots = [Path(p) for p in idx_config["scan_roots"]]

        self._observer: Optional[Observer] = None

    def start(self):
        """İzlemeyi başlat."""
        handler = _IndexEventHandler(self.indexer, self.debounce_sec)
        self._observer = Observer()

        for root in self.scan_roots:
            if root.exists():
                self._observer.schedule(handler, str(root), recursive=True)
                logger.info(f"İzleniyor: {root}")
            else:
                logger.warning(f"İzlenecek dizin bulunamadı: {root}")

        self._observer.start()
        logger.info("Dosya izleyici başlatıldı.")

    def stop(self):
        """İzlemeyi durdur."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            logger.info("Dosya izleyici durduruldu.")

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()