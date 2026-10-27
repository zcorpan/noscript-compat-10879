# Per-counter summary of detection and comparison results -> out/summary.md
import csv, json, collections
pages = [json.loads(l) for l in open('pages.jsonl')]
det = {r['idx']: r for r in map(json.loads, open('out-detect/results.jsonl'))}
cmp_ = {r['idx']: r for r in map(json.loads, open('out/results.jsonl'))}
rev = {int(r['idx']): r for r in csv.DictReader(open('out/review.csv'))}
COUNTERS = ['template', 'NoBrowsingContext', 'DOMParser', 'XHR', 'iframe']
out = ['| Counter (crawl) | Pages | Hit in detection | Hit again in comparison | 9426 vs Gecko/Chromium: worse | neutral | no visible change |', '|---|---|---|---|---|---|---|']
for c in COUNTERS + ['any']:
    sub = [p for p in pages if c == 'any' or c in p['counters']]
    hit = [p for p in sub if det[p['idx']]['B']['noscript']]
    again = [p for p in hit if cmp_.get(p['idx']) and cmp_[p['idx']]['B'].get('noscript')]
    rat = collections.Counter(rev[p['idx']]['ff9426_vs_gecko'] for p in hit)
    out.append(f"| {c} | {len(sub)} | {len(hit)} | {len(again)} | {rat['worse']} | {rat['neutral']} | {rat['no visible change']} |")
# Noscripts with element children in the top document (moved in from a parse with the flag off).
moved = collections.Counter()
for i, r in cmp_.items():
    a2, b, cc = (r[t].get('extra') or {} for t in ('A2', 'B', 'C'))
    if (b.get('noscriptsWithElements') or 0) > (a2.get('noscriptsWithElements') or 0):
        moved['B>A2'] += 1
    if (a2.get('noscriptsWithElements') or 0) > (cc.get('noscriptsWithElements') or 0):
        moved['A2>C'] += 1
    if any((r[t].get('extra') or {}).get('noscriptsRendered') for t in ('A2', 'B', 'C')):
        moved['rendered:' + ''.join(t for t in ('A2', 'B', 'C') if (r[t].get('extra') or {}).get('noscriptsRendered'))] += 1
out.append('')
out.append('Top-document noscripts with element children (moved in from a parse with the flag off):')
out.append(f"- more in Chromium-like (B) than Gecko (A2): {moved['B>A2']} pages")
out.append(f"- more in Gecko (A2) than 9426 (C): {moved['A2>C']} pages")
out.append('Pages with a rendered top-document noscript: ' + ', '.join(f'{k} {v}' for k, v in moved.items() if k.startswith('rendered')))
open('out/summary.md', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
