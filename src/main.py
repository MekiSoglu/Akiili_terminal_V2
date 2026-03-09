"""
Smart Terminal v2 - Ana Giriş Noktası (DAG Tabanlı)

Kullanım:
    python main.py index          # Dosya sistemini indeksle
    python main.py index --force  # Yeniden indeksle
    python main.py run            # Uygulamayı başlat
    python main.py stats          # İndeks istatistikleri
"""

import sys
import logging

from src.OutputFormat.file_operations import OutputFormatter
from src.indexing.Database import Database
from src.indexing.FileIndexer import FileIndexer
from src.llm.Brain import Brain

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

CONFIG = "config.json"


def main():
    commands = {
        "index": cmd_index,
        "run": cmd_run,
        "stats": cmd_stats,
    }

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(__doc__)
        return

    commands[sys.argv[1]]()


def _check_admin():
    """Windows yönetici kontrolü."""
    try:
        import ctypes

        shell32 = getattr(ctypes, "windll").shell32
        if not shell32.IsUserAnAdmin():
            print("⚠ Yönetici modunda değilsiniz. Bazı ağ işlemleri çalışmayabilir.")
            print("  Tam yetki için terminali yönetici olarak başlatın.\n")
    except Exception:
        pass


def cmd_index():
    indexer = FileIndexer(CONFIG)
    stats = indexer.full_scan()
    logging.info(f"Tamamlandı: {stats['files']} dosya, {stats['dirs']} dizin")


def cmd_run():
    db = Database(CONFIG)
    if db.get_stats()["total_files"] == 0:
        print("İndeks boş! Önce çalıştırın: python main.py index")
        return

    _check_admin()

    # Dosya izleyici
    try:
        indexer = FileIndexer(CONFIG)
        from indexing.FileWatcher import FileWatcher

        watcher = FileWatcher(indexer, CONFIG)
        watcher.start()
    except ImportError:
        logging.warning("watchdog yüklü değil, dosya izleme devre dışı.")

    # Çıktı formatlayıcı
    formatter = OutputFormatter()

    # Brain v2 — DAG tabanlı
    brain = Brain(CONFIG)
    brain.initialize()  # Modüller + ChromaDB + embedding model yüklenir

    print("\nSmart Terminal v2 hazır.")
    print("   Çıkmak için 'exit' yazın.\n")

    while True:
        try:
            user_input = input(">>> ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            break

        result = brain.process(user_input)
        formatter.display(result)

    print("Çıkış yapıldı.")


def cmd_stats():
    db = Database(CONFIG)
    stats = db.get_stats()
    print(f"\n  Toplam dosya:   {stats['total_files']:,}")
    print(f"  Toplam dizin:   {stats['total_directories']:,}")
    print(f"  Toplam boyut:   {stats['total_size_gb']} GB")
    print(f"  Son tarama:     {stats['last_full_scan'] or 'henüz yapılmadı'}\n")


if __name__ == "__main__":
    main()
