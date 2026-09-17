import sqlite3
con = sqlite3.connect(':memory:')
con.execute('CREATE VIRTUAL TABLE test_fts USING fts5(name, tokenize="unicode61 separators \'_-. \'");')
con.execute("INSERT INTO test_fts(name) VALUES ('power_bi_sales_dashboard_1.pbix');")
res = con.execute("SELECT * FROM test_fts WHERE test_fts MATCH 'pow* 1*';").fetchall()
print('Matches with separators:', len(res))
