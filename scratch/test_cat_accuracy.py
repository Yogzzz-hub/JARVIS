import json
import asyncio
import tempfile
import sqlite3
from pathlib import Path
from jarvis.scripts.bench_search import populate_test_database
from jarvis.memory.search.engine import SearchEngine

with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
    p = f.name
con = sqlite3.connect(p)
populate_test_database(con, 1000)
con.close()
e = SearchEngine(p)

async def check():
    with open('tests/data/search_golden.jsonl', 'r', encoding='utf-8') as f:
        entries = [json.loads(line) for line in f if line.strip()]
    
    cats = {}
    for item in entries:
        cat = item.get('category', 'unknown')
        if cat not in cats:
            cats[cat] = {'total': 0, 'top1': 0, 'top5': 0}
        cats[cat]['total'] += 1
        q = item['query']
        exp = (item.get('expected_file') or '').casefold()
        resp = await e.search(q)
        top = resp.results[0].name.casefold() if resp.results else ''
        names = [r.name.casefold() for r in resp.results[:5]]
        if item.get('is_ambiguous') and resp.is_ambiguous:
            cats[cat]['top1'] += 1
            cats[cat]['top5'] += 1
        elif exp and (exp in top or top in exp):
            cats[cat]['top1'] += 1
            cats[cat]['top5'] += 1
        elif exp and any(exp in n or n in exp for n in names):
            cats[cat]['top5'] += 1

    for cat, d in cats.items():
        t1 = d['top1']
        t5 = d['top5']
        tot = d['total']
        print(f"{cat:<15}: Top-1 {t1}/{tot} ({t1/tot*100:.1f}%), Top-5 {t5}/{tot} ({t5/tot*100:.1f}%)")

asyncio.run(check())
