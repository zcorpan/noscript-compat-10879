# Applies harness.scrub_record to existing results.jsonl files in place (compare.py now does this
# before writing). Usage: scrub_results.py <results.jsonl>...
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import harness

for path in sys.argv[1:]:
    rows = [harness.scrub_record(json.loads(l)) for l in open(path)]
    with open(path, 'w') as f:
        f.writelines(json.dumps(r) + '\n' for r in rows)
