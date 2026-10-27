# What the most common calling scripts do with the parsed noscript

From the detection pass (`out-detect/summary.md`), the top calling scripts per category were read
(minified source, not executed). Verdicts are for the noscript content becoming one raw-text node
(Gecko today on the template/windowless paths; everywhere under #9426).

Behavior checks in Chrome Canary and Firefox Nightly on a test origin:
- `template.innerHTML = '<noscript><img src=…></noscript>'`, then append `content` to the live doc:
  Chrome creates the `img` and fetches it; Firefox creates a text node and fetches nothing.
- `createHTMLDocument()` + `write('<noscript><img src=…></noscript><p>x')`: Chrome (scripting flag
  off, noscript in head) hoists the `img` out of the noscript into body; Firefox keeps
  `<noscript>&lt;img …&gt;</noscript>`.

## template-fragment

- Shopline multiplatformpixel, adsninja `init.js`, CMS head/body snippets on two Next.js sites
  (site code, not Next/React), Tiendanube `linkedstore-v2` (`jQueryNuvem.parseHTML`): parse
  tracking/custom-code snippets with `template.innerHTML` and append them to the live doc. Noscript
  stays hidden either way; Chromium today also loads the noscript fallback pixel or GTM `ns.html`
  iframe in addition to the JS one. No visible effect.
- Blazor `blazor.web.js` (`insertMarkup`): same pattern for `MarkupString`. Its enhanced navigation
  uses DOMParser then DOM-merges into `document`, which replaces the live noscript's text with
  elements today in both engines. No visible effect.
- GitHub `include-fragment-element`: imports a login fragment whose noscripts hold "enable
  JavaScript" messages; hidden either way. No effect.

## windowless-fragment / windowless-write

- Transcend `airgap.js` (consent manager): wraps `innerHTML`, `document.write` and friends, parses
  the string with `createHTMLDocument` + `write`, and only if it regulated something re-serializes
  and passes the result on. In Chromium a leading `<noscript><img|iframe>` gets hoisted out of the
  noscript in that doc, so a rewritten string can carry a live `img`/`iframe`. In Gecko today the
  rewritten string carries escaped noscript text (`&lt;img…`). #9426 round-trips exactly. No
  visible effect expected.
- jQuery: only `$.parseHTML(str)` without context and `.load(url + " selector")` use the windowless
  doc (`$(html)` parses in the live doc). Effect depends on the site: moved noscripts stay hidden;
  selectors stop matching elements inside noscript fallbacks.

## DOMParser

- askspot chat widget: parses the host page into markdown for an AI context; noscript content would
  appear as a string. Not visible.
- ruffruff selling periods, Fandom `load.php` (a dev-wiki script): read one specific element. No effect.
- Shopify Dawn-derived `global.js`: section rendering, wishlist and infinite scroll move parsed
  nodes into the live doc (noscript hidden either way) or copy `innerHTML` (round-trips under #9426).
  No visible effect.
- pjax-api: already converts noscripts with element children to raw text after parsing, and
  feature-tests the parser for `head > noscript` raw text. Wants the #9426 behavior.
