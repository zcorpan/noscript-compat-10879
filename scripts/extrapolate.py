# Extrapolates the reviewed ratings to each stratum ((count / sampled) x stratum size), with exact
# binomial (Clopper-Pearson) 95% intervals, and sums them (summed bounds are conservative). Sampled pages that didn't hit in the
# detection pass (absent from review.csv) count as "no visible change", or "not assessable" if the
# detection visit failed to load.
# Prints Markdown tables, one per comparison column of review.csv.
# Usage: extrapolate.py <dir>  (reads <dir>/pages.jsonl and <dir>/out/review.csv)
import collections, csv, json, math, sys

RATINGS = ['broken', 'worse', 'neutral', 'improved', 'no visible change', 'not assessable']
d = sys.argv[1]
pages = [json.loads(l) for l in open(f'{d}/pages.jsonl')]
sizes = {p['stratum']: p['stratum_size'] for p in pages}
reviewed = {int(r['idx']): r for r in csv.DictReader(open(f'{d}/out/review.csv'))}
failed = {r['idx'] for r in map(json.loads, open(f'{d}/out-detect/results.jsonl'))
          if r.get('error') or r['B'].get('error')}


def rating(p, col):
    if p['idx'] in reviewed:
        return reviewed[p['idx']][col]
    return 'not assessable' if p['idx'] in failed else 'no visible change'


COLUMNS = [('gecko_vs_chromium', 'Gecko today vs Chromium'), ('ff9426_vs_gecko', '9426 vs Gecko today'),
           ('ff9426_vs_chromium', '9426 vs Chromium')]


def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def solve(f, target):
    # f is decreasing in p on [0, 1]
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) > target else (lo, mid)
    return lo


def clopper_pearson(k, n):
    lo = 0.0 if k == 0 else solve(lambda p: binom_cdf(k - 1, n, p), 0.975)
    hi = 1.0 if k == n else solve(lambda p: binom_cdf(k, n, p), 0.025)
    return lo, hi


for col, title in COLUMNS:
    ratings = [x for x in RATINGS if any(rating(p, col) == x for p in pages)]
    unknown = [k for k, r in reviewed.items() if r[col] not in RATINGS]
    if unknown:
        sys.exit(f'unrated or unknown {col}: idx {unknown}')
    print(f'### {title}\n')
    print('| Stratum | Pages | Sampled | ' + ' | '.join(x.capitalize() for x in ratings) + ' |')
    print('|---|---|---|' + '---|' * len(ratings))
    totals = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    for stratum in sizes:
        rs = [{'rating': rating(p, col)} for p in pages if p['stratum'] == stratum]
        n, N = len(rs), sizes[stratum]
        counts = collections.Counter(r['rating'] for r in rs)
        cells = []
        for x in ratings:
            k = counts[x]
            lo, hi = clopper_pearson(k, n)
            cells.append(f'{k} (~{k / n * N:,.0f}, {lo * N:,.0f}–{hi * N:,.0f})')
            t = totals[x]
            t[0] += k / n * N
            t[1] += lo * N
            t[2] += hi * N
        print(f'| {stratum} | {N:,} | {n} | ' + ' | '.join(cells) + ' |')
    print(f'| All | {sum(sizes.values()):,} | {len(pages)} | ' + ' | '.join('~{:,.0f} ({:,.0f}–{:,.0f})'.format(*totals[x]) for x in ratings) + ' |')
    print()
