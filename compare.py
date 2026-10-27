# Usage:
#   compare.py detect <firefox> <pages.jsonl> <out-dir> [--concurrency N]
#     Loads each page once in mode 1 (Chromium-like, the superset of documents parsed with the
#     scripting flag off) and records NOSCRIPT_MARKUP lines: which pages still hit, how, and from where.
#   compare.py compare <firefox> <pages.jsonl> <out-dir> [--concurrency N]
#     Loads each page in A, A2 (mode 0), B (mode 1), C (mode 2) with screenshots.
# Appends one JSON line per page to <out-dir>/results.jsonl; pages already there are skipped.
import argparse, concurrent.futures, json, os, queue, sys, threading
import change, harness

ap = argparse.ArgumentParser()
ap.add_argument('cmd', choices=['detect', 'compare', 'sanity'])
ap.add_argument('firefox')
ap.add_argument('pages', nargs='?')
ap.add_argument('out_dir', nargs='?')
ap.add_argument('--concurrency', type=int, default=3)
ap.add_argument('--timeout', type=int, default=180)
args = ap.parse_args()


def sanity():
    url = harness.serve(harness.here('sanity')) + change.SANITY_PAGE
    br = harness.Browser(args.firefox, '/tmp/noscript-sanity-geckodriver.log')
    print('Firefox', br.version, flush=True)
    out = {}
    try:
        for mode in (0, 1, 2):
            br.set_mode(mode)
            br.driver.switch_to.new_window('tab')
            br.driver.get(url)
            out[mode] = br.driver.execute_async_script(
                'const done = arguments[arguments.length - 1]; window.sanityDone.then(done);')
            br.driver.close()
            br.driver.switch_to.window(br.home)
        out['log'] = br.log_lines(0)
    finally:
        br.quit()
    return out


if args.cmd == 'sanity':
    res = sanity()
    for k in res[0]:
        print(f'{k}:\n  0 {res[0][k]}\n  1 {res[1][k]}\n  2 {res[2][k]}')
    for l in res['log']:
        print(l)
    sys.exit(0)

os.makedirs(f'{args.out_dir}/shots', exist_ok=True)
os.makedirs(f'{args.out_dir}/logs', exist_ok=True)
results_path = f'{args.out_dir}/results.jsonl'
done = set()
if os.path.exists(results_path):
    done = {r['page'] for r in map(json.loads, open(results_path))}
rows = [json.loads(l) for l in open(args.pages)]
todo = queue.Queue()
for r in rows:
    if r['page'] not in done:
        todo.put(r)
lock = threading.Lock()


def run_page(br, r):
    idx = r['idx']
    if args.cmd == 'detect':
        return {**r, 'B': harness.visit(br, r['page'], 1)}
    visits = {}
    for tag in ('A', 'A2', 'B', 'C'):
        visits[tag] = harness.visit(br, r['page'], change.MODES[tag], f"{args.out_dir}/shots/{idx}-{tag}.png")
    a, a2, b, c = visits['A'], visits['A2'], visits['B'], visits['C']
    return {**r, **visits,
            'textRatioAA2': harness.text_ratio(a, a2), 'textRatioA2B': harness.text_ratio(a2, b),
            'textRatioA2C': harness.text_ratio(a2, c), 'textRatioBC': harness.text_ratio(b, c),
            'pixAA2': harness.pixel_diff(a.get('shot'), a2.get('shot')),
            'pixA2B': harness.pixel_diff(a2.get('shot'), b.get('shot')),
            'pixA2C': harness.pixel_diff(a2.get('shot'), c.get('shot')),
            'pixBC': harness.pixel_diff(b.get('shot'), c.get('shot'))}


def worker(n):
    log = f'{args.out_dir}/logs/geckodriver-{n}.log'
    br = harness.Browser(args.firefox, log)
    pool = concurrent.futures.ThreadPoolExecutor(1)
    while True:
        try:
            r = todo.get_nowait()
        except queue.Empty:
            break
        fut = pool.submit(run_page, br, r)
        try:
            res = fut.result(timeout=args.timeout)
        except Exception as e:
            # A hung page: kill this Firefox and start over with a fresh one.
            res = {**r, 'error': f'{type(e).__name__}: {harness.scrub(str(e))[:200]}' or 'timeout'}
            try:
                br.driver.service.process.kill()
            except Exception:
                pass
            pool.shutdown(wait=False)
            pool = concurrent.futures.ThreadPoolExecutor(1)
            br = harness.Browser(args.firefox, log)
        with lock:
            with open(results_path, 'a') as f:
                f.write(json.dumps(harness.scrub_record(res)) + '\n')
            hits = sorted({h['category'] for tag in ('A', 'A2', 'B', 'C') for h in res.get(tag, {}).get('noscript', [])})
            print(r['idx'], r['page'][:70], hits, res.get('pixA2B'), res.get('pixA2C'), res.get('error', ''), flush=True)
    br.quit()


threads = [threading.Thread(target=worker, args=(n,)) for n in range(args.concurrency)]
for t in threads:
    t.start()
for t in threads:
    t.join()
