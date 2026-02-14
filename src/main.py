

"""
Smart Terminal - Ana Giris Noktasi

Kullanim:
    python main.py index          # Dosya sistemini indeksle
    python main.py index --force  # Yeniden indeksle
    python main.py run            # Uygulamayi baslat
    python main.py stats          # Indeks istatistikleri
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


def cmd_index():
    indexer = FileIndexer(CONFIG)
    stats = indexer.full_scan()
    logging.info(f"Tamamlandi: {stats['files']} dosya, {stats['dirs']} dizin")


def cmd_run():
    db = Database(CONFIG)
    if db.get_stats()["total_files"] == 0:
        print("Indeks bos! Once calistirin: python main.py index")
        return

    try:
        indexer = FileIndexer(CONFIG)
        from indexing.FileWatcher import FileWatcher
        watcher = FileWatcher(indexer, CONFIG)
        watcher.start()
    except ImportError:
        logging.warning("watchdog yüklü değil, dosya izleme devre dışı.")

    formatter = OutputFormatter()

    brain = Brain(CONFIG)
    brain.initialize()

    print("\nSmart Terminal hazir. Cikmak icin 'exit' yazin.\n")

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

    print("Cikis yapildi.")


def cmd_stats():
    db = Database(CONFIG)
    stats = db.get_stats()
    print(f"\n  Toplam dosya:   {stats['total_files']:,}")
    print(f"  Toplam dizin:   {stats['total_directories']:,}")
    print(f"  Toplam boyut:   {stats['total_size_gb']} GB")
    print(f"  Son tarama:     {stats['last_full_scan'] or 'henuz yapilmadi'}\n")


if __name__ == "__main__":
    main()