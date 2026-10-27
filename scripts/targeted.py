# Targeted checks in modes 0 (Gecko), 1 (Chromium-like) and 2 (#9426) for groups the code review
# flagged; each loads the page, waits, and evaluates a check. Usage: targeted.py <firefox> > nonvisual/targeted.txt
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import harness

CHECKS = [
    ('equity.wwu.edu search label (g132)', 'https://equity.wwu.edu/', 1, """
      const label = document.querySelector('wwu-search .search-form label[for=search-box]') || [...document.querySelectorAll('label[for=search-box]')].pop();
      const all = [...document.querySelectorAll('[id=search-box]')];
      return {searchBoxIds: all.length, inNoscript: all.map(e => !!e.closest('noscript')),
              labelFound: !!label, labelControlInNoscript: !!(label && label.control && label.control.closest('noscript')),
              labelControlIsVisibleInput: !!(label && label.control && label.control.getClientRects().length)};"""),
    ('everythingfor420 cart drawer default button (g131)', 'https://everythingfor420.com/', 1, """
      const form = document.getElementById('CartDrawer-Form');
      const submits = [...document.querySelectorAll('button, input[type=submit], input[type=image]')].filter(b => b.form === form && b.type === 'submit');
      return {form: !!form, submitButtons: submits.length,
              defaultButton: submits[0] ? {text: submits[0].textContent.trim().slice(0, 30), inNoscript: !!submits[0].closest('noscript')} : null};"""),
    ('vivianfestas GTM error (g035)', 'https://www.vivianfestas.com.br/descartavel', 3, None),
    ('ec.jal.co.jp jQuery error (g022)', 'https://ec.jal.co.jp/shop/e/ehokkaido/', 3, None),
]
br = harness.Browser(sys.argv[1], '/tmp/noscript-targeted.log')
try:
    for name, url, runs, js in CHECKS:
        print(f'## {name}')
        for mode in (0, 1, 2):
            for run in range(runs):
                br.set_mode(mode)
                br.errors.clear()
                br.driver.switch_to.new_window('tab')
                try:
                    br.driver.get(url)
                except Exception:
                    pass
                time.sleep(6)
                out = br.driver.execute_script(js) if js else None
                errs = [e[:90] for e in br.errors if 'firstChild' in e or 'jQuery is not defined' in e]
                br.driver.close()
                br.driver.switch_to.window(br.home)
                print(f'mode {mode} run {run}:', json.dumps(out) if js else '', 'errors:', errs[:2])
finally:
    br.quit()
