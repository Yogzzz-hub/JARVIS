import json
import asyncio
import tempfile
import sqlite3
from pathlib import Path
from jarvis.memory.search.engine import SearchEngine
from jarvis.memory.search.tokenizer import path_tokens_string

with open('tests/data/search_golden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    p = f.name

con = sqlite3.connect(p)
con.executescript(Path('jarvis/db/migrations/003_search_index.sql').read_text(encoding='utf-8'))
now_ns = 1789644962000000000

seen = set()
files_rows = []
fts_rows = []
for i, item in enumerate(entries, 1):
    ef = item.get('expected_file')
    if ef and ef.casefold() not in seen:
        seen.add(ef.casefold())
        ext = Path(ef).suffix.casefold()
        stem = Path(ef).stem.casefold()
        path = f'C:/Users/ashok/Documents/{ef}'
        ptokens = path_tokens_string(path)
        files_rows.append((i, path, path.lower(), 'C:/Users/ashok/Documents', ef, ef.lower(), stem, ext, 1024, now_ns, 1, 1))
        fts_rows.append((i, ef, stem, ptokens, f'content for {stem}'))

con.executemany('INSERT INTO files (id, path, path_norm, parent_path, name, name_norm, stem, extension, size_bytes, modified_ns, is_available, open_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', files_rows)
con.executemany('INSERT INTO files_fts (file_id, name, stem, path_tokens, content) VALUES (?, ?, ?, ?, ?)', fts_rows)
con.commit()
con.close()

e = SearchEngine(p)

async def test():
    top1 = 0
    top5 = 0
    misses = []
    for item in entries:
        q = item['query']
        exp = (item.get('expected_file') or '').casefold()
        resp = await e.search(q)
        top_name = resp.results[0].name.casefold() if resp.results else 'NONE'
        names = [r.name.casefold() for r in resp.results[:5]]
        if item.get('is_ambiguous') and resp.is_ambiguous:
            top1 += 1
            top5 += 1
        elif exp and (exp == top_name or exp in top_name or top_name in exp):
            top1 += 1
            top5 += 1
        elif exp and any(exp == n or exp in n or n in exp for n in names):
            top5 += 1
        else:
            misses.append((q, exp, top_name, names[:3]))
    print(f'Top-1: {top1}/{len(entries)} ({top1/len(entries)*100:.1f}%)')
    print(f'Top-5: {top5}/{len(entries)} ({top5/len(entries)*100:.1f}%)')
    print(f'Total misses: {len(misses)}')
    for q, exp, top, top3 in misses[:5]:
        print(f'Query: {q!r} | Expected: {exp!r} | Top-1: {top!r} | Top-3: {top3}')

asyncio.run(test())
