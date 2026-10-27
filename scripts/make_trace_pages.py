# Union of the pages that hit in the three detection passes -> nonvisual/pages.jsonl, one row per
# URL with the samples it's in (sample name and idx there), its crawl counters, and the categories it hit.
import json

SAMPLES = [('2026-07-01 top100', '.'), ('2026-10-01 top100', '2026-10-01'), ('2026-10-01 random', '2026-10-01/random')]
pages = {}
for name, d in SAMPLES:
    stratum = {p['idx']: p.get('stratum') for p in map(json.loads, open(f'{d}/pages.jsonl'))}
    for h in map(json.loads, open(f'{d}/hits.jsonl')):
        p = pages.setdefault(h['page'], {'page': h['page'], 'rank': h['rank'], 'samples': [], 'counters': set(), 'detected': set()})
        p['samples'].append({'sample': name, 'idx': h['idx'], **({'stratum': stratum[h['idx']]} if stratum[h['idx']] else {})})
        p['counters'] |= set(h['counters'])
        p['detected'] |= set(h['detected'])
with open('nonvisual/pages.jsonl', 'w') as f:
    for i, p in enumerate(sorted(pages.values(), key=lambda p: (p['rank'], p['page']))):
        f.write(json.dumps({'idx': i, **p, 'counters': sorted(p['counters']), 'detected': sorted(p['detected'])}) + '\n')
print(len(pages), 'pages')
