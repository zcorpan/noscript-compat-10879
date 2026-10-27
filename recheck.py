# Loads one page twice in each of the given modes, waiting 10s each, and saves full-page
# screenshots cropped to <top>..<top+900> side by side, to tell page timing from real changes.
# Usage: recheck.py <firefox> <url> <out.png> <top> <mode> [<mode> ...]
import sys
from PIL import Image
import harness

firefox, url, out, top = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
modes = [int(m) for m in sys.argv[5:]]
br = harness.Browser(firefox, out + '.geckodriver.log')
shots = []
try:
    for mode in modes:
        for run in range(2):
            shot = f'{out}.m{mode}r{run}.png'
            rec = harness.visit(br, url, mode, shot, wait=10000)
            print(mode, run, rec.get('error', ''), rec.get('extra'), [h['category'] for h in rec['noscript']], rec['pageErrors'][:3])
            if 'shot' in rec:
                shots.append(shot)
finally:
    br.quit()
ims = [Image.open(s).crop((0, top, 1366, top + 900)) for s in shots]
grid = Image.new('RGB', (len(ims) * (1366 + 10), 900), 'red')
for k, im in enumerate(ims):
    grid.paste(im, (k * (1366 + 10), 0))
grid.thumbnail((2400, 900))
grid.save(out)
