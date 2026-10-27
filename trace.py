# Traces what scripts do with markup parsed inside <noscript> (trace.js) on every page that hit in a
# detection pass. Each page is visited in mode 1 (Chromium-like, B) and mode 2 (#9426, C): load,
# wait 3s, scroll to the bottom in steps, wait 3s. Records the trace events, hashed URLs of fetched
# resources, JS errors with their top stack frames, and the NOSCRIPT_MARKUP log lines.
# Usage: trace.py <firefox> <pages.jsonl> <out-dir> [--concurrency N]
# Appends one JSON line per page to <out-dir>/results.jsonl; pages already there are skipped.
import argparse, concurrent.futures, hashlib, json, os, queue, re, threading, time
import harness

ap = argparse.ArgumentParser()
ap.add_argument('firefox')
ap.add_argument('pages')
ap.add_argument('out_dir')
ap.add_argument('--concurrency', type=int, default=4)
ap.add_argument('--timeout', type=int, default=150)
args = ap.parse_args()
os.makedirs(f'{args.out_dir}/logs', exist_ok=True)
results_path = f'{args.out_dir}/results.jsonl'
done = {json.loads(l)['idx'] for l in open(results_path)} if os.path.exists(results_path) else set()
todo = queue.Queue()
for r in map(json.loads, open(args.pages)):
    if r['idx'] not in done:
        todo.put(r)
TRACE_JS = open(harness.here('trace.js')).read()
lock = threading.Lock()


def strip(u):
    return re.sub(r'[?#].*', '', u)


def origin(u):
    m = re.match(r'[a-z][a-z0-9+.-]*://[^/?#]*', u or '', re.I)
    return m.group(0) if m else ''


def trace_visit(br, url, mode):
    d = br.driver
    br.set_mode(mode)
    br.errors.clear(); br.error_stacks.clear(); br.console.clear(); br.trace.clear()
    rec = {'mode': mode}
    offset = br.log_offset()
    resources = []
    try:
        d.switch_to.new_window('tab')
        try:
            d.get(url)
        except Exception as e:
            if 'Timeout' not in type(e).__name__:
                raise
            rec['loadTimeout'] = True
        time.sleep(3)
        for _ in range(15):
            at_end = d.execute_script(
                'window.scrollBy(0, innerHeight); return innerHeight + scrollY >= document.documentElement.scrollHeight - 2;')
            time.sleep(0.3)
            if at_end:
                break
        time.sleep(3)
        resources = d.execute_script(
            "return performance.getEntriesByType('resource').map(e => [e.initiatorType, e.name]);") or []
        rec['extra'] = d.execute_script("""
          const ns = [...document.querySelectorAll('noscript')];
          return {noscripts: ns.length, noscriptsWithElements: ns.filter(n => n.firstElementChild).length,
                  elements: document.getElementsByTagName('*').length};""")
    except Exception as e:
        rec['error'] = harness.scrub(str(e).splitlines()[0] if str(e) else type(e).__name__)[:300]
    finally:
        try:
            d.close()
            d.switch_to.window(br.home)
        except Exception as e:
            rec.setdefault('error', 'close failed: ' + harness.scrub(str(e))[:200])
    time.sleep(0.5)
    events = []
    for t in br.trace:
        try:
            events.append(json.loads(t))
        except ValueError:
            pass
    # Fetched resources as hashes of URL without query, so trace_summary.py can match them against
    # URLs in noscript content from either visit without the URLs being recorded.
    rec['resources'] = sorted({(kind, hashlib.sha1(strip(name).encode()).hexdigest()[:12]) for kind, name in resources})
    for ev in events:
        if 'doc' in ev:
            ev['doc'] = origin(ev['doc'])
    rec['trace'] = events
    rec['noscript'] = br.log_lines(offset)
    rec['errors'] = br.error_stacks[:20]
    return rec


def worker(n):
    log = f'{args.out_dir}/logs/geckodriver-{n}.log'
    br = harness.Browser(args.firefox, log, preload=TRACE_JS)
    pool = concurrent.futures.ThreadPoolExecutor(1)
    while True:
        try:
            r = todo.get_nowait()
        except queue.Empty:
            break
        fut = pool.submit(lambda: {**r, 'B': trace_visit(br, r['page'], 1), 'C': trace_visit(br, r['page'], 2)})
        try:
            res = fut.result(timeout=args.timeout)
        except Exception as e:
            res = {**r, 'error': f'{type(e).__name__}: {harness.scrub(str(e))[:200]}'}
            try:
                br.driver.service.process.kill()
            except Exception:
                pass
            pool.shutdown(wait=False)
            pool = concurrent.futures.ThreadPoolExecutor(1)
            br = harness.Browser(args.firefox, log, preload=TRACE_JS)
        with lock:
            with open(results_path, 'a') as f:
                f.write(harness.CC_HOST.sub(r'\1.<cc>', json.dumps(harness.scrub_record(res))) + '\n')
            b = res.get('B', {})
            print(r['idx'], r['page'][:60], len(b.get('trace', [])), len(res.get('C', {}).get('trace', [])),
                  res.get('error', ''), flush=True)
    br.quit()


threads = [threading.Thread(target=worker, args=(n,)) for n in range(args.concurrency)]
for t in threads:
    t.start()
for t in threads:
    t.join()
