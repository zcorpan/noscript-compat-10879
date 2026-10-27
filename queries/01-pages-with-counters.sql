-- Pages hitting any of the noscript use counters (Chromium 5857-5861).
-- Result saved to a scratch table (<scratch>.noscriptmarkupwithscriptingdisabled_pages); 180,279,837,849 bytes processed.
SELECT
  page,
  rank,
  ARRAY_AGG(DISTINCT f.feature ORDER BY f.feature) AS use_counters
FROM
  `httparchive.crawl.pages`,
  UNNEST(features) AS f
WHERE
  date = "2026-07-01"
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
