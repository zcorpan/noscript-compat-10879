# Loads sanity/trace-test.html with trace.js in modes 0, 1 and 2 and prints the trace events, to
# check each entry point and consumer is caught. Usage: trace_sanity.py <firefox> > sanity/trace-modes.txt
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import harness

br = harness.Browser(sys.argv[1], '/tmp/noscript-trace-sanity.log', preload=open(harness.here('trace.js')).read())
url = harness.serve(harness.here('sanity')) + 'trace-test.html'
try:
    for mode in (0, 1, 2):
        br.set_mode(mode)
        br.trace.clear()
        br.driver.switch_to.new_window('tab')
        br.driver.get(url)
        time.sleep(1.5)
        fetched = br.driver.execute_script(
            "return performance.getEntriesByType('resource').map(e => e.name.split('/').pop()).filter(n => n.startsWith('px-'));")
        br.driver.close()
        br.driver.switch_to.window(br.home)
        time.sleep(0.5)
        print(f'## mode {mode}; pixels fetched: {sorted(fetched)}')
        for t in br.trace:
            ev = json.loads(t)
            ev.pop('caller', None)
            ev.pop('doc', None)
            print(json.dumps(ev, sort_keys=True))
finally:
    br.quit()
