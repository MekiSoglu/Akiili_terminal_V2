"""
Dosya Sorgu Motoru (FileQueryEngine)

LLM'in araç olarak çağıracağı tüm dosya arama/sorgulama metotları.
Her metot basit parametreler alır ve sonuç döner.

v2 DEĞİŞİKLİKLER:
  - search_files_by_exact_name: SQL LIKE yerine tam eşleşme (= operatörü)
  - search_directories: FTS5 yerine önce tam eşleşme, sonra LIKE, en son FTS5
  - search_files directory filtresi: dizin adı tam eşleşme öncelikli
  - _resolve_directory_id: dizin adından ID çözümleme (tam → kısmi → FTS5 sıralaması)
"""

import time
from typing import Optional

from src.indexing.Database import Database


class FileQueryEngine:
    """
    Dosya sistemi sorgu motoru v2.
    Arama önceliği: Tam eşleşme → LIKE → FTS5 fuzzy
    """

    def __init__(self, config_path: str = "config.json"):
        self.db = Database(config_path)

    # ================================================================
    # DİZİN ÇÖZÜMLEME (Yeni — tüm metotların kullandığı çekirdek)
    # ================================================================

    def _resolve_directory_id(self, dir_name: str, conn) -> Optional[int]:
        """
        Dizin adından directory ID çözümle.
        Sıralama: Tam ad eşleşme → path'te tam segment → LIKE → FTS5

        "transform_test" → doğru dizini bulur, "transform/tests" ile karışmaz.
        """
        if not dir_name:
            return None

        # 1) Tam yol eşleşme (C:\...\transform_test)
        row = conn.execute(
            "SELECT id FROM directories WHERE full_path = ?", (dir_name,)
        ).fetchone()
        if row:
            return row["id"]

        # 2) Tam ad eşleşme (name = 'transform_test')
        row = conn.execute(
            "SELECT id FROM directories WHERE LOWER(name) = LOWER(?) ORDER BY depth ASC LIMIT 1",
            (dir_name,),
        ).fetchone()
        if row:
            return row["id"]

        # 3) Path'te tam segment eşleşme (full_path'te /transform_test/ veya \transform_test\)
        #    Bu, "transform_test" ararken "transform/tests" bulmasını engeller
        row = conn.execute(
            """SELECT id FROM directories
               WHERE full_path LIKE ? OR full_path LIKE ? OR full_path LIKE ?
               ORDER BY depth ASC LIMIT 1""",
            (f"%\\{dir_name}", f"%/{dir_name}", f"%\\{dir_name}\\%"),
        ).fetchone()
        if row:
            return row["id"]

        # 4) LIKE ile kısmi eşleşme (son çare)
        row = conn.execute(
            "SELECT id FROM directories WHERE full_path LIKE ? ORDER BY depth ASC LIMIT 1",
            (f"%{dir_name}%",),
        ).fetchone()
        if row:
            return row["id"]

        return None

    def _resolve_directory_path(self, dir_name: str, conn) -> Optional[str]:
        """Dizin adından tam yol çözümle."""
        if not dir_name:
            return None

        # Tam yol ise direkt kontrol
        row = conn.execute(
            "SELECT full_path FROM directories WHERE full_path = ?", (dir_name,)
        ).fetchone()
        if row:
            return row["full_path"]

        # Ad ile ara
        row = conn.execute(
            "SELECT full_path FROM directories WHERE LOWER(name) = LOWER(?) ORDER BY depth ASC LIMIT 1",
            (dir_name,),
        ).fetchone()
        if row:
            return row["full_path"]

        # Path segmenti ile ara
        row = conn.execute(
            """SELECT full_path FROM directories
               WHERE full_path LIKE ? OR full_path LIKE ?
               ORDER BY depth ASC LIMIT 1""",
            (f"%\\{dir_name}", f"%/{dir_name}"),
        ).fetchone()
        if row:
            return row["full_path"]

        return None

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
        Genel dosya arama.

        Arama önceliği:
          name: Önce tam eşleşme (LOWER(name) = LOWER(?)), sonra LIKE, sonra FTS5
          directory: _resolve_directory_id ile çözümleme (tam ad → segment → LIKE)
        """
        conditions = []
        params = []

        # İsim araması — önce tam eşleşme, yoksa LIKE, yoksa FTS5
        if name:
            conditions.append("""(
                LOWER(f.name) = LOWER(?)
                OR f.name LIKE ?
                OR f.id IN (SELECT rowid FROM files_fts WHERE files_fts MATCH ?)
            )""")
            fts_query = " ".join(f"{w}*" for w in name.strip().split())
            params.extend([name, f"%{name}%", fts_query])

        # Uzantı filtresi
        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())

        # Dizin filtresi — _resolve_directory_id kullan
        if directory:
            with self.db.connect() as conn:
                dir_id = self._resolve_directory_id(directory, conn)
            if dir_id:
                # Bu dizin ve alt dizinlerinde ara
                conditions.append("""
                    f.directory_id IN (
                        WITH RECURSIVE sub AS (
                            SELECT id FROM directories WHERE id = ?
                            UNION ALL
                            SELECT d.id FROM directories d JOIN sub s ON d.parent_id = s.id
                        )
                        SELECT id FROM sub
                    )
                """)
                params.append(dir_id)
            else:
                # Dizin bulunamadıysa path LIKE fallback
                conditions.append("""
                    f.directory_id IN (
                        SELECT d.id FROM directories d
                        WHERE d.full_path LIKE ?
                    )
                """)
                params.append(f"%{directory}%")

        # Boyut filtreleri
        if min_size_mb is not None:
            conditions.append("f.size_bytes >= ?")
            params.append(int(min_size_mb * 1024 * 1024))

        if max_size_mb is not None:
            conditions.append("f.size_bytes <= ?")
            params.append(int(max_size_mb * 1024 * 1024))

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Sıralama: tam eşleşme önce gelsin
        if name:
            order = f"""ORDER BY
                CASE WHEN LOWER(f.name) = LOWER('{name}') THEN 0
                     WHEN f.name LIKE '%{name}%' THEN 1
                     ELSE 2 END,
                f.modified_at DESC"""
        else:
            order = "ORDER BY f.modified_at DESC"

        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, f.created_at, d.full_path as dir_path
            FROM files f
            JOIN directories d ON f.directory_id = d.id
            {where}
            {order}
            LIMIT ?
        """
        params.append(limit)

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._file_row_to_dict(r) for r in rows]

    def search_files_by_exact_name(
        self, name: str, extension: Optional[str] = None
    ) -> list[dict]:
        """
        Tam dosya adıyla arama (SQL = operatörü, FTS5 KULLANMAZ).

        "test_resim" ararken "test_rotation" DÖNMEZ.
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
        Öncelik: Tam ad eşleşme → segment eşleşme → LIKE → FTS5
        """
        conditions = []
        params = []

        if name:
            # Tam ad eşleşme öncelikli, FTS5 son çare
            conditions.append("""(
                LOWER(d.name) = LOWER(?)
                OR d.full_path LIKE ?
                OR d.full_path LIKE ?
                OR d.id IN (SELECT rowid FROM dirs_fts WHERE dirs_fts MATCH ?)
            )""")
            fts_query = " ".join(f"{word}*" for word in name.strip().split())
            params.extend(
                [
                    name,  # tam ad
                    f"%\\{name}",  # segment sonu
                    f"%\\{name}\\%",  # segment ortası
                    fts_query,  # FTS5 fuzzy
                ]
            )

        if parent_path:
            conditions.append("d.full_path LIKE ?")
            params.append(f"%{parent_path}%")

        if min_depth is not None:
            conditions.append("d.depth >= ?")
            params.append(min_depth)

        if max_depth is not None:
            conditions.append("d.depth <= ?")
            params.append(max_depth)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        # Sıralama: tam ad eşleşme önce
        if name:
            order = f"""ORDER BY
                CASE WHEN LOWER(d.name) = LOWER('{name}') THEN 0
                     WHEN d.full_path LIKE '%\\{name}' THEN 1
                     WHEN d.full_path LIKE '%\\{name}\\%' THEN 2
                     ELSE 3 END,
                d.depth ASC, d.name ASC"""
        else:
            order = "ORDER BY d.depth ASC, d.name ASC"

        query = f"""
            SELECT d.id, d.name, d.full_path, d.depth, d.modified_at,
                   (SELECT COUNT(*) FROM files WHERE directory_id = d.id) as file_count,
                   (SELECT COUNT(*) FROM directories WHERE parent_id = d.id) as subdir_count
            FROM directories d
            {where}
            {order}
            LIMIT ?
        """
        params.append(limit)

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._dir_row_to_dict(r) for r in rows]

    def get_directory_contents(self, dir_path: str) -> dict:
        """Bir dizinin içeriğini getir (dosyalar + alt dizinler)."""
        with self.db.connect() as conn:
            # Önce tam yol, sonra ad ile ara
            dir_row = conn.execute(
                "SELECT id, name, full_path, depth FROM directories WHERE full_path = ?",
                (dir_path,),
            ).fetchone()

            if not dir_row:
                # Tam yol bulunamadı → ad ile ara
                resolved = self._resolve_directory_path(dir_path, conn)
                if resolved:
                    dir_row = conn.execute(
                        "SELECT id, name, full_path, depth FROM directories WHERE full_path = ?",
                        (resolved,),
                    ).fetchone()

            if not dir_row:
                return {
                    "error": f"Dizin bulunamadı: {dir_path}",
                    "files": [],
                    "subdirs": [],
                }

            dir_id = dir_row["id"]

            # Dosyalar
            files = conn.execute(
                """SELECT name, extension, full_path, size_bytes, modified_at, created_at
                   FROM files WHERE directory_id = ?
                   ORDER BY name""",
                (dir_id,),
            ).fetchall()

            # Alt dizinler
            subdirs = conn.execute(
                """SELECT d.name, d.full_path,
                          (SELECT COUNT(*) FROM files WHERE directory_id = d.id) as file_count
                   FROM directories d WHERE d.parent_id = ?
                   ORDER BY d.name""",
                (dir_id,),
            ).fetchall()

            return {
                "directory": dir_row["full_path"],
                "files": [self._file_row_to_dict(f) for f in files],
                "subdirs": [dict(s) for s in subdirs],
            }

    # ================================================================
    # BÜYÜK/KÜÇÜK DOSYALAR
    # ================================================================

    def find_largest_files(
        self,
        min_size_mb: float = 0,
        extension: Optional[str] = None,
        directory: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """En büyük dosyaları bul."""
        conditions = []
        params = []

        if min_size_mb > 0:
            conditions.append("f.size_bytes >= ?")
            params.append(int(min_size_mb * 1024 * 1024))

        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())

        if directory:
            with self.db.connect() as conn:
                dir_id = self._resolve_directory_id(directory, conn)
            if dir_id:
                conditions.append("""f.directory_id IN (
                    WITH RECURSIVE sub AS (
                        SELECT id FROM directories WHERE id = ?
                        UNION ALL
                        SELECT d.id FROM directories d JOIN sub s ON d.parent_id = s.id
                    ) SELECT id FROM sub)""")
                params.append(dir_id)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, d.full_path as dir_path
            FROM files f JOIN directories d ON f.directory_id = d.id
            {where}
            ORDER BY f.size_bytes DESC
            LIMIT ?
        """
        params.append(limit)

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._file_row_to_dict(r) for r in rows]

    def find_small_files(
        self,
        max_size_mb: float = 1.0,
        extension: Optional[str] = None,
        directory: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Belirtilen boyutun altındaki dosyaları bul."""
        conditions = ["f.size_bytes <= ?"]
        params = [int(max_size_mb * 1024 * 1024)]

        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())

        if directory:
            with self.db.connect() as conn:
                dir_id = self._resolve_directory_id(directory, conn)
            if dir_id:
                conditions.append(
                    "f.directory_id IN (WITH RECURSIVE sub AS (SELECT id FROM directories WHERE id = ? UNION ALL SELECT d.id FROM directories d JOIN sub s ON d.parent_id = s.id) SELECT id FROM sub)"
                )
                params.append(dir_id)

        where = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, d.full_path as dir_path
            FROM files f JOIN directories d ON f.directory_id = d.id
            {where}
            ORDER BY f.size_bytes ASC
            LIMIT ?
        """
        params.append(limit)

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._file_row_to_dict(r) for r in rows]

    def find_empty_files(self, directory: Optional[str] = None) -> list[dict]:
        """0 byte dosyaları bul."""
        return self.find_small_files(max_size_mb=0, directory=directory, limit=50)

    def find_empty_directories(self, directory: Optional[str] = None) -> list[dict]:
        """Boş klasörleri bul."""
        conditions = [
            "(SELECT COUNT(*) FROM files WHERE directory_id = d.id) = 0",
            "(SELECT COUNT(*) FROM directories WHERE parent_id = d.id) = 0",
        ]
        params = []

        if directory:
            with self.db.connect() as conn:
                dir_id = self._resolve_directory_id(directory, conn)
            if dir_id:
                conditions.append(
                    "d.id IN (WITH RECURSIVE sub AS (SELECT id FROM directories WHERE id = ? UNION ALL SELECT c.id FROM directories c JOIN sub s ON c.parent_id = s.id) SELECT id FROM sub)"
                )
                params.append(dir_id)

        where = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT d.id, d.name, d.full_path, d.depth, d.modified_at,
                   0 as file_count, 0 as subdir_count
            FROM directories d
            {where}
            ORDER BY d.name
            LIMIT 50
        """

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._dir_row_to_dict(r) for r in rows]

    # ================================================================
    # TARİH BAZLI ARAMA
    # ================================================================

    def find_recently_modified(
        self,
        days: int = 7,
        extension: Optional[str] = None,
        directory: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Son X gün içinde değiştirilen dosyaları bul."""
        cutoff = time.time() - (days * 86400)
        conditions = ["f.modified_at >= ?"]
        params = [cutoff]

        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())

        if directory:
            with self.db.connect() as conn:
                dir_id = self._resolve_directory_id(directory, conn)
            if dir_id:
                conditions.append(
                    "f.directory_id IN (WITH RECURSIVE sub AS (SELECT id FROM directories WHERE id = ? UNION ALL SELECT d.id FROM directories d JOIN sub s ON d.parent_id = s.id) SELECT id FROM sub)"
                )
                params.append(dir_id)

        where = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, f.created_at, d.full_path as dir_path
            FROM files f JOIN directories d ON f.directory_id = d.id
            {where}
            ORDER BY f.modified_at DESC
            LIMIT ?
        """
        params.append(limit)

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._file_row_to_dict(r) for r in rows]

    # ================================================================
    # İSTATİSTİKLER
    # ================================================================

    def get_extension_stats(self, directory: Optional[str] = None) -> list[dict]:
        """Uzantı bazlı istatistikler."""
        conditions = []
        params = []

        if directory:
            with self.db.connect() as conn:
                dir_id = self._resolve_directory_id(directory, conn)
            if dir_id:
                conditions.append(
                    "f.directory_id IN (WITH RECURSIVE sub AS (SELECT id FROM directories WHERE id = ? UNION ALL SELECT d.id FROM directories d JOIN sub s ON d.parent_id = s.id) SELECT id FROM sub)"
                )
                params.append(dir_id)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT f.extension,
                   COUNT(*) as file_count,
                   ROUND(SUM(f.size_bytes) / 1048576.0, 2) as total_size_mb,
                   ROUND(AVG(f.size_bytes) / 1048576.0, 2) as avg_size_mb
            FROM files f
            {where}
            GROUP BY f.extension
            ORDER BY SUM(f.size_bytes) DESC
        """

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_system_stats(self) -> dict:
        """Genel sistem istatistikleri."""
        return self.db.get_stats()

    def find_directory_size(self, dir_path: str, recursive: bool = True) -> dict:
        """Dizin boyutunu hesapla."""
        with self.db.connect() as conn:
            # Dizini çözümle
            resolved = self._resolve_directory_path(dir_path, conn)
            if not resolved:
                return {"error": f"Dizin bulunamadı: {dir_path}"}

            dir_id = self._resolve_directory_id(resolved, conn)
            if not dir_id:
                return {"error": f"Dizin ID bulunamadı: {resolved}"}

            if recursive:
                row = conn.execute(
                    """
                    WITH RECURSIVE sub AS (
                        SELECT id FROM directories WHERE id = ?
                        UNION ALL
                        SELECT d.id FROM directories d JOIN sub s ON d.parent_id = s.id
                    )
                    SELECT COUNT(*) as file_count, COALESCE(SUM(size_bytes), 0) as total_size
                    FROM files WHERE directory_id IN (SELECT id FROM sub)
                """,
                    (dir_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as file_count, COALESCE(SUM(size_bytes), 0) as total_size FROM files WHERE directory_id = ?",
                    (dir_id,),
                ).fetchone()

            total = row["total_size"]
            return {
                "directory": resolved,
                "file_count": row["file_count"],
                "total_size_bytes": total,
                "total_size_mb": round(total / 1048576, 2),
                "total_size_gb": round(total / (1024**3), 2),
                "recursive": recursive,
            }

    def find_duplicate_names(
        self,
        name: Optional[str] = None,
        extension: Optional[str] = None,
        min_count: int = 2,
    ) -> list[dict]:
        """Aynı isimde birden fazla dosya bul."""
        conditions = ["cnt >= ?"]
        params = [min_count]

        having_extra = ""
        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            having_extra = " AND extension = ?"
            params.insert(0, ext.lower())

        if name:
            having_extra += " AND name LIKE ?"
            params.insert(0, f"%{name}%")

        query = f"""
            SELECT name, extension, COUNT(*) as cnt,
                   GROUP_CONCAT(full_path, '|||') as paths
            FROM files
            WHERE 1=1 {f"AND extension = '{ext}'" if extension else ""}
            {f"AND name LIKE '%{name}%'" if name else ""}
            GROUP BY name, extension
            HAVING COUNT(*) >= ?
            ORDER BY cnt DESC
            LIMIT 50
        """

        with self.db.connect() as conn:
            rows = conn.execute(query, [min_count]).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["paths"] = d["paths"].split("|||") if d.get("paths") else []
                results.append(d)
            return results

    def get_directory_tree(self, dir_path: str, max_depth: int = 3) -> dict:
        """Dizin ağacı yapısını getir."""
        with self.db.connect() as conn:
            # Dizini çözümle
            resolved = self._resolve_directory_path(dir_path, conn)
            target = resolved or dir_path

            root = conn.execute(
                "SELECT id, name, full_path, depth FROM directories WHERE full_path = ?",
                (target,),
            ).fetchone()

            if not root:
                return {"error": f"Dizin bulunamadı: {dir_path}"}

            return self._build_tree(conn, root["id"], max_depth)

    def _build_tree(self, conn, dir_id: int, max_depth: int) -> dict:
        """Recursive ağaç yapısı."""
        dir_row = conn.execute(
            "SELECT name, full_path FROM directories WHERE id = ?", (dir_id,)
        ).fetchone()

        fc = conn.execute(
            "SELECT COUNT(*) as c FROM files WHERE directory_id = ?", (dir_id,)
        ).fetchone()["c"]

        result = {
            "name": dir_row["name"],
            "path": dir_row["full_path"],
            "file_count": fc,
            "children": [],
        }

        if max_depth > 0:
            for child in conn.execute(
                "SELECT id FROM directories WHERE parent_id = ? ORDER BY name",
                (dir_id,),
            ).fetchall():
                result["children"].append(
                    self._build_tree(conn, child["id"], max_depth - 1)
                )

        return result

    # ================================================================
    # GELİŞMİŞ ARAMA
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
        """Tüm filtreleri kombine edebilen gelişmiş arama."""
        conditions = []
        params = []

        if name:
            conditions.append("(LOWER(f.name) = LOWER(?) OR f.name LIKE ?)")
            params.extend([name, f"%{name}%"])

        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            conditions.append("f.extension = ?")
            params.append(ext.lower())

        if directory:
            with self.db.connect() as conn:
                dir_id = self._resolve_directory_id(directory, conn)
            if dir_id:
                conditions.append(
                    "f.directory_id IN (WITH RECURSIVE sub AS (SELECT id FROM directories WHERE id = ? UNION ALL SELECT d.id FROM directories d JOIN sub s ON d.parent_id = s.id) SELECT id FROM sub)"
                )
                params.append(dir_id)

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
        allowed_sorts = {"name", "size_bytes", "modified_at", "created_at", "extension"}
        sort_col = sort_by if sort_by in allowed_sorts else "modified_at"
        sort_dir = "ASC" if sort_order.upper() == "ASC" else "DESC"

        query = f"""
            SELECT f.name, f.extension, f.full_path, f.size_bytes,
                   f.modified_at, f.created_at, f.is_hidden,
                   d.full_path as dir_path
            FROM files f JOIN directories d ON f.directory_id = d.id
            {where}
            ORDER BY f.{sort_col} {sort_dir}
            LIMIT ?
        """
        params.append(limit)

        with self.db.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._file_row_to_dict(r) for r in rows]

    # ================================================================
    # YARDIMCI
    # ================================================================

    @staticmethod
    def _dir_row_to_dict(row) -> dict:
        from datetime import datetime

        d = dict(row)
        if "modified_at" in d and d["modified_at"]:
            try:
                d["modified_at_human"] = datetime.fromtimestamp(
                    d["modified_at"]
                ).strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError):
                d["modified_at_human"] = "bilinmiyor"
        return d

    @staticmethod
    def _file_row_to_dict(row) -> dict:
        from datetime import datetime

        d = dict(row)
        size = d.get("size_bytes", 0)
        if size >= 1024**3:
            d["size_human"] = f"{size / (1024**3):.2f} GB"
        elif size >= 1024**2:
            d["size_human"] = f"{size / (1024**2):.2f} MB"
        elif size >= 1024:
            d["size_human"] = f"{size / 1024:.1f} KB"
        else:
            d["size_human"] = f"{size} B"
        for key in ("modified_at", "created_at"):
            if key in d and d[key]:
                try:
                    d[key + "_human"] = datetime.fromtimestamp(d[key]).strftime(
                        "%Y-%m-%d %H:%M"
                    )
                except (ValueError, OSError):
                    d[key + "_human"] = "bilinmiyor"
        return d
