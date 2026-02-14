import sqlite3
conn = sqlite3.connect('data/file_index.db')

print("=== LIKE ===")
rows = conn.execute("SELECT name, full_path FROM files WHERE name LIKE '%m12%'").fetchall()
for r in rows:
    print(r)

print("\n=== FTS ===")
rows = conn.execute("SELECT rowid FROM files_fts WHERE files_fts MATCH 'm12*'").fetchall()
for r in rows:
    print(r)

print("\n=== OR ===")
rows = conn.execute("SELECT name, full_path FROM files WHERE name LIKE '%m12%' OR id IN (SELECT rowid FROM files_fts WHERE files_fts MATCH 'm12*')").fetchall()
for r in rows:
    print(r)