import sqlite3
import tempfile
import time
from jarvis.scripts.bench_search import populate_test_database

with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
    p = f.name
con = sqlite3.connect(p)
populate_test_database(con, 10000)
c = con.cursor()

# 1. Old query
t0 = time.perf_counter()
for _ in range(50):
    expr = '(name:"deep"* OR stem:"deep"* OR path_tokens:"deep"*) AND (name:"learning"* OR stem:"learning"* OR path_tokens:"learning"*)'
    c.execute('''
        SELECT f.id FROM files_fts
        JOIN files f ON f.id = files_fts.file_id
        WHERE files_fts MATCH ? AND f.is_available = 1
        ORDER BY bm25(files_fts, 10.0, 5.0, 2.0, 1.0) ASC LIMIT 20
    ''', (expr,)).fetchall()
ms_old = (time.perf_counter() - t0) * 20
print('Old syntax ms:', ms_old)

# 2. FTS5 column filter syntax {name stem path_tokens} : deep* learning*
t0 = time.perf_counter()
for _ in range(50):
    expr2 = '{name stem path_tokens} : deep* learning*'
    c.execute('''
        SELECT f.id FROM files_fts
        JOIN files f ON f.id = files_fts.file_id
        WHERE files_fts MATCH ? AND f.is_available = 1
        ORDER BY bm25(files_fts, 10.0, 5.0, 2.0, 1.0) ASC LIMIT 20
    ''', (expr2,)).fetchall()
ms_new = (time.perf_counter() - t0) * 20
print('New syntax ms:', ms_new)
print('Speedup:', ms_old / ms_new)

# 3. What if using rowid directly?
con.execute('CREATE INDEX idx_files_stem ON files(stem);')
con.commit()
t0 = time.perf_counter()
for _ in range(50):
    expr3 = '{name stem path_tokens} : deep* learning*'
    c.execute('''
        SELECT f.id, f.name, f.path FROM files_fts
        JOIN files f ON f.id = files_fts.rowid
        WHERE files_fts MATCH ? AND f.is_available = 1
        ORDER BY bm25(files_fts, 10.0, 5.0, 2.0, 1.0) ASC LIMIT 20
    ''', (expr3,)).fetchall()
ms_rowid = (time.perf_counter() - t0) * 20
print('Rowid join ms:', ms_rowid)
