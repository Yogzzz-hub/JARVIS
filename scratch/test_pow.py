import sqlite3
import tempfile
from pathlib import Path

with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    p = f.name

con = sqlite3.connect(p)
con.executescript(Path('jarvis/db/migrations/003_search_index.sql').read_text(encoding='utf-8'))
con.execute("INSERT INTO files (id, path, path_norm, name, name_norm, stem, extension, is_available) VALUES (1, 'C:/a/power_bi_sales_dashboard_1.pbix', 'c:/a/power_bi_sales_dashboard_1.pbix', 'power_bi_sales_dashboard_1.pbix', 'power_bi_sales_dashboard_1.pbix', 'power_bi_sales_dashboard_1', '.pbix', 1);")
con.execute("INSERT INTO files_fts (file_id, name, stem, path_tokens, content) VALUES (1, 'power_bi_sales_dashboard_1.pbix', 'power_bi_sales_dashboard_1', 'users ashok documents power bi sales dashboard 1', 'content');")
con.commit()

expr = '(name:"pow"* OR stem:"pow"* OR path_tokens:"pow"*) AND (name:"1"* OR stem:"1"* OR path_tokens:"1"*)'
cur = con.execute('SELECT file_id, name, stem, path_tokens FROM files_fts WHERE files_fts MATCH ?', (expr,))
rows = cur.fetchall()
print('Matched rows:', len(rows))
for r in rows:
    print('Row:', r)
