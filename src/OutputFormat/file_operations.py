"""
Çıktı Formatlayıcı - Terminal sonuçlarını okunabilir formatta gösterir.
Her araç tipi için özel format tanımlanabilir.
"""

import logging

logger = logging.getLogger(__name__)


class OutputFormatter:

    def display(self, result):
        if result.success:
            print(f"\n✓ {result.message}")
            for step in result.steps:
                self._format_step(step)
        else:
            print(f"\n✗ {result.message}")
            for step in result.steps:
                if not step.success:
                    print(f"  Adım {step.step_number}: {step.error}")

    def _format_step(self, step):
        r = step.result
        data = r.get("data", None)
        content = r.get("content", None)
        message = r.get("message", "")

        # Araç adına göre özel formatlayıcı varsa kullan
        formatter = getattr(self, f"_fmt_{step.tool_name}", None)
        if formatter and data is not None:
            formatter(data)
            return

        # Dosya içeriği
        if content:
            print(f"\n--- {message} ---")
            print(content)
            print("---")
            return

        # Liste sonuçları
        if isinstance(data, list) and data:
            self._fmt_list(data, step.tool_name)
            return

        # Dict içinde subdirs/files varsa
        if isinstance(data, dict):
            if "subdirs" in data or "files" in data:
                self._fmt_directory_contents(data)
                return
            # Genel dict bilgisi
            self._fmt_dict(data)
            return

        if message:
            print(f"  ✓ {message}")

    # ============================================================
    # ARAÇ BAZLI FORMATLAR
    # ============================================================

    def _fmt_get_directory_size(self, data):
        print(f"\n  📁 {data.get('directory', '')}")
        print(f"     Dosya sayısı:  {data.get('file_count', 0)}")
        print(f"     Toplam boyut:  {data.get('total_size_mb', 0)} MB ({data.get('total_size_gb', 0)} GB)")

    def _fmt_get_file_info(self, data):
        print(f"\n  📄 {data.get('name', '')}")
        print(f"     Yol:           {data.get('full_path', '')}")
        print(f"     Boyut:         {data.get('size_human', '')}")
        print(f"     Oluşturulma:   {data.get('created', '')}")
        print(f"     Değiştirilme:  {data.get('modified', '')}")

    def _fmt_search_directories(self, data):
        if isinstance(data, list):
            for d in data:
                print(f"\n  📁 {d.get('name', '')}")
                print(f"     Yol:           {d.get('full_path', '')}")
                print(f"     Dosya sayısı:  {d.get('file_count', 0)}")
                print(f"     Alt klasör:    {d.get('subdir_count', 0)}")

    # ============================================================
    # GENEL FORMATLAR
    # ============================================================

    def _fmt_list(self, data, tool_name):
        print(f"\n  {tool_name} ({len(data)} sonuç):")
        for item in data[:15]:
            name = f"{item.get('name', '')}{item.get('extension', '')}"
            size = item.get('size_human', '')
            path = item.get('full_path', '')
            print(f"    {name:<30} {size:<10} {path}")
        if len(data) > 15:
            print(f"    ... ve {len(data) - 15} sonuç daha")

    def _fmt_directory_contents(self, data):
        subdirs = data.get("subdirs", [])
        files = data.get("files", [])
        if subdirs:
            print(f"\n  Klasörler ({len(subdirs)}):")
            for d in subdirs:
                print(f"    📁 {d['name']:<25} ({d.get('file_count', 0)} dosya)")
        if files:
            print(f"\n  Dosyalar ({len(files)}):")
            for f in files[:15]:
                name = f"{f.get('name', '')}{f.get('extension', '')}"
                print(f"    📄 {name:<25} {f.get('size_human', '')}")

    def _fmt_dict(self, data):
        for key, value in data.items():
            print(f"     {key:<15} {value}")

    def _fmt_find_largest_files(self, data):
        if isinstance(data, list):
            print(f"\n  En büyük dosyalar ({len(data)} sonuç):")
            for item in data:
                name = f"{item.get('name', '')}{item.get('extension', '')}"
                print(f"\n    📄 {name}")
                print(f"       Yol:           {item.get('full_path', '')}")
                print(f"       Boyut:         {item.get('size_human', '')}")
                print(f"       Dizin:         {item.get('dir_path', '')}")
                print(f"       Değiştirilme:  {item.get('modified_at_human', '')}")
                print(f"       Oluşturulma:   {item.get('created_at_human', '')}")

    def _fmt_search_in_files(self, data):
        if isinstance(data, list):
            print(f"\n  Dosya içi arama ({len(data)} dosyada eşleşme):")
            for item in data:
                print(f"\n    📄 {item['name']} ({item['total_matches']} eşleşme)")
                for m in item['matches']:
                    print(f"       Satır {m['line']}: {m['text'][:80]}")

    def _fmt_count_lines_words(self, data):
        print(f"\n    📄 {data.get('file', '')}")
        print(f"       Satır:     {data.get('lines', 0)}")
        print(f"       Kelime:    {data.get('words', 0)}")
        print(f"       Karakter:  {data.get('characters', 0)}")

    def _fmt_get_extension_stats(self, data):
        if isinstance(data, list):
            print(f"\n  Uzantı İstatistikleri ({len(data)} uzantı):")
            print(f"    {'Uzantı':<15} {'Dosya':<10} {'Toplam':<12} {'Ortalama':<10}")
            print(f"    {'-' * 47}")
            for item in data[:20]:
                print(
                    f"    {item['extension']:<15} {item['file_count']:<10} {item['total_size_mb']:<12} {item['avg_size_mb']:<10}")

    def _fmt_find_duplicate_names(self, data):
        if isinstance(data, list):
            print(f"\n  Tekrar Eden Dosyalar ({len(data)} grup):")
            for item in data:
                print(f"\n    📄 {item['name']}{item['extension']} (x{item['count']})")
                for p in item['paths']:
                    print(f"       {p}")

    def _fmt_compare_files(self, data):
        print(f"\n    Sonuç: {data.get('reason', '')}")
        if data.get('hash_1'):
            print(f"    Hash 1: {data['hash_1']}")
            print(f"    Hash 2: {data['hash_2']}")

    def _fmt_find_empty_files(self, data):
        if isinstance(data, list):
            print(f"\n  Boş Dosyalar ({len(data)} adet):")
            for item in data:
                print(f"    📄 {item.get('name', '')}{item.get('extension', '')}  {item.get('full_path', '')}")

    def _fmt_find_empty_directories(self, data):
        if isinstance(data, list):
            print(f"\n  Boş Klasörler ({len(data)} adet):")
            for item in data:
                print(f"    📁 {item.get('name', '')}  {item.get('full_path', '')}")

    def _fmt_get_directory_tree(self, data):
        self._print_tree(data, "")

    def _print_tree(self, node, indent):
        icon = "📁" if node.get("children") is not None else "📄"
        fc = f" ({node.get('file_count', 0)} dosya)" if node.get('file_count', 0) > 0 else ""
        print(f"{indent}{icon} {node.get('name', '')}{fc}")
        for child in node.get("children", []):
            self._print_tree(child, indent + "    ")