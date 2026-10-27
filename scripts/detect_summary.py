# Summarizes out-detect/results.jsonl: per Chromium counter, how many pages still hit in the mode-1
# detection visit, by Gecko category, and the most common calling scripts.
# Usage: detect_summary.py <out-detect> > <out-detect>/summary.md
import collections, json, re, sys

rows = [json.loads(l) for l in open(f'{sys.argv[1]}/results.jsonl')]
# Which Chromium counter each Gecko category corresponds to (sandbox/frame-disabled -> iframe).
CAT_TO_COUNTER = {'template-fragment': 'template', 'windowless-fragment': 'NoBrowsingContext',
                  'windowless-write': 'NoBrowsingContext', 'parseHTMLUnsafe': 'NoBrowsingContext',
                  'DOMParser': 'DOMParser', 'XHR': 'XHR', 'sandbox': 'iframe', 'frame-disabled': 'iframe'}
COUNTERS = ['template', 'NoBrowsingContext', 'DOMParser', 'XHR', 'iframe']


def script_key(caller):
    if not caller:
        return '(no JS caller)'
    u = re.sub(r':\d+$', '', caller)
    u = re.sub(r'[.-][0-9a-f]{6,}(?=[.-])', '.<hash>', u)
    return u


errors = [r for r in rows if r.get('error') or r['B'].get('error')]
print(f'Pages: {len(rows)}; load errors: {len(errors)}\n')
print('| Chromium counter (crawl) | Pages | Still hit same counter | Hit any | By Gecko category |')
print('|---|---|---|---|---|')
for c in COUNTERS:
    sub = [r for r in rows if c in r['counters']]
    same = [r for r in sub if any(CAT_TO_COUNTER.get(h['category']) == c for h in r['B']['noscript'])]
    anyhit = [r for r in sub if r['B']['noscript']]
    cats = collections.Counter(cat for r in sub for cat in {h['category'] for h in r['B']['noscript']})
    print(f'| {c} | {len(sub)} | {len(same)} | {len(anyhit)} | {", ".join(f"{k} {v}" for k, v in cats.most_common())} |')

print('\n## Calling scripts by category (pages)\n')
by = collections.defaultdict(collections.Counter)
for r in rows:
    seen = set()
    for h in r['B']['noscript']:
        k = (h['category'], script_key(h['caller']))
        if k not in seen:
            seen.add(k)
            by[h['category']][k[1]] += 1
for cat, cnt in sorted(by.items(), key=lambda kv: -sum(kv[1].values())):
    print(f'### {cat}\n')
    for k, v in cnt.most_common(25):
        print(f'- {v} {k}')
    print()
