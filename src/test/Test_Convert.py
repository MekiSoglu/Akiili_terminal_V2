"""
Dosya Donusturme LLM Entegrasyon Testi

Brain.process() uzerinden gercek LLM planlamasi ile convert_file ozelligini test eder.
Test dosyalarinin tam yolu prompt'a verilir (DB indeksleme bagimsizhgi icin).

Kullanim:
    python src/test/Test_Convert.py
"""

import os
import sys
import time
import logging
from pathlib import Path

_THIS = Path(__file__).resolve()
for _up in [_THIS.parent.parent, _THIS.parent.parent.parent]:
    if (_up / "config.json").exists():
        ROOT = _up
        break
else:
    ROOT = _THIS.parent
    while ROOT.name and ROOT.name != "akkil_teminal_v2":
        ROOT = ROOT.parent
    if not ROOT.name:
        ROOT = _THIS.parent.parent

for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.chdir(str(ROOT))
CONFIG_PATH = str(ROOT / "config.json")

try:
    from src.llm.Brain import Brain
except (ModuleNotFoundError, ImportError):
    from llm.Brain import Brain


class ConvertLLMTestRunner:
    """LLM uzerinden convert_file testleri."""

    SOURCE_DIR = Path(r"C:\Users\EXCALIBUR\Desktop\projeler\transform_test")

    FILES = {
        "txt": "test.txt",
        "xlsx": "test_exel.xlsx",
        "png": "test_resim.png",
        "wav": "test_Wav.wav",
    }

    def __init__(self):
        self.brain = None
        self.results = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []
        self.tests = []

    def _build_tests(self):
        """Tam yollarla test prompt'larini olustur."""
        d = str(self.SOURCE_DIR)
        txt = f"{d}\\test.txt"
        png = f"{d}\\test_resim.png"
        wav = f"{d}\\test_Wav.wav"
        xlsx = f"{d}\\test_exel.xlsx"

        self.tests = [
            # GRUP 1: Basit tek adim — tam yol
            (
                "TXT->PDF",
                f"{txt} dosyasini PDF formatina donustur",
                "convert_file",
                True,
            ),
            ("PNG->JPG", f"{png} dosyasini jpg formatina cevir", "convert_file", True),
            ("WAV->MP3", f"{wav} dosyasini mp3 olarak donustur", "convert_file", True),
            ("XLSX->CSV", f"{xlsx} dosyasini CSV ye cevir", "convert_file", True),
            (
                "TXT->DOCX",
                f"{txt} dosyasini Word belgesine donustur",
                "convert_file",
                True,
            ),
            ("TXT->HTML", f"{txt} dosyasini HTML e cevir", "convert_file", True),
            # GRUP 2: Kalite parametreli
            (
                "PNG->JPG kaliteli",
                f"{png} dosyasini jpg ye cevir kalite 95 olsun",
                "convert_file",
                True,
            ),
            (
                "WAV->MP3 320k",
                f"{wav} dosyasini 320 bitrate mp3 yap",
                "convert_file",
                True,
            ),
            # GRUP 3: Zincirleme
            (
                "Donustur + Yaz",
                f"{txt} dosyasini PDF yap ve sonucu rapor.txt ye yaz",
                "convert_file",
                True,
            ),
        ]

    def setup(self):
        print("=" * 65)
        print("  DOSYA DONUSTURME - LLM ENTEGRASYON TESTI")
        print("=" * 65)

        if not self.SOURCE_DIR.exists():
            print(f"\n  Kaynak dizin bulunamadi: {self.SOURCE_DIR}")
            return False

        missing = [
            n for k, n in self.FILES.items() if not (self.SOURCE_DIR / n).exists()
        ]
        if missing:
            print(f"\n  Eksik dosyalar: {', '.join(missing)}")
            return False

        print(f"  Kaynak: {self.SOURCE_DIR}")
        for key, name in self.FILES.items():
            size = (self.SOURCE_DIR / name).stat().st_size
            print(f"    {name:<25} {self._human_size(size)}")

        self._build_tests()

        print("\n  Brain baslatiliyor...")
        try:
            self.brain = Brain(config_path=CONFIG_PATH)
            self.brain.initialize()
            self.brain._ask_user_confirmation = lambda *a, **k: True
            print(f"  Brain hazir — {len(self.tests)} test\n")
            return True
        except Exception as e:
            print(f"  Brain baslatilamadi: {e}")
            return False

    def run_test(self, name, prompt, expected_tool, expect_success=True):
        print(f"\n{'=' * 65}")
        print(f"  Test: {name}")
        print(f'  Prompt: "{prompt}"')
        print(f"{'=' * 65}")

        start = time.time()

        try:
            result = self.brain.process(prompt)
            elapsed = time.time() - start

            success = result.success if result else False
            tools_used = []
            if result and result.steps:
                tools_used = [s.tool_name for s in result.steps]

            used_convert = expected_tool in tools_used

            convert_step_ok = False
            if result and result.steps:
                for step in result.steps:
                    if step.tool_name == expected_tool:
                        convert_step_ok = step.success
                        break

            print("\n  Sonuc:")
            print(f"     Sure: {elapsed:.1f}s")
            print(f"     Araclar: {' -> '.join(tools_used) if tools_used else 'yok'}")
            print(f"     {expected_tool}: {'EVET' if used_convert else 'HAYIR'}")
            print(f"     Basari: {'EVET' if success else 'HAYIR'}")

            if success and expect_success and used_convert:
                print("\n  BASARILI")
                self.passed += 1
                self.results.append(("PASS", name, f"{elapsed:.1f}s"))
            elif used_convert and convert_step_ok and not success:
                print("\n  KISMI BASARI")
                self.passed += 1
                self.results.append(("PASS", name, f"Kismi - {elapsed:.1f}s"))
            else:
                error_msg = result.message if result else "Sonuc yok"
                if (
                    "kutuphane" in str(error_msg).lower()
                    or "ffmpeg" in str(error_msg).lower()
                ):
                    print(f"\n  ATLANDI - {str(error_msg)[:60]}")
                    self.skipped += 1
                    self.results.append(("SKIP", name, str(error_msg)[:60]))
                else:
                    print("\n  BASARISIZ")
                    print(f"     Hata: {str(error_msg)[:100]}")
                    if not used_convert:
                        print(f"     LLM {expected_tool} aracini secmedi!")
                    self.failed += 1
                    self.results.append(("FAIL", name, str(error_msg)[:80]))
                    self.errors.append((name, prompt, str(error_msg)))

        except Exception as e:
            elapsed = time.time() - start
            print(f"\n  EXCEPTION ({elapsed:.1f}s): {str(e)[:100]}")
            self.failed += 1
            self.results.append(("FAIL", name, f"Exception: {str(e)[:60]}"))
            self.errors.append((name, prompt, str(e)))

    def run_all(self):
        for name, prompt, expected_tool, expect_success in self.tests:
            self.run_test(name, prompt, expected_tool, expect_success)

    def print_summary(self):
        total = self.passed + self.failed + self.skipped

        print(f"\n{'=' * 65}")
        print(f"  GENEL SONUC: {self.passed}/{total} basarili", end="")
        if self.skipped:
            print(f" ({self.skipped} atlandi)", end="")
        if self.failed:
            print(f" - {self.failed} BASARISIZ", end="")
        print(f"\n{'=' * 65}")

        print(f"\n  {'Test':<25} {'Durum':<8} {'Detay'}")
        print(f"  {'-' * 55}")
        for status, name, detail in self.results:
            icon = {"PASS": "OK", "FAIL": "FAIL", "SKIP": "SKIP"}.get(status, "?")
            print(f"  {name:<25} {icon:<8} {detail}")

        if self.errors:
            print("\n  Hata detaylari:")
            for name, prompt, error in self.errors:
                print(f"\n     Test: {name}")
                print(f"     Hata: {error[:150]}")

        new_files = [
            f
            for f in self.SOURCE_DIR.iterdir()
            if f.is_file() and f.name not in self.FILES.values()
        ]
        if new_files:
            print("\n  Olusturulan dosyalar:")
            for f in sorted(new_files):
                print(f"     {f.name:<35} {self._human_size(f.stat().st_size)}")

    @staticmethod
    def _human_size(size_bytes):
        if size_bytes >= 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        elif size_bytes >= 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes} B"


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    runner = ConvertLLMTestRunner()
    if not runner.setup():
        sys.exit(1)
    runner.run_all()
    runner.print_summary()


if __name__ == "__main__":
    main()
