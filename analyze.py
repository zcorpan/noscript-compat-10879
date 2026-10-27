# Rates the clear cases in compare.py's output per pair and writes A2|B|C panels for the rest to
# <out-dir>/review/<idx>.png. Pairs: B vs A2 (Chromium vs Gecko), C vs A2 (9426 vs Gecko),
# C vs B (9426 vs Chromium). A vs A2 is page noise.
# Writes <out-dir>/auto.csv; creates <out-dir>/review.csv (prefilled) if it doesn't exist.
# Usage: analyze.py <out-dir>
import csv, json, os, sys
from PIL import Image, ImageDraw

out_dir = sys.argv[1]
rows = sorted(map(json.loads, open(f'{out_dir}/results.jsonl')), key=lambda r: r['idx'])
PAIRS = [('A2', 'B'), ('A2', 'C'), ('B', 'C')]


def same(r, x, y):
    tr = r.get(f'textRatio{x}{y}')
    px = r.get(f'pix{x}{y}')
    if tr is None:
        return False
    ex, ey = r[x].get('extra') or {}, r[y].get('extra') or {}
    if ex.get('noscriptsRendered') != ey.get('noscriptsRendered'):
        return False
    return tr >= min(r['textRatioAA2'], 0.98) and (px or 0) <= max((r['pixAA2'] or 0) * 1.5, 0.01)


def auto(r):
    if r.get('error'):
        return 'not assessable', r['error'][:80]
    errs = [r[t].get('error') for t in ('A', 'A2', 'B', 'C') if r[t].get('error')]
    if errs:
        return 'not assessable', 'load error: ' + errs[0][:80]
    diffs = [f'{y}vs{x}' for x, y in PAIRS if not same(r, x, y)]
    if not diffs:
        return 'no visible change', 'all pairs within A vs A2 noise'
    return '', 'differs: ' + ' '.join(diffs)


def new_errors(r, x, y):
    before = set(r['A'].get('pageErrors', []) + r[x].get('pageErrors', []))
    return ' | '.join(e[:100] for e in r[y].get('pageErrors', []) if e not in before)[:300]


def categories(r, tag):
    return ' '.join(sorted({h['category'] for h in r.get(tag, {}).get('noscript', [])}))


def panel(r):
    ims = [Image.open(r[t]['shot']) for t in ('A2', 'B', 'C')]
    h = min(1100, max(im.height for im in ims))
    w = sum(im.width for im in ims) + 24
    out = Image.new('RGB', (w, h + 30), 'red')
    x = 0
    d = ImageDraw.Draw(out)
    for t, label, im in zip(('A2', 'B', 'C'), ('Gecko (A2)', 'Chromium-like (B)', '9426 (C)'), ims):
        out.paste(im.crop((0, 0, im.width, min(h, im.height))), (x, 30))
        d.text((x + 8, 8), label, fill='white')
        x += im.width + 12
    out.thumbnail((2000, 1100))
    out.save(f"{out_dir}/review/{r['idx']:03}.png")


os.makedirs(f'{out_dir}/review', exist_ok=True)
rated = []
with open(f'{out_dir}/auto.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['idx', 'rank', 'counters', 'page', 'auto_rating', 'reason', 'cats_A', 'cats_B', 'textRatioAA2',
                'textRatioA2B', 'textRatioA2C', 'textRatioBC', 'pixAA2', 'pixA2B', 'pixA2C', 'pixBC',
                'new_errors_B', 'new_errors_C_vs_B', 'new_errors_C_vs_A2'])
    for r in rows:
        rating, reason = auto(r)
        rated.append((r, rating, reason))
        g = lambda k: r.get(k)
        w.writerow([r['idx'], r['rank'], ' '.join(r['counters']), r['page'], rating, reason,
                    categories(r, 'A'), categories(r, 'B'), g('textRatioAA2'), g('textRatioA2B'),
                    g('textRatioA2C'), g('textRatioBC'), g('pixAA2'), g('pixA2B'), g('pixA2C'), g('pixBC'),
                    new_errors(r, 'A2', 'B') if 'B' in r else '', new_errors(r, 'B', 'C') if 'C' in r else '',
                    new_errors(r, 'A2', 'C') if 'C' in r else ''])
        if not rating:
            try:
                panel(r)
            except Exception as e:
                print('panel failed', r['idx'], e)

if not os.path.exists(f'{out_dir}/review.csv'):
    with open(f'{out_dir}/review.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['idx', 'rank', 'counters', 'page', 'gecko_vs_chromium', 'ff9426_vs_gecko',
                    'ff9426_vs_chromium', 'method', 'note'])
        for r, rating, reason in rated:
            v = rating if rating else ''
            w.writerow([r['idx'], r['rank'], ' '.join(r['counters']), r['page'], v, v, v,
                        'auto' if rating else 'manual', reason if rating else ''])
print(sum(1 for _, rating, _ in rated if not rating), 'pages to review in', f'{out_dir}/review/')
