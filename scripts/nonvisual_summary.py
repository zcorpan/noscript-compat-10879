# Merges the trace groups (nonvisual/groups.csv), the code-review verdicts (nonvisual/reviews.jsonl)
# and the targeted checks into per-page non-visual verdicts for #9426 vs Chromium and vs Gecko, and
# extrapolates the 2026-10-01 random sample like scripts/extrapolate.py.
# Groups without a review take their automatic class: none -> none, tracking -> invisible,
# hidden -> invisible (every hidden group whose inserted noscripts hold form controls, labels, links,
# metadata or stylesheets was reviewed). A page's verdict is the most significant one among its
# groups (user-facing > benign > invisible > none). Pages that hit in detection but whose trace visit
# had no JS-driven parse with noscript-derived elements count as none if their only hits were in
# sandboxed documents (no script runs there; the visual check covers them) or the hit was an XHR
# document no script read, else 'not traced'.
# Writes nonvisual/verdicts.csv and nonvisual/summary.md.
import collections, csv, json, math, sys

ORDER = ['none', 'invisible', 'benign', 'user-facing', 'not traced']


def norm(v):
    return 'user-facing' if v in ('user-visible', 'unclear') else v


groups = {(r['entry'], r['script']): r for r in csv.DictReader(open('nonvisual/groups.csv'))}
reviews = {(d['entry'], d['script']): d for d in map(json.loads, open('nonvisual/reviews.jsonl'))}
verdict = {}
for key, g in groups.items():
    if key in reviews:
        d = reviews[key]
        vc, vg = norm(d['verdict_vs_chromium']), norm(d['verdict_vs_gecko'])
        note = d.get('override_note') or ''
        if d.get('override_vs_chromium'):
            vc = d['override_vs_chromium']
        if d.get('override_vs_gecko'):
            vg = d['override_vs_gecko']
        verdict[key] = (vc, vg, 'review', note)
    else:
        auto = {'none': 'none', 'tracking': 'invisible', 'hidden': 'invisible'}[g['class']]
        verdict[key] = (auto, 'none' if g['entry'] not in ('DOMParser', 'XHR', 'parseHTMLUnsafe') else auto, 'auto', '')

page_keys = collections.defaultdict(set)
for pg in csv.DictReader(open('nonvisual/page-groups.csv')):
    page_keys[int(pg['idx'])].add((pg['entry'], pg['script']))
traced = {r['idx']: r for r in map(json.loads, open('nonvisual/results.jsonl'))}
pages = [json.loads(l) for l in open('nonvisual/pages.jsonl')]
rows = []
for p in pages:
    keys = page_keys.get(p['idx'], set())
    if keys:
        vc = max((verdict[k][0] for k in keys), key=ORDER.index)
        vg = max((verdict[k][1] for k in keys), key=ORDER.index)
    elif set(p['detected']) <= {'sandbox', 'frame-disabled'}:
        vc = vg = 'none'
    elif (traced.get(p['idx'], {}).get('B', {}).get('noscript') and
          {h['category'] for h in traced[p['idx']]['B']['noscript']} == {'XHR'} and
          not any(e['t'] == 'parse' for e in traced[p['idx']]['B'].get('trace', []))):
        vc = vg = 'none'  # the XHR document was parsed but no script read responseXML/response
    else:
        vc = vg = 'not traced'
    rows.append({'idx': p['idx'], 'page': p['page'], 'samples': ' '.join(f"{s['sample']}#{s['idx']}" for s in p['samples']),
                 'detected': ' '.join(p['detected']), 'groups': len(keys), 'vs_chromium': vc, 'vs_gecko': vg,
                 'traced_error': traced.get(p['idx'], {}).get('error', '')})
with open('nonvisual/verdicts.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, list(rows[0]))
    w.writeheader()
    w.writerows(rows)


def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def solve(f, target):
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) > target else (lo, mid)
    return lo


def cp(k, n):
    return (0.0 if k == 0 else solve(lambda p: binom_cdf(k - 1, n, p), 0.975),
            1.0 if k == n else solve(lambda p: binom_cdf(k, n, p), 0.025))


out = ['# Non-visual verdicts', '']
by_sample = collections.defaultdict(list)
for r, p in zip(rows, pages):
    for s in p['samples']:
        by_sample[s['sample']].append((r, s))
for sample in ('2026-07-01 top100', '2026-10-01 top100', '2026-10-01 random'):
    out += [f'## {sample} (pages that hit in detection: {len(by_sample[sample])})', '',
            '| Comparison | ' + ' | '.join(ORDER) + ' |', '|---|' + '---|' * len(ORDER)]
    for comp in ('vs_chromium', 'vs_gecko'):
        c = collections.Counter(r[comp] for r, _ in by_sample[sample])
        out.append(f'| #9426 {comp.replace("_", " ")} | ' + ' | '.join(str(c[o]) for o in ORDER) + ' |')
    out.append('')
# Extrapolation over the random sample: pages without a detection hit count as none.
strata = {}
for p in map(json.loads, open('2026-10-01/random/pages.jsonl')):
    strata.setdefault(p['stratum'], [p['stratum_size'], {}])[1][p['idx']] = 'none'
for r, s in by_sample['2026-10-01 random']:
    strata[s['stratum']][1][s['idx']] = r
out += ['## Extrapolated to the 59,711 pages with a counter hit (2026-10-01 random sample)', '',
        'Sampled pages without a live detection hit count as none. ~estimate (95% interval).', '']
for comp in ('vs_chromium', 'vs_gecko'):
    out += [f'### #9426 {comp.replace("_", " ")}', '', '| Stratum | Pages | Sampled | ' + ' | '.join(ORDER) + ' |', '|---|---|---|' + '---|' * len(ORDER)]
    tot = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    for name, (size, members) in strata.items():
        vals = [m if isinstance(m, str) else m[comp] for m in members.values()]
        n = len(vals)
        cells = []
        for o in ORDER:
            k = vals.count(o)
            lo, hi = cp(k, n)
            cells.append(f'{k} (~{k / n * size:,.0f}, {lo * size:,.0f}–{hi * size:,.0f})')
            t = tot[o]
            t[0] += k / n * size; t[1] += lo * size; t[2] += hi * size
        out.append(f'| {name} | {size:,} | {n} | ' + ' | '.join(cells) + ' |')
    out.append(f'| All | {sum(s for s, _ in strata.values()):,} | {sum(len(m) for _, m in strata.values())} | ' +
               ' | '.join('~{:,.0f} ({:,.0f}–{:,.0f})'.format(*tot[o]) for o in ORDER) + ' |')
    out.append('')
open('nonvisual/summary.md', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
