"""
Dosya Sorgu Motoru (FileQueryEngine)

LLM'in araç olarak çağıracağı tüm dosya arama/sorgulama metotları.
Her metot basit parametreler alır ve sonuç döner.
LLM'in yapması gereken: kullanıcı niyetini okuyup doğru metodu
doğru parametrelerle çağırmak.

Kullanım yaklaşımı:
    LLM, kullanıcının doğal dildeki isteğini analiz eder
    ve bu sınıftaki uygun metodu uygun parametrelerle çağırır.

    Örn: "projedeki Python dosyalarını bul"
    -> search_files(name="proje", extension=".py")

    Örn: "son 3 günde değişen büyük dosyalar"
    -> find_recently_modified(days=3, min_size_mb=100)
"""

import time
from typing import Optional

from src.indexing.Database import Database


class FileQueryEngine:
    """
    Dosya sistemi sorgu motoru.
    Tüm metotlar dict listesi döner - LLM'in parse etmesi kolay.
    """

    def __init__(self, config_path: str = "config.json"):
        self.db = Database(config_path)

    # ================================================================
    # DOSYA ARAMA
    # ================================================================

    def search_files(
        self,
        name: Optional[str] = None,
        extension: Optional[str] = None,
        directory: Optional[str] = None,
        min_size_mb: Optional[float] = None,
        max_size_mb: Optional[float] = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Genel dosya arama. Tüm parametreler opsiyonel, kombine edilebilir.

        Args:
            name: Dosya adında aranacak metin (FTS5 ile fuzzy arama)
            extension: Dosya uzantısı (.py, .txt vs.)
            directory: Dizin adı veya yolu (içinde arama)
            min_size_mb: Minimum dosya boyutu (MB)
            max_size_mb: Maximum dosya boyutu (MB)
            limit: Maksimum sonuç sayısı

        Returns:
            Eşleşen dosyaların listesi
        """
        conditions = []
        params = []

        # FTS5 ile isim araması
        if name:
            conditions.append("(f.name LIKE ? OR f.id IN (SELECT rowid FROM files_fts WHERE files_fts MATCH ?))")
            params.extend([f"%{name}%", " ".join(f"{w}*" for w in name.strip().split())])

        # Uzantı filtresi
        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())

        # Dizin filtresi
        if directory:
            conditions.append("""
                f.directory_id IN (
                    SELECT d.id FROM directories d
                    WHERE d.full_path LIKE ? OR d.name LIKE ?
                )
            """)
            dir_pattern = f"%{directory}%"
            params.extend([dir_pattern, dir_pattern])

        # Boyut filtreleri
        if min_size_mb is not None:
            conditions.append("f.size_bytes >= ?")
            params.append(int(min_size_mb * 1024 * 1024))

        if max_size_mb is not None:
            conditions.append("f.size_bytes <= ?")
            params.append(int(max_size_mb * 1024 * 1024))

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, f.created_at, d.full_path as dir_path
            FROM files f
            JOIN directories d ON f.directory_id = d.id
            {where}
            ORDER BY f.modified_at DESC
            LIMIT ?
        """
        params.append(limit)

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._file_row_to_dict(r) for r in rows]

    def search_files_by_exact_name(self, name: str, extension: Optional[str] = None) -> list[dict]:
        """
        Tam dosya adıyla arama (case-insensitive).

        Args:
            name: Tam dosya adı (uzantısız)
            extension: Opsiyonel uzantı filtresi
        """
        conditions = ["LOWER(f.name) = LOWER(?)"]
        params = [name]

        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())

        where = " AND ".join(conditions)

        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, f.created_at, d.full_path as dir_path
            FROM files f
            JOIN directories d ON f.directory_id = d.id
            WHERE {where}
            ORDER BY f.modified_at DESC
        """

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._file_row_to_dict(r) for r in rows]

    # ================================================================
    # DİZİN ARAMA
    # ================================================================

    def search_directories(
        self,
        name: Optional[str] = None,
        parent_path: Optional[str] = None,
        min_depth: Optional[int] = None,
        max_depth: Optional[int] = None,
        limit: int = 30,
    ) -> list[dict]:
        """
        Dizin arama.

        Args:
            name: Dizin adında aranacak metin (FTS5 fuzzy)
            parent_path: Üst dizin yolu (altında ara)
            min_depth: Minimum derinlik
            max_depth: Maximum derinlik
            limit: Maksimum sonuç
        """
        conditions = []
        params = []

        if name:
            conditions.append("""
                d.id IN (
                    SELECT rowid FROM dirs_fts
                    WHERE dirs_fts MATCH ?
                )
            """)
            fts_query = " ".join(f"{word}*" for word in name.strip().split())
            params.append(fts_query)

        if parent_path:
            conditions.append("(d.full_path LIKE ? OR d.name LIKE ?)")
            params.extend([f"%{parent_path}%", f"%{parent_path}%"])

        if min_depth is not None:
            conditions.append("d.depth >= ?")
            params.append(min_depth)

        if max_depth is not None:
            conditions.append("d.depth <= ?")
            params.append(max_depth)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
# istenen dosyadak toplam alt kaslör ve alt dosya sayısınıda döner
        query = f"""
            SELECT d.id, d.name, d.full_path, d.depth, d.modified_at,
                   (SELECT COUNT(*) FROM files WHERE directory_id = d.id) as file_count,
                   (SELECT COUNT(*) FROM directories WHERE parent_id = d.id) as subdir_count
            FROM directories d
            {where}
            ORDER BY d.depth ASC, d.name ASC
            LIMIT ?
        """
        params.append(limit)

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._dir_row_to_dict(r) for r in rows]

    def get_directory_contents(self, dir_path: str) -> dict:
        """
        Bir dizinin içeriğini getir (dosyalar + alt dizinler).

        Args:
            dir_path: Dizin tam yolu
        """
        with self.db.connect() as conn:
            dir_row = conn.execute(
                "SELECT id, name, full_path, depth FROM directories WHERE full_path = ?",
                (dir_path,)
            ).fetchone()

            if not dir_row:
                return {"error": f"Dizin bulunamadı: {dir_path}", "files": [], "subdirs": []}

            dir_id = dir_row["id"]

            files = conn.execute("""
                SELECT name, extension, full_path, size_bytes, modified_at
                FROM files WHERE directory_id = ?
                ORDER BY name
            """, (dir_id,)).fetchall()

            subdirs = conn.execute("""
                SELECT name, full_path,
                       (SELECT COUNT(*) FROM files WHERE directory_id = directories.id) as file_count
                FROM directories WHERE parent_id = ?
                ORDER BY name
            """, (dir_id,)).fetchall()

            return {
                "directory": dir_path,
                "files": [self._file_row_to_dict(r) for r in files],
                "subdirs": [dict(r) for r in subdirs],
            }

    # ================================================================
    # ZAMANA GÖRE ARAMA
    # ================================================================

    def find_recently_modified(
        self,
        days: int = 7,
        extension: Optional[str] = None,
        directory: Optional[str] = None,
        min_size_mb: Optional[float] = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Son X gün içinde değiştirilen dosyaları bul.

        Args:
            days: Kaç gün geriye bakılacak
            extension: Uzantı filtresi
            directory: Dizin filtresi
            min_size_mb: Minimum boyut (MB)
            limit: Maks sonuç
        """
        cutoff = time.time() - (days * 86400)
        conditions = ["f.modified_at >= ?"]
        params = [cutoff]

        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())

        if directory:
            conditions.append("""
                f.directory_id IN (
                    SELECT id FROM directories
                    WHERE full_path LIKE ? OR name LIKE ?
                )
            """)
            params.extend([f"%{directory}%", f"%{directory}%"])

        if min_size_mb is not None:
            conditions.append("f.size_bytes >= ?")
            params.append(int(min_size_mb * 1024 * 1024))

        where = " AND ".join(conditions)

        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, d.full_path as dir_path
            FROM files f
            JOIN directories d ON f.directory_id = d.id
            WHERE {where}
            ORDER BY f.modified_at DESC
            LIMIT ?
        """
        params.append(limit)

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._file_row_to_dict(r) for r in rows]

    def find_recently_created(self, days: int = 7, limit: int = 50) -> list[dict]:
        """Son X gün içinde oluşturulan dosyalar."""
        cutoff = time.time() - (days * 86400)

        query = """
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, f.created_at, d.full_path as dir_path
            FROM files f
            JOIN directories d ON f.directory_id = d.id
            WHERE f.created_at >= ?
            ORDER BY f.created_at DESC
            LIMIT ?
        """

        with self.db.connect() as conn:
            rows = conn.execute(query, (cutoff, limit)).fetchall()
            return [self._file_row_to_dict(r) for r in rows]

    # ================================================================
    # BOYUTA GÖRE ARAMA
    # ================================================================

    def find_largest_filess(
        self,
        extension: Optional[str] = None,
        directory: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """En büyük dosyaları bul."""
        conditions = []
        params = []

        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())

        if directory:
            conditions.append("""
                f.directory_id IN (
                    SELECT id FROM directories WHERE full_path LIKE ?
                )
            """)
            params.append(f"%{directory}%")

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, d.full_path as dir_path
            FROM files f
            JOIN directories d ON f.directory_id = d.id
            {where}
            ORDER BY f.size_bytes DESC
            LIMIT ?
        """
        params.append(limit)

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._file_row_to_dict(r) for r in rows]


    # ================================================================
    # UZANTI ANALİZLERİ
    # ================================================================

    def get_extension_stats(self, directory: Optional[str] = None) -> list[dict]:
        """
        Uzantı bazlı istatistikler.
        Kaç dosya, toplam boyut, ortalama boyut.
        """
        conditions = []
        params = []

        if directory:
            conditions.append("""
                f.directory_id IN (
                    SELECT id FROM directories WHERE full_path LIKE ?
                )
            """)
            params.append(f"%{directory}%")

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT f.extension,
                   COUNT(*) as file_count,
                   SUM(f.size_bytes) as total_size,
                   AVG(f.size_bytes) as avg_size,
                   MAX(f.size_bytes) as max_size
            FROM files f
            {where}
            GROUP BY f.extension
            ORDER BY total_size DESC
        """

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                {
                    "extension": r["extension"] or "(uzantısız)",
                    "file_count": r["file_count"],
                    "total_size_mb": round(r["total_size"] / (1024*1024), 2),
                    "avg_size_mb": round(r["avg_size"] / (1024*1024), 2),
                    "max_size_mb": round(r["max_size"] / (1024*1024), 2),
                }
                for r in rows
            ]

    def list_files_by_extension(
        self,
        extension: str,
        directory: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Belirli uzantıdaki tüm dosyaları listele."""
        ext = extension if extension.startswith(".") else f".{extension}"
        conditions = ["f.extension = ?"]
        params = [ext.lower()]

        if directory:
            conditions.append("""
                f.directory_id IN (
                    SELECT id FROM directories WHERE full_path LIKE ?
                )
            """)
            params.append(f"%{directory}%")

        where = " AND ".join(conditions)

        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, d.full_path as dir_path
            FROM files f
            JOIN directories d ON f.directory_id = d.id
            WHERE {where}
            ORDER BY f.name ASC
            LIMIT ?
        """
        params.append(limit)

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._file_row_to_dict(r) for r in rows]

    # ================================================================
    # DİZİN ANALİZLERİ
    # ================================================================

    def get_directory_size(self, dir_path: str, recursive: bool = True) -> dict:
        """
        Bir dizinin toplam boyutunu hesapla.

        Args:
            dir_path: Dizin yolu
            recursive: Alt dizinler dahil mi
        """
        with self.db.connect() as conn:
            if recursive:
                # CTE ile tüm alt dizinleri bul
                query = """
                    WITH RECURSIVE sub AS (
                        SELECT id FROM directories WHERE full_path = ?
                        UNION ALL
                        SELECT d.id FROM directories d
                        JOIN sub s ON d.parent_id = s.id
                    )
                    SELECT COUNT(*) as file_count,
                           COALESCE(SUM(f.size_bytes), 0) as total_size
                    FROM files f
                    WHERE f.directory_id IN (SELECT id FROM sub)
                """
            else:
                query = """
                    SELECT COUNT(*) as file_count,
                           COALESCE(SUM(f.size_bytes), 0) as total_size
                    FROM files f
                    JOIN directories d ON f.directory_id = d.id
                    WHERE d.full_path = ?
                """

            row = conn.execute(query, (dir_path,)).fetchone()
            return {
                "directory": dir_path,
                "file_count": row["file_count"],
                "total_size_bytes": row["total_size"],
                "total_size_mb": round(row["total_size"] / (1024*1024), 2),
                "total_size_gb": round(row["total_size"] / (1024**3), 2),
                "recursive": recursive,
            }

    def find_largest_directories(self, limit: int = 20) -> list[dict]:
        """En büyük dizinleri bul (recursive boyut)."""
        query = """
            SELECT d.full_path, d.name,
                   COUNT(f.id) as file_count,
                   COALESCE(SUM(f.size_bytes), 0) as total_size
            FROM directories d
            LEFT JOIN files f ON f.directory_id = d.id
            GROUP BY d.id
            HAVING file_count > 0
            ORDER BY total_size DESC
            LIMIT ?
        """

        with self.db.connect() as conn:
            rows = conn.execute(query, (limit,)).fetchall()
            return [
                {
                    "name": r["name"],
                    "full_path": r["full_path"],
                    "file_count": r["file_count"],
                    "total_size_mb": round(r["total_size"] / (1024*1024), 2),
                }
                for r in rows
            ]

    def find_empty_directories(self, limit: int = 50) -> list[dict]:
        """Boş dizinleri bul (dosya ve alt dizin içermeyen)."""
        query = """
            SELECT d.name, d.full_path, d.depth
            FROM directories d
            WHERE NOT EXISTS (SELECT 1 FROM files WHERE directory_id = d.id)
              AND NOT EXISTS (SELECT 1 FROM directories WHERE parent_id = d.id)
            ORDER BY d.depth DESC
            LIMIT ?
        """

        with self.db.connect() as conn:
            rows = conn.execute(query, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ================================================================
    # YINELENEN DOSYA TESPİTİ
    # ================================================================

    def find_duplicate_names(
        self,
        extension: Optional[str] = None,
        min_count: int = 2,
        limit: int = 30,
    ) -> list[dict]:
        """
        Aynı ada sahip dosyaları bul (farklı konumlarda).

        Args:
            extension: Uzantı filtresi
            min_count: Minimum tekrar sayısı
            limit: Maks sonuç
        """
        conditions = []
        params = []

        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Önce tekrar eden isimleri bul
        query = f"""
            SELECT f.name, f.extension, COUNT(*) as count,
                   GROUP_CONCAT(f.full_path, '|||') as paths,
                   SUM(f.size_bytes) as total_size
            FROM files f
            {where}
            GROUP BY f.name, f.extension
            HAVING count >= ?
            ORDER BY count DESC
            LIMIT ?
        """
        params.extend([min_count, limit])

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                {
                    "name": r["name"],
                    "extension": r["extension"],
                    "count": r["count"],
                    "paths": r["paths"].split("|||"),
                    "total_size_mb": round(r["total_size"] / (1024*1024), 2),
                }
                for r in rows
            ]

    def find_largest_files(self, extension=None, directory=None, limit=20) -> list[dict]:
        conditions, params = [], []
        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())
        if directory:
            conditions.append("f.directory_id IN (SELECT id FROM directories WHERE full_path LIKE ? OR name LIKE ?)")
            params.extend([f"%{directory}%", f"%{directory}%"])
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, f.created_at, d.full_path as dir_path
            FROM files f JOIN directories d ON f.directory_id = d.id
            {where} ORDER BY f.size_bytes DESC LIMIT ?
        """
        params.append(limit)
        with self.db.connect() as conn:
            return [self._file_row_to_dict(r) for r in conn.execute(query, params).fetchall()]

    def find_small_files(self, max_size_mb=1.0, extension=None, directory=None, limit=50) -> list[dict]:
        conditions = ["f.size_bytes <= ? AND f.size_bytes > 0"]
        params = [int(max_size_mb * 1024 * 1024)]
        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())
        if directory:
            conditions.append("f.directory_id IN (SELECT id FROM directories WHERE full_path LIKE ? OR name LIKE ?)")
            params.extend([f"%{directory}%", f"%{directory}%"])
        where = " AND ".join(conditions)
        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, f.created_at, d.full_path as dir_path
            FROM files f JOIN directories d ON f.directory_id = d.id
            WHERE {where} ORDER BY f.size_bytes ASC LIMIT ?
        """
        params.append(limit)
        with self.db.connect() as conn:
            return [find_small_files(r) for r in conn.execute(query, params).fetchall()]

    def find_empty_files(self, directory=None, limit=50) -> list[dict]:
        conditions = ["f.size_bytes = 0"]
        params = []
        if directory:
            conditions.append("f.directory_id IN (SELECT id FROM directories WHERE full_path LIKE ? OR name LIKE ?)")
            params.extend([f"%{directory}%", f"%{directory}%"])
        where = " AND ".join(conditions)
        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, d.full_path as dir_path
            FROM files f JOIN directories d ON f.directory_id = d.id
            WHERE {where} LIMIT ?
        """
        params.append(limit)
        with self.db.connect() as conn:
            return [self._file_row_to_dict(r) for r in conn.execute(query, params).fetchall()]

    def find_empty_directories(self, limit=50) -> list[dict]:
        query = """
                SELECT d.name, d.full_path, d.depth
                FROM directories d
                WHERE NOT EXISTS (SELECT 1 FROM files WHERE directory_id = d.id)
                  AND NOT EXISTS (SELECT 1 FROM directories WHERE parent_id = d.id)
                ORDER BY d.depth DESC LIMIT ? \
                """
        with self.db.connect() as conn:
            return [dict(r) for r in conn.execute(query, (limit,)).fetchall()]

    def get_extension_stats(self, directory=None) -> list[dict]:
        conditions, params = [], []
        if directory:
            conditions.append("f.directory_id IN (SELECT id FROM directories WHERE full_path LIKE ? OR name LIKE ?)")
            params.extend([f"%{directory}%", f"%{directory}%"])
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT f.extension, COUNT(*) as file_count,
                   SUM(f.size_bytes) as total_size, AVG(f.size_bytes) as avg_size
            FROM files f {where}
            GROUP BY f.extension ORDER BY total_size DESC
        """
        with self.db.connect() as conn:
            return [
                {"extension": r["extension"] or "(uzantisiz)", "file_count": r["file_count"],
                 "total_size_mb": round(r["total_size"] / (1024 * 1024), 2),
                 "avg_size_mb": round(r["avg_size"] / (1024 * 1024), 2)}
                for r in conn.execute(query, params).fetchall()
            ]

    def find_duplicate_names(self, extension=None, min_count=2, limit=30) -> list[dict]:
        conditions, params = [], []
        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT f.name, f.extension, COUNT(*) as count,
                   GROUP_CONCAT(f.full_path, '|||') as paths
            FROM files f {where}
            GROUP BY f.name, f.extension HAVING count >= ?
            ORDER BY count DESC LIMIT ?
        """
        params.extend([min_count, limit])
        with self.db.connect() as conn:
            return [
                {"name": r["name"], "extension": r["extension"],
                 "count": r["count"], "paths": r["paths"].split("|||")}
                for r in conn.execute(query, params).fetchall()
            ]

    def get_directory_tree(self, dir_path: str, max_depth=3) -> dict:
        with self.db.connect() as conn:
            root = conn.execute("SELECT id, name, full_path FROM directories WHERE full_path = ?",
                                (dir_path,)).fetchone()
            if not root:
                return {"error": f"Dizin bulunamadi: {dir_path}"}
            return self._build_tree(conn, root["id"], max_depth)

    def _build_tree(self, conn, dir_id, max_depth):
        row = conn.execute("SELECT name, full_path FROM directories WHERE id = ?", (dir_id,)).fetchone()
        fc = conn.execute("SELECT COUNT(*) as c FROM files WHERE directory_id = ?", (dir_id,)).fetchone()["c"]
        result = {"name": row["name"], "path": row["full_path"], "file_count": fc, "children": []}
        if max_depth > 0:
            for child in conn.execute("SELECT id FROM directories WHERE parent_id = ? ORDER BY name",
                                      (dir_id,)).fetchall():
                result["children"].append(self._build_tree(conn, child["id"], max_depth - 1))
        return result

    # ================================================================
    # GELIŞMIŞ / KOMBİNE SORGULAR
    # ================================================================

    def advanced_search(
        self,
        name: Optional[str] = None,
        extension: Optional[str] = None,
        directory: Optional[str] = None,
        min_size_mb: Optional[float] = None,
        max_size_mb: Optional[float] = None,
        modified_after_days: Optional[int] = None,
        modified_before_days: Optional[int] = None,
        created_after_days: Optional[int] = None,
        is_hidden: Optional[bool] = None,
        sort_by: str = "modified_at",
        sort_order: str = "DESC",
        limit: int = 50,
    ) -> list[dict]:
        """
        Tüm filtreleri kombine edebilen gelişmiş arama.
        LLM karmaşık isteklerde bunu kullanır.

        Args:
            name: Dosya adı araması (fuzzy)
            extension: Uzantı filtresi
            directory: Dizin filtresi
            min_size_mb: Min boyut (MB)
            max_size_mb: Max boyut (MB)
            modified_after_days: Son X gün içinde değişmiş
            modified_before_days: X günden eski değişiklik
            created_after_days: Son X gün içinde oluşturulmuş
            is_hidden: Gizli dosya filtresi
            sort_by: Sıralama kolonu (name, size_bytes, modified_at, created_at)
            sort_order: Sıralama yönü (ASC, DESC)
            limit: Maks sonuç
        """
        conditions = []
        params = []

        if name:
            conditions.append("""
                f.id IN (
                    SELECT rowid FROM files_fts WHERE files_fts MATCH ?
                )
            """)
            fts_query = " ".join(f"{word}*" for word in name.strip().split())
            params.append(fts_query)

        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())

        if directory:
            conditions.append("""
                f.directory_id IN (
                    SELECT id FROM directories
                    WHERE full_path LIKE ? OR name LIKE ?
                )
            """)
            params.extend([f"%{directory}%", f"%{directory}%"])

        if min_size_mb is not None:
            conditions.append("f.size_bytes >= ?")
            params.append(int(min_size_mb * 1024 * 1024))

        if max_size_mb is not None:
            conditions.append("f.size_bytes <= ?")
            params.append(int(max_size_mb * 1024 * 1024))

        now = time.time()

        if modified_after_days is not None:
            conditions.append("f.modified_at >= ?")
            params.append(now - (modified_after_days * 86400))

        if modified_before_days is not None:
            conditions.append("f.modified_at <= ?")
            params.append(now - (modified_before_days * 86400))

        if created_after_days is not None:
            conditions.append("f.created_at >= ?")
            params.append(now - (created_after_days * 86400))

        if is_hidden is not None:
            conditions.append("f.is_hidden = ?")
            params.append(1 if is_hidden else 0)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Güvenli sıralama
        allowed_sorts = {"name", "size_bytes", "modified_at", "created_at", "extension"}
        sort_col = sort_by if sort_by in allowed_sorts else "modified_at"
        sort_dir = "ASC" if sort_order.upper() == "ASC" else "DESC"

        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, f.created_at, f.is_hidden,
                   d.full_path as dir_path
            FROM files f
            JOIN directories d ON f.directory_id = d.id
            {where}
            ORDER BY f.{sort_col} {sort_dir}
            LIMIT ?
        """
        params.append(limit)

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._file_row_to_dict(r) for r in rows]

    # ================================================================
    # İSTATİSTİKLER
    # ================================================================

    def get_system_stats(self) -> dict:
        """Genel sistem istatistikleri."""
        return self.db.get_stats()

    def get_directory_tree(self, dir_path: str, max_depth: int = 3) -> dict:
        """
        Dizin ağacı yapısını getir.

        Args:
            dir_path: Kök dizin yolu
            max_depth: Kaç seviye derine inilecek
        """
        with self.db.connect() as conn:
            root = conn.execute(
                "SELECT id, name, full_path, depth FROM directories WHERE full_path = ?",
                (dir_path,)
            ).fetchone()

            if not root:
                return {"error": f"Dizin bulunamadı: {dir_path}"}

            return self._build_tree(conn, root["id"], root["depth"], max_depth)

    def _build_tree(self, conn, dir_id: int, current_depth: int, max_depth: int) -> dict:
        """Recursive ağaç yapısı."""
        dir_row = conn.execute(
            "SELECT name, full_path FROM directories WHERE id = ?",
            (dir_id,)
        ).fetchone()

        file_count = conn.execute(
            "SELECT COUNT(*) as c FROM files WHERE directory_id = ?",
            (dir_id,)
        ).fetchone()["c"]

        result = {
            "name": dir_row["name"],
            "path": dir_row["full_path"],
            "file_count": file_count,
            "children": [],
        }

        if max_depth > 0:
            children = conn.execute(
                "SELECT id, depth FROM directories WHERE parent_id = ? ORDER BY name",
                (dir_id,)
            ).fetchall()

            for child in children:
                result["children"].append(
                    self._build_tree(conn, child["id"], child["depth"], max_depth - 1)
                )

        return result

    # ================================================================
    # YARDIMCI METOTLAR
    # ================================================================

    @staticmethod
    def _dir_row_to_dict(row) -> dict:
        """SQLite Row nesnesini dizin dict'ine çevir."""
        from datetime import datetime
        d = dict(row)
        if "modified_at" in d and d["modified_at"]:
            try:
                d["modified_at_human"] = datetime.fromtimestamp(d["modified_at"]).strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError):
                d["modified_at_human"] = "bilinmiyor"
        return d

    @staticmethod
    def _file_row_to_dict(row) -> dict:
        """SQLite Row nesnesini okunabilir dict'e çevir."""
        from datetime import datetime

        d = dict(row)

        # Boyutu okunabilir formata çevir
        size = d.get("size_bytes", 0)
        if size >= 1024 * 1024 * 1024:
            d["size_human"] = f"{size / (1024**3):.2f} GB"
        elif size >= 1024 * 1024:
            d["size_human"] = f"{size / (1024**2):.2f} MB"
        elif size >= 1024:
            d["size_human"] = f"{size / 1024:.1f} KB"
        else:
            d["size_human"] = f"{size} B"

        # Tarihleri okunabilir formata çevir
        for key in ("modified_at", "created_at"):
            if key in d and d[key]:
                try:
                    d[key + "_human"] = datetime.fromtimestamp(d[key]).strftime("%Y-%m-%d %H:%M")
                except (ValueError, OSError):
                    d[key + "_human"] = "bilinmiyor"

        return d