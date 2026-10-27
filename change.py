# The change under test, in one Firefox build (scripts/apply_gecko_patch.py) with three modes of
# dom.html_parser.noscript_mode: 0 = current Gecko, 1 = Chromium-like, 2 = whatwg/html#9426.
# Visits: A and A2 in mode 0, B in mode 1, C in mode 2.

MODE_PREF = 'dom.html_parser.noscript_mode'
MODES = {'A': 0, 'A2': 0, 'B': 1, 'C': 2}
LABELS = {0: 'Gecko', 1: 'Chromium', 2: '9426'}

PREFS = {
    'browser.shell.checkDefaultBrowser': False,
    'datareporting.policy.dataSubmissionEnabled': False,
    'toolkit.telemetry.reportingpolicy.firstRun': False,
}

# Change-specific measurements: noscript elements in the top document and how they render, plus
# counts that move when content inside noscript is (or isn't) parsed as markup.
EXTRA_MEASURE_JS = """
const ns = [...document.querySelectorAll('noscript')];
return {
  noscripts: ns.length,
  noscriptsWithElements: ns.filter(n => n.firstElementChild).length,
  noscriptsRendered: ns.filter(n => n.getClientRects().length).length,
  elements: document.getElementsByTagName('*').length,
  images: document.images.length,
  iframes: document.getElementsByTagName('iframe').length,
};
"""

SANITY_PAGE = 'noscript-modes.html'
SANITY_JS = """
return window.sanityDone.then(r => r);
"""


def classify(r):
    """Change-specific auto-rating for a page analyze.py couldn't rate: (rating, reason) or None."""
    return None
