# queries/top100-per-counter.csv -> pages.jsonl: one row per unique page with the counters it hit.
import csv, json, sys

rows = {}
for r in csv.DictReader(open(sys.argv[1])):
    p = rows.setdefault(r['page'], {'page': r['page'], 'rank': int(r['rank']), 'counters': []})
    p['counters'].append(r['use_counter'])
with open(sys.argv[2], 'w') as f:
    for i, p in enumerate(sorted(rows.values(), key=lambda p: (p['rank'], p['page']))):
        f.write(json.dumps({'idx': i, **p}) + '\n')
print(len(rows), 'pages')
