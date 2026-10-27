# Summarizes nonvisual/results.jsonl (trace.py): groups traced parses by (entry point, calling
# script), records what happened to the elements that came from noscript content in the
# Chromium-like visit (B), compares query results with the #9426 visit (C), ties C-only JS errors to
# traced scripts, and gives each group an automatic class:
#   none          nothing observed using the noscript-derived elements
#   hidden        only whole noscript elements reached the live document (hidden in every mode)
#   tracking      noscript content made live is tracking only (pixels, tag-manager iframes)
#   review        anything else (queries that find noscript-derived elements, serialization, text
#                 reads, other content made live, fetches or errors that differ): read the code
# Writes <dir>/groups.csv and <dir>/page-groups.csv. Usage: trace_summary.py [<dir>] (default nonvisual)
import collections, csv, hashlib, json, re, sys
from urllib.parse import urljoin

TRACKING = re.compile(r'googletagmanager\.com/ns\.html|facebook\.com/tr|google-analytics|doubleclick|'
                      r'bat\.bing|analytics|pixel|adsrvr|linkedin\.com/collect|px\.ads|tiktok|snapchat|'
                      r'pinterest\.com/v3|ct\.pinterest|criteo|adnxs|yandex\.ru/watch|mc\.yandex|matomo|piwik|'
                      r'quantserve|scorecardresearch|/collect\b|/tr\b|beacon|track|counter|stat', re.I)


def script_key(frames):
    for f in frames or []:
        m = re.search(r'@?((?:https?|moz-extension|blob):[^\s]*?)(?::\d+){0,2}$', f)
        if m:
            u = m.group(1)
            u = re.sub(r' line \d+ > (eval|Function).*', '', u)
            u = re.sub(r'[.-][0-9a-f]{6,}(?=[.-])', '.<hash>', u)
            u = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<uuid>', u)
            return u
    return '(no JS caller)'


def content_kind(c):
    kinds = set()
    for m in re.finditer(r'<([a-z][a-z0-9]*)\b([^>]*)(?:>|$)', c, re.I):
        tag, attrs = m.group(1).lower(), m.group(2)
        url = re.search(r'(?:src|href)\s*=\s*["\']?([^"\'\s>]+)', attrs, re.I)
        u = url.group(1) if url else ''
        if tag == 'iframe':
            kinds.add('tracking' if TRACKING.search(u) else 'iframe')
        elif tag == 'img':
            tiny = re.search(r'(width|height)\s*=\s*["\']?[01]\b', attrs) or 'display:none' in attrs.replace(' ', '')
            kinds.add('tracking' if tiny or TRACKING.search(u) else 'image')
        elif tag in ('link', 'style'):
            kinds.add('stylesheet' if tag == 'style' or 'stylesheet' in attrs.lower() else 'link-' + (re.search(r'rel\s*=\s*["\']?([\w-]+)', attrs, re.I) or [None, 'other'])[1].lower())
        elif tag in ('script', 'meta', 'video', 'audio', 'object', 'embed', 'form', 'input', 'button', 'select', 'textarea'):
            kinds.add(tag)
        elif tag in ('a',):
            kinds.add('link')
        elif tag in ('picture', 'source'):
            kinds.add('image')
        else:
            kinds.add('markup')
    if not kinds:
        kinds.add('text')
    if kinds - {'tracking'} == {'markup'} or kinds - {'tracking', 'markup'} <= {'link'} and 'markup' in kinds:
        text = re.sub(r'<[^>]+>', ' ', c).strip()
        if text:
            kinds.add('message')
    return kinds


D = sys.argv[1] if len(sys.argv) > 1 else 'nonvisual'
rows = [json.loads(l) for l in open(f'{D}/results.jsonl')]
groups = collections.defaultdict(lambda: {'pages': set(), 'samples': collections.Counter(), 'kinds': collections.Counter(),
                                          'outcomes': collections.Counter(), 'queries': collections.Counter(),
                                          'query_diff': set(), 'live': collections.Counter(), 'entries': set(),
                                          'callers': collections.Counter(), 'content': [], 'errors': set()})
page_groups = []
for r in rows:
    if r.get('error'):
        continue
    B, C = r['B'], r['C']
    bev, cev = B.get('trace', []), C.get('trace', [])
    parses = {e['id']: e for e in bev if e['t'] == 'parse'}
    by_id = collections.defaultdict(list)
    for e in bev:
        if e['t'] != 'parse':
            by_id[e.get('id')].append(e)
    # Query totals in C by (api, selector, top caller frame), to compare with B.
    c_queries = collections.defaultdict(set)
    for e in cev:
        if e['t'] == 'query':
            c_queries[(e['api'], e['sel'], (e.get('caller') or [''])[0])].add(e['total'])
    # Resources fetched in B but not C whose URL is in noscript content seen in either visit.
    urls = {re.sub(r'[?#].*', '', urljoin(r['page'], u)) for e in bev + cev if e['t'] == 'parse'
            for c in e.get('content', []) + e.get('parsed', [])
            for u in re.findall(r'(?:src|href|data-src)\s*=\s*["\']?([^"\'\s>]+)', c, re.I)}
    hashes = {hashlib.sha1(u.encode()).hexdigest()[:12] for u in urls}
    fetch_b = {h for _, h in B.get('resources', []) if h in hashes}
    fetch_c = {h for _, h in C.get('resources', []) if h in hashes}
    c_err = {e['text'] for e in C.get('errors', [])} - {e['text'] for e in B.get('errors', [])}
    keys = set()
    for pid, p in parses.items():
        if not (p.get('inside') or p.get('hoisted') or (p['entry'] == 'XHR' and p.get('noscripts'))):
            continue  # nothing turned into elements in this parse (XHR: source unknown, keep any noscript)
        key = (p['entry'], script_key(p.get('caller')))
        keys.add(key)
        g = groups[key]
        g['pages'].add(r['page'])
        for s in r['samples']:
            g['samples'][s['sample']] += 1
        g['entries'].add(p['entry'])
        g['callers'][(p.get('caller') or [''])[0][:160]] += 1
        for c in p.get('content') or p.get('parsed') or []:
            for k in content_kind(c):
                g['kinds'][k] += 1
            if len(g['content']) < 6 and c[:120] not in [x[:120] for x in g['content']]:
                g['content'].append(c[:200])
        outcomes = set()
        for e in by_id.get(pid, []):
            if e['t'] == 'query':
                if e['derived']:
                    outcomes.add('query')
                    g['queries'][f"{e['api']}({e['sel']})"] += 1
                    ck = (e['api'], e['sel'], (e.get('caller') or [''])[0])
                    if ck in c_queries and e['total'] not in c_queries[ck]:
                        g['query_diff'].add(f"{e['api']}({e['sel']}): {e['total']} vs {sorted(c_queries[ck])}")
            elif e['t'] in ('serialize', 'read-text'):
                outcomes.add(e['t'])
            elif e['t'] == 'insert':
                live = {k: v for k, v in e['found'].items() if k.endswith('-live')}
                if live:
                    outcomes.add('live')
                    for k, v in live.items():
                        g['live'][k] += v
                elif any(k.startswith('noscript') for k in e['found']):
                    outcomes.add('noscript-inserted')
        if fetch_b - fetch_c:
            outcomes.add('fetch')
        sk = key[1]
        for e in C.get('errors', []):
            if e['text'] in c_err and any(sk != '(no JS caller)' and sk.split('/')[-1] in f for f in e['frames']):
                outcomes.add('error')
                g['errors'].add(e['text'][:120])
        if not outcomes:
            outcomes.add('none')
        for o in outcomes:
            g['outcomes'][o] += 1
    for k in keys:
        page_groups.append({'idx': r['idx'], 'page': r['page'], 'entry': k[0], 'script': k[1]})


def klass(g):
    o = set(g['outcomes'])
    risky = o & {'query', 'serialize', 'read-text', 'error'}
    if risky or g['query_diff']:
        return 'review'
    if 'live' in o or 'fetch' in o:
        live_kinds = set(g['kinds']) - {'message', 'markup', 'text'}
        return 'tracking' if live_kinds <= {'tracking'} else 'review'
    if 'noscript-inserted' in o:
        return 'hidden'
    return 'none'


with open(f'{D}/groups.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['entry', 'script', 'class', 'pages', 'samples', 'content_kinds', 'outcomes', 'queries_finding_noscript_elements',
                'query_totals_B_vs_C', 'live_insertions', 'c_only_errors', 'top_callers', 'content_examples'])
    for key, g in sorted(groups.items(), key=lambda kv: -len(kv[1]['pages'])):
        w.writerow([key[0], key[1], klass(g), len(g['pages']), json.dumps(dict(g['samples'])), json.dumps(dict(g['kinds'])),
                    json.dumps(dict(g['outcomes'])), json.dumps(dict(g['queries'].most_common(8))),
                    ' | '.join(sorted(g['query_diff'])[:5]), json.dumps(dict(g['live'])), ' | '.join(sorted(g['errors'])[:3]),
                    ' | '.join(c for c, _ in g['callers'].most_common(3)), ' || '.join(g['content'])])
with open(f'{D}/page-groups.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, ['idx', 'page', 'entry', 'script'])
    w.writeheader()
    w.writerows(page_groups)
cls = collections.Counter(klass(g) for g in groups.values())
pages_by_cls = collections.defaultdict(set)
for key, g in groups.items():
    pages_by_cls[klass(g)] |= g['pages']
print(len(rows), 'pages traced;', len(groups), 'groups:', dict(cls))
print('pages per class:', {k: len(v) for k, v in pages_by_cls.items()})
