import sys
import os
import json
import logging
from pathlib import Path

# ÖNCE path ayarla
ROOT = (
    Path(__file__).resolve().parent.parent.parent
)  # indexing → src → akkil_teminal_v2
if not (ROOT / "config.json").exists():
    ROOT = Path(r"C:\Users\EXCALIBUR\Desktop\akkil_teminal_v2")

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
os.chdir(str(ROOT))

# SONRA import et
from src.indexing.FileIndexer import FileIndexer
from src.indexing.FileQueryEngine import FileQueryEngine

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def update_config_blacklist():
    """config.json'a venv ve site-packages blacklist ekle."""
    config_path = ROOT / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    bl = set(config["indexing"].get("blacklist_dirs", []))
    new_entries = {
        "venv",
        ".venv",
        "env",
        ".env",
        "site-packages",
        "__pycache__",
        "node_modules",
        ".git",
        "data",
        "data/",
        ".idea",
        ".vscode",
        "dist",
        "build",
        "egg-info",
    }

    added = new_entries - bl
    if added:
        config["indexing"]["blacklist_dirs"] = sorted(bl | new_entries)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"Blacklist guncellendi, eklenen: {added}")
    else:
        logger.info("Blacklist zaten guncel")


def reindex():
    """DB'yi sifirla ve yeniden tara."""

    indexer = FileIndexer("config.json")

    # Mevcut istatistikleri goster
    stats_before = indexer.db.get_stats()
    logger.info(
        f"Mevcut DB: {stats_before['total_files']} dosya, "
        f"{stats_before['total_directories']} dizin"
    )

    # Tam tarama (DELETE + INSERT)
    logger.info("=" * 50)
    logger.info("TAM TARAMA BASLIYOR...")
    logger.info("=" * 50)

    stats = indexer.full_scan()

    # Sonuc
    stats_after = indexer.db.get_stats()
    logger.info("=" * 50)
    logger.info("TAMAMLANDI:")
    logger.info(f"  Dizin:   {stats['dirs']}")
    logger.info(f"  Dosya:   {stats['files']}")
    logger.info(f"  Atlanan: {stats['skipped']}")
    logger.info(f"  Hata:    {stats['errors']}")
    logger.info(f"  DB:      {stats_after['total_size_gb']} GB")
    logger.info("=" * 50)

    # Kontrol: transform_test dosyalari var mi?
    qe = FileQueryEngine("config.json")

    print("\n--- KONTROL: transform_test dosyalari ---")
    for name in ["test_resim", "test_Wav", "test_exel", "test"]:
        r = qe.search_files(name=name, limit=3)
        if r:
            for f in r:
                print(f"  {f['name']}{f['extension']}  ->  {f['full_path']}")
        else:
            print(f"  {name}: BULUNAMADI")


if __name__ == "__main__":
    print("1) Config blacklist guncelleniyor...")
    update_config_blacklist()

    print("\n2) DB yeniden indeksleniyor...")
    reindex()
