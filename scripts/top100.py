# pages-with-counters.csv (query output, all matching pages) -> top100-per-counter.csv (top 100 by
# rank per counter, same format as the 2026-07-01 sheet), and prints pages per counter.
# Usage: top100.py <pages-with-counters.csv> <top100-per-counter.csv>
import collections, csv, sys

NAMES = {'Template': 'template', 'IframeSandbox': 'iframe', 'XHR': 'XHR', 'DOMParser': 'DOMParser',
         'NoBrowsingContext': 'NoBrowsingContext'}
rows = list(csv.DictReader(open(sys.argv[1])))
per = collections.defaultdict(list)
for r in rows:
    for c in r['use_counters'].split():
        per[NAMES[c]].append((int(r['rank']), r['page']))
print('pages', len(rows))
out = []
for c, lst in per.items():
    print(c, len(lst))
    out += [(rank, page, c) for rank, page in sorted(lst)[:100]]
with open(sys.argv[2], 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['page', 'rank', 'use_counter'])
    for rank, page, c in sorted(out):
        w.writerow([page, rank, c])
