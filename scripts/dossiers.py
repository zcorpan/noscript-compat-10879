# Builds one dossier per trace group for code review: the group's row from groups.csv, up to three
# example pages with their trace events in both visits (B = Chromium-like, C = #9426), C-only JS
# errors, and the calling scripts' code around each reported frame (fetched live, beautified).
# Selects every 'review' group plus a seeded sample of the other classes for validating them.
# Scripts are third-party code: dossiers go outside the repo and aren't committed.
# Usage: dossiers.py <out-dir> <seed> <n-none> <n-tracking> <n-hidden> [<reviews.jsonl> to skip reviewed groups, ids prefixed x]
import csv, collections, hashlib, json, os, random, re, subprocess, sys
import jsbeautifier

out_dir, seed = sys.argv[1], sys.argv[2]
n_sample = {'none': int(sys.argv[3]), 'tracking': int(sys.argv[4]), 'hidden': int(sys.argv[5])}
reviewed = {(d['entry'], d['script']) for d in map(json.loads, open(sys.argv[6]))} if len(sys.argv) > 6 else set()
prefix = 'x' if reviewed else 'g'
src_dir = os.path.join(out_dir, 'src')
os.makedirs(src_dir, exist_ok=True)
sys.argv = [sys.argv[0]]
exec(open(os.path.join(os.path.dirname(__file__), 'trace_summary.py')).read().split('\nrows = ')[0])  # script_key, content_kind

groups = list(csv.DictReader(open('nonvisual/groups.csv')))
rng = random.Random(seed)
chosen = [g for g in groups if g['class'] == 'review' and (g['entry'], g['script']) not in reviewed]
for cls, n in n_sample.items():
    pool = sorted((g for g in groups if g['class'] == cls), key=lambda g: (g['entry'], g['script']))
    chosen += rng.sample(pool, min(n, len(pool)))
pages_of = collections.defaultdict(list)
for pg in csv.DictReader(open('nonvisual/page-groups.csv')):
    pages_of[(pg['entry'], pg['script'])].append(int(pg['idx']))
rows = {r['idx']: r for r in map(json.loads, open('nonvisual/results.jsonl'))}
FRAME = re.compile(r'^(.*?)@((?:https?):[^\s]*?)(?::(\d+))?(?::(\d+))?$')


def fetch(url):
    path = os.path.join(src_dir, hashlib.sha1(url.encode()).hexdigest()[:16])
    if not os.path.exists(path):
        subprocess.run(['curl', '-sL', '--max-time', '20', '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:150.0) Gecko/20100101 Firefox/150.0',
                        '-o', path, url], capture_output=True)
    try:
        return open(path, encoding='utf-8', errors='replace').read()
    except FileNotFoundError:
        return ''


def snippet(frame):
    m = FRAME.match(frame)
    if not m:
        return None
    fn, url, line, col = m.group(1), m.group(2), m.group(3), m.group(4)
    text = fetch(url)
    if not text:
        return f'### {frame}\n(could not fetch)\n'
    if line:
        lines = text.split('\n')
        li = min(int(line), len(lines)) - 1
        pos = sum(len(l) + 1 for l in lines[:li]) + max(int(col or 1) - 1, 0)
    else:
        name = fn.split('/')[-1].split('.')[-1] or 'parseFromString'
        idx = [i for i in (text.find(name), text.find('parseFromString'), text.find('innerHTML'), text.find('noscript')) if i >= 0]
        pos = idx[0] if idx else 0
    window = text[max(0, pos - 2500):pos + 2500]
    pretty = jsbeautifier.beautify(window) if '<html' not in window[:200].lower() else window
    return f'### {frame}\n(position {pos} of {len(text)}; {"line/col from stack" if line else "located by name, approximate"})\n```js\n{pretty[:9000]}\n```\n'


def events_for(r, tag, ids):
    return [e for e in r[tag].get('trace', []) if e.get('id') in ids]


index = []
for n, g in enumerate(chosen):
    key = (g['entry'], g['script'])
    gid = f'{prefix}{n:03}'
    parts = [f'# {gid}: {g["entry"]} from {g["script"]}\n', f'Class from the trace: **{g["class"]}**\n',
             '```json\n' + json.dumps({k: g[k] for k in g if k != 'content_examples'}, indent=1) + '\n```\n',
             'Content examples:\n```\n' + g['content_examples'].replace(' || ', '\n') + '\n```\n']
    frames = collections.Counter()
    for idx in pages_of[key][:3]:
        r = rows[idx]
        b_ids = {e['id'] for e in r['B']['trace'] if e['t'] == 'parse' and (e['entry'], script_key(e.get('caller'))) == key}
        c_ids = {e['id'] for e in r['C']['trace'] if e['t'] == 'parse' and (e['entry'], script_key(e.get('caller'))) == key}
        parts.append(f'## Example page {r["page"]}\n')
        for tag, ids in (('B', b_ids), ('C', c_ids)):
            evs = events_for(r, tag, ids)[:40]
            for e in evs:
                for f in (e.get('caller') or [])[:2]:
                    frames[f] += 1
            parts.append(f'{tag} ({"Chromium-like" if tag == "B" else "#9426"}) events:\n```json\n' +
                         '\n'.join(json.dumps(e)[:700] for e in evs) + '\n```\n')
        c_only = [e for e in r['C'].get('errors', []) if e['text'] not in {x['text'] for x in r['B'].get('errors', [])}]
        if c_only:
            parts.append('Errors only in the #9426 visit:\n```json\n' + '\n'.join(json.dumps(e) for e in c_only[:5]) + '\n```\n')
    parts.append('## Code around the reported frames\n')
    for f, _ in frames.most_common(6):
        s = snippet(f)
        if s:
            parts.append(s)
    path = os.path.join(out_dir, f'{gid}.md')
    open(path, 'w').write('\n'.join(parts))
    index.append({'gid': gid, 'class': g['class'], 'entry': g['entry'], 'script': g['script'], 'pages': int(g['pages']), 'file': path})
json.dump(index, open(os.path.join(out_dir, f'index-{prefix}.json' if reviewed else 'index.json'), 'w'), indent=1)
print(len(index), 'dossiers;', collections.Counter(i['class'] for i in index))
