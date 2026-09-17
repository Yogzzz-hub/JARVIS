import sqlite3
import time
import tempfile
from jarvis.scripts.bench_search import populate_test_database

with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    p = f.name
con = sqlite3.connect(p)
populate_test_database(con, 10000)
c = con.cursor()

# Test 1: Wildcard on all content terms
t0 = time.perf_counter()
for _ in range(50):
    c.execute("""
        SELECT f.id FROM files_fts
        JOIN files f ON f.id = files_fts.file_id
        WHERE files_fts MATCH 'content:"gradient"* AND content:"descent"*'
        LIMIT 10
    """).fetchall()
ms_wild = (time.perf_counter() - t0) * 20
print('Wildcard all:', ms_wild, 'ms')

# Test 2: Standard terms on content
t0 = time.perf_counter()
for _ in range(50):
    c.execute("""
        SELECT f.id FROM files_fts
        JOIN files f ON f.id = files_fts.file_id
        WHERE files_fts MATCH 'content:"gradient" content:"descent"'
        LIMIT 10
    """).fetchall()
ms_exact = (time.perf_counter() - t0) * 20
print('Standard terms:', ms_exact, 'ms')
print('Speedup:', ms_wild / ms_exact)
