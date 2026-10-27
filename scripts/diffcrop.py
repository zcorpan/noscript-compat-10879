# For pages flagged in <out-dir>/auto.csv, crops each differing pair (X|Y) around the bounding box
# of the changed pixels into <out-dir>/review/<idx>-<Y>vs<X>.png.
# Usage: diffcrop.py <out-dir>
import csv, json, sys
from PIL import Image, ImageChops

out_dir = sys.argv[1]
rows = {r['idx']: r for r in map(json.loads, open(f'{out_dir}/results.jsonl'))}
for a in csv.DictReader(open(f'{out_dir}/auto.csv')):
    if a['auto_rating']:
        continue
    r = rows[int(a['idx'])]
    for pair in a['reason'].split(': ')[1].split():
        y, x = pair.split('vs')
        try:
            ix, iy = Image.open(r[x]['shot']).convert('RGB'), Image.open(r[y]['shot']).convert('RGB')
        except Exception:
            continue
        w, h = min(ix.width, iy.width), min(ix.height, iy.height)
        diff = ImageChops.difference(ix.crop((0, 0, w, h)), iy.crop((0, 0, w, h))).convert('L').point(lambda v: 255 if v > 16 else 0)
        box = diff.getbbox()
        if not box:
            box = (0, min(ix.height, iy.height) - 400, w, min(ix.height, iy.height))
        l, t, rr, b = box
        t, b = max(0, t - 80), min(max(ix.height, iy.height), b + 80, t + 1200)
        cx, cy = ix.crop((0, t, ix.width, min(b, ix.height))), iy.crop((0, t, iy.width, min(b, iy.height)))
        out = Image.new('RGB', (cx.width + cy.width + 12, max(cx.height, cy.height, 1)), 'red')
        out.paste(cx, (0, 0))
        out.paste(cy, (cx.width + 12, 0))
        out.thumbnail((2000, 1000))
        out.save(f"{out_dir}/review/{int(a['idx']):03}-{y}vs{x}.png")
        print(a['idx'], pair, 'box', box, 'heights', ix.height, iy.height)
