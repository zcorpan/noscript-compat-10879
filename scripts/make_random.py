# Seeded random sample of N pages per stratum from pages-with-counters.csv. Each page goes in the
# stratum of its rarest counter (iframe, XHR, NoBrowsingContext, template, DOMParser), so strata
# are disjoint and sum to all matching pages. Writes pages.jsonl format plus stratum and its size.
# Usage: make_random.py <pages-with-counters.csv> <out.jsonl> <seed> <n>
import collections, csv, hashlib, json, sys

NAMES = {'Template': 'template', 'IframeSandbox': 'iframe', 'XHR': 'XHR', 'DOMParser': 'DOMParser',
         'NoBrowsingContext': 'NoBrowsingContext'}
ORDER = ['iframe', 'XHR', 'NoBrowsingContext', 'template', 'DOMParser']
src, out_path, seed, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
strata = collections.defaultdict(list)
for r in csv.DictReader(open(src)):
    counters = sorted(NAMES[c] for c in r['use_counters'].split())
    strata[min(counters, key=ORDER.index)].append({'page': r['page'], 'rank': int(r['rank']), 'counters': counters})
picked = []
for name in ORDER:
    rows = sorted(strata[name], key=lambda r: hashlib.sha256((r['page'] + seed).encode()).hexdigest())
    picked += [{**r, 'stratum': name, 'stratum_size': len(rows)} for r in rows[:n]]
    print(name, len(rows), min(n, len(rows)))
with open(out_path, 'w') as f:
    for i, p in enumerate(sorted(picked, key=lambda p: (ORDER.index(p['stratum']), p['rank'], p['page']))):
        f.write(json.dumps({'idx': i, **p}) + '\n')
