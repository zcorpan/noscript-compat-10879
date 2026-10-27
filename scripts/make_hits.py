# <dir>/out-detect/results.jsonl -> <dir>/hits.jsonl: pages with any NOSCRIPT_MARKUP line in the
# detection visit, with the Gecko categories that hit.
# Usage: make_hits.py <dir>
import json, sys

d = sys.argv[1]
with open(f'{d}/hits.jsonl', 'w') as f:
    for r in sorted(map(json.loads, open(f'{d}/out-detect/results.jsonl')), key=lambda r: r['idx']):
        cats = sorted({h['category'] for h in r['B'].get('noscript', [])})
        if cats:
            f.write(json.dumps({k: r[k] for k in ('idx', 'page', 'rank', 'counters')} | {'detected': cats}) + '\n')
