/* Comparable countries in a single year. Never mix latest available years. */
SELECT country, ROUND(spend_ppp) AS spending_ppp,
       treatable AS deaths_per_100k, ROUND(oop_share, 1) AS household_share
FROM complete_observations
WHERE year = 2023
ORDER BY treatable;

/* A balanced before/after comparison. A descriptive change, not a policy effect. */
SELECT a.country, a.treatable AS rate_2010, b.treatable AS rate_2023,
       ROUND(100.0 * (b.treatable / a.treatable - 1), 1) AS change_pct
FROM panel a
JOIN panel b ON a.iso3 = b.iso3 AND b.year = 2023
WHERE a.year = 2010 AND a.treatable IS NOT NULL AND b.treatable IS NOT NULL
ORDER BY change_pct;

/* Missingness must remain visible. */
SELECT year, country_slots, countries_with_mortality,
       country_slots - countries_with_mortality AS missing_mortality
FROM annual_summary
ORDER BY year;
