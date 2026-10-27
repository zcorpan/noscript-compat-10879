-- Pages hitting any of the noscript use counters (Chromium 5857-5861), 2026-10-01 desktop crawl.
-- Output: pages-with-counters.csv (all matching pages; top 100 per counter picked by
-- scripts/top100.py). 184,150,971,875 bytes processed.
SELECT
  page,
  rank,
  ARRAY_TO_STRING(ARRAY_AGG(DISTINCT REPLACE(f.feature, "NoscriptMarkupWithScriptingDisabled", "")
    ORDER BY REPLACE(f.feature, "NoscriptMarkupWithScriptingDisabled", "")), " ") AS use_counters
FROM
  `httparchive.crawl.pages`,
  UNNEST(features) AS f
WHERE
  date = "2026-10-01"
  AND client = "desktop"
  AND f.feature IN (
    "NoscriptMarkupWithScriptingDisabledTemplate",
    "NoscriptMarkupWithScriptingDisabledIframeSandbox",
    "NoscriptMarkupWithScriptingDisabledXHR",
    "NoscriptMarkupWithScriptingDisabledDOMParser",
    "NoscriptMarkupWithScriptingDisabledNoBrowsingContext"
  )
GROUP BY
  page,
  rank
ORDER BY
  rank,
  page;
