# For pages analyze.py left unrated, finds the "odd" mode (differs from both others) and whether
# the page's hit categories allow that mode to differ: B only for template/windowless parses
# (modes 0 and 2 parse those the same), C for any category (sandbox hiding, DOMParser/XHR parsing,
# windowless serialization), A2 never (it's the same build behavior as B or C per category).
# Usage: triage.py <out-dir>
import csv, sys

PAIRS = {('A2', 'B'): 'BvsA2', ('A2', 'C'): 'CvsA2', ('B', 'C'): 'CvsB'}
WINDOWLESS = {'template-fragment', 'windowless-fragment', 'windowless-write', 'parseHTMLUnsafe'}
for r in csv.DictReader(open(f'{sys.argv[1]}/auto.csv')):
    if r['auto_rating']:
        continue
    diffs = set(r['reason'].split(': ')[1].split())
    differs = lambda x, y: PAIRS.get((x, y), PAIRS.get((y, x))) in diffs
    odd = [m for m in ('A2', 'B', 'C') if all(differs(m, o) for o in ('A2', 'B', 'C') if o != m)]
    cats = set((r['cats_A'] + ' ' + r['cats_B']).split())
    possible = [m for m in odd if m == 'C' or (m == 'B' and cats & WINDOWLESS)]
    print(r['idx'], '|', r['counters'], '|', r['cats_B'], '|', ' '.join(sorted(diffs)), '| odd', ''.join(odd) or '-',
          '| candidate' if possible else '| noise', '|', r['page'][:60])
