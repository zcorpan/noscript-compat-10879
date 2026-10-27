-- Top 100 pages by rank per counter, from query 01's result. Output: top100-per-counter.csv. 5,498,652 bytes processed.
SELECT
  page,
  rank,
  CASE use_counter
    WHEN "NoscriptMarkupWithScriptingDisabledTemplate" THEN "template"
    WHEN "NoscriptMarkupWithScriptingDisabledIframeSandbox" THEN "iframe"
    WHEN "NoscriptMarkupWithScriptingDisabledXHR" THEN "XHR"
    WHEN "NoscriptMarkupWithScriptingDisabledDOMParser" THEN "DOMParser"
    WHEN "NoscriptMarkupWithScriptingDisabledNoBrowsingContext" THEN "NoBrowsingContext"
  END AS use_counter
FROM
  `<scratch>.noscriptmarkupwithscriptingdisabled_pages`,
  UNNEST(use_counters) AS use_counter
QUALIFY
  ROW_NUMBER() OVER (
    PARTITION BY use_counter
    ORDER BY rank, page
  ) <= 100
ORDER BY
  rank,
  page;
