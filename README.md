# Compat impact of the noscript scripting flag (whatwg/html#10879, whatwg/html#9426)

Proposed change (#9426): the HTML parser's scripting flag, which decides whether `<noscript>`
content is raw text or markup, depends only on whether the user disabled JavaScript in the browser.
Today it's off for documents without a script-enabled window or with sandboxed scripts, and engines
disagree on which ones (#10879). Here, 9426 also covers noscript serialization and the UA
`noscript { display: none }` rule.

| Parse | Chromium | Gecko today | 9426 |
|---|---|---|---|
| `template.innerHTML`, innerHTML etc. in windowless docs (`createHTMLDocument`, template contents, DOMParser docs) | markup | raw text, serialized escaped | raw text |
| `document.write` in a windowless doc | markup | raw text, serialized escaped | raw text |
| `DOMParser`, `Document.parseHTMLUnsafe`, XHR `responseXML` | markup | markup | raw text |
| sandboxed iframe or CSP `sandbox` without `allow-scripts` | markup, shown | markup, shown | raw text, hidden |

Verified with `sanity/noscript-modes.html` in Chrome Canary 158.0.8110.0 and Firefox Nightly 161
(`sanity/chrome-canary.txt`, `sanity/firefox-nightly.txt`).

## Summary

- Sample: the top 100 pages by rank for each of Chromium's five noscript use counters in the
  2026-07-01 desktop crawl (499 unique pages; 54k pages hit any counter). It isn't random, so
  nothing is extrapolated.
- 287 of 499 pages still parsed markup inside noscript with the flag off when loaded live
  (`out-detect/`).
- Gecko today vs Chromium: no visible difference on any of the 287 pages.
- 9426 vs Gecko today (same as vs Chromium): 2 pages worse, 2 neutral, 283 no visible change. All
  four are in the iframe (sandbox) bucket:
  - Worse: [dominikaner-braunschweig.de/gottesdienste](https://www.dominikaner-braunschweig.de/gottesdienste)
    embeds `<iframe sandbox="">` of a page whose only no-JS content is
    `<noscript><img src="kreuz-glorificatio.jpg"></noscript>`; the image disappears.
  - Worse: [mancity.bg](https://mancity.bg/) embeds mancity.com/news in
    `sandbox="allow-same-origin"`; lazy-loaded thumbnails rely on noscript `<img>` fallbacks and
    become placeholders.
  - Neutral: two jd.viaversion.com Jenkins javadoc pages, served with `Content-Security-Policy:
    sandbox allow-same-origin`, lose the "JavaScript is disabled on your browser." banner. Page
    scripts don't run either way.
- No breakage in the template, NoBrowsingContext, DOMParser, or XHR buckets. Parsed noscripts that
  end up in the live document stay hidden either way. The difference is in fetches: on 37 pages
  Chromium-like parsing moves noscripts with element children (per `libraries.md`, typically
  tracking pixels and GTM `ns.html` iframes) into the live document, where they load; on 6 pages Gecko does the same via DOMParser.
  What the most common calling scripts do is in `libraries.md`. One of them (pjax-api) already
  converts parsed noscripts to raw text itself.

## 1. HTTP Archive

- `queries/01-pages-with-counters.sql`: pages on the 2026-07-01 crawl, desktop client, root and
  secondary pages, with any of `NoscriptMarkupWithScriptingDisabled{Template,IframeSandbox,XHR,DOMParser,NoBrowsingContext}`
  (Chromium 5857–5861, added in
  [chromium 48fbd23480f5f](https://chromium.googlesource.com/chromium/src/+/48fbd23480f5f000313d5fe2c37794450f5fdb08)).
  They're counted in `HTMLTreeBuilder::ProcessToken` when the flag is off and a start tag, comment,
  non-`</noscript>` end tag, or character reference shows up inside an open noscript. Template = a
  fragment parse with a `template` context; NoBrowsingContext = any other windowless doc;
  IframeSandbox = a doc with a frame and scripting off.
- `queries/02-top100-per-counter.sql` → `queries/top100-per-counter.csv`: top 100 by rank per counter.
- `pages.jsonl`: 499 unique pages (`scripts/make_pages.py`).

## 2. Live comparison

All three behaviors run in one Firefox build (local build of mozilla-firefox main `gecko-base.txt`
plus `gecko.patch`, made with `scripts/apply_gecko_patch.py`), switched by
`dom.html_parser.noscript_mode`: 0 = Gecko today, 1 = Chromium-like (flag off for any doc without a
script-enabled window, as in Blink's `HTMLParserOptions`), 2 = 9426. Script execution in sandboxed
documents is unchanged. The patch also logs `NOSCRIPT_MARKUP` lines (Blink's counter condition,
minus character references) with the parse category, document URL and JS caller. Sanity check
(`sanity/patched-mode*.txt`): mode 0 matches Firefox Nightly and mode 1 matches Chrome Canary on all
16 probes; mode 2 gives raw text everywhere, consistent serialization, and a hidden noscript in
sandboxed iframes.

Harness: Selenium 4.51 + geckodriver 0.37.1 with WebDriver BiDi, headless, 1366x768 (`harness.py`).
Each visit opens a new tab, waits 3s after load, records text, scroll size, noscript counts (top
document), JS errors and log lines, and takes a full-page screenshot (cropped to 4000px).

- Detection (`compare.py detect`, `out-detect/`): every page once in mode 1, which turns the flag off
  for a superset of what modes 0 and 2 do, so it catches every page a comparison could affect.
  `out-detect/summary.md` breaks hits down by category and calling script.

  | Counter (crawl) | Pages | Hit again | By Gecko category |
  |---|---|---|---|
  | template | 100 | 53 | template-fragment 52, DOMParser 1 |
  | NoBrowsingContext | 100 | 52 | windowless-fragment 42, windowless-write 8, DOMParser 6 |
  | DOMParser | 100 | 80 | DOMParser 80 |
  | XHR | 100 | 37 | XHR 34, DOMParser 23 |
  | iframe | 100 | 66 | sandbox 66 (most common documents: youtube.com 18, facebook.com 13) |

- Comparison (`compare.py compare`, `out/`): the 287 hits, each in A and A2 (mode 0, noise), B
  (mode 1) and C (mode 2). `analyze.py` rates a pair "no visible change" when the text and the
  screenshot are within A vs A2 noise and the rendered noscript count is the same. For the
  DOMParser, XHR and sandbox paths modes 0 and 1 are identical, so B vs A2 there is a second
  noise sample. 27 pages differed in some pair and were reviewed by eye (`out/review/`, crops
  around the changed pixels from `scripts/diffcrop.py`). Seven were rechecked with two 10s loads
  per mode (`recheck.py`, `out/recheck/`), and the 3 affected pages were screenshotted in Chrome
  Canary (`out/chrome/chrome-affected.png`; the mancity.com frame didn't load in headless Chrome).
  Ratings with notes: `out/review.csv`; per-counter totals: `out/summary.md`.

  | Counter (crawl) | Hits | Worse | Neutral | No visible change |
  |---|---|---|---|---|
  | template | 53 | 0 | 0 | 53 |
  | NoBrowsingContext | 52 | 0 | 0 | 52 |
  | DOMParser | 80 | 0 | 0 | 80 |
  | XHR | 37 | 0 | 0 | 37 |
  | iframe | 66 | 2 | 2 | 62 |

  The ratings are 9426 vs Gecko today; 9426 vs Chromium gives the same, and Gecko vs Chromium has
  no visible change on all 287 pages. JS exceptions that appeared in only one mode (3 pages) look
  like page noise: two were in B on DOMParser pages, where modes 0 and 1 are identical, and the one
  C-only exception (shop.tvsmotor.com) didn't reproduce in 3 more loads per mode.

## Not covered

- Pages with no hit when loaded live (212 of 499): the page changed, the hit needs interaction or
  logged-in state, or it was character-reference-only (counted by Chromium, not logged here).
- 54k pages hit the counters; this checks the top-ranked 100 per counter, not a random sample.
- Effects that aren't visible: tracking pixels and GTM `ns.html` iframes inside noscript stop
  loading under 9426 where Chromium loads them today (37 pages); scripts that query elements inside
  parsed noscripts (see `libraries.md`).
- Users with JavaScript disabled, and WebKit.

## Reproduce

```sh
python3 scripts/make_pages.py queries/top100-per-counter.csv pages.jsonl
# Firefox: worktree at gecko-base.txt, python3 scripts/apply_gecko_patch.py <worktree>, ./mach build
python3 -m venv .venv && .venv/bin/pip install selenium pillow
.venv/bin/python compare.py sanity "$FIREFOX"
.venv/bin/python compare.py detect "$FIREFOX" pages.jsonl out-detect --concurrency 6
python3 scripts/detect_summary.py out-detect > out-detect/summary.md
# hits.jsonl: pages with any NOSCRIPT_MARKUP line in out-detect/results.jsonl
.venv/bin/python compare.py compare "$FIREFOX" hits.jsonl out --concurrency 6
.venv/bin/python analyze.py out && .venv/bin/python scripts/diffcrop.py out
python3 scripts/summary.py
```

Live pages change, so a rerun won't match exactly. Screenshots (`out*/shots/`) aren't committed.
