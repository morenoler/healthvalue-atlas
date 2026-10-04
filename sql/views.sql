CREATE VIEW IF NOT EXISTS annual_summary AS
SELECT year,
       COUNT(*) AS country_slots,
       COUNT(treatable) AS countries_with_mortality,
       COUNT(spend_ppp) AS countries_with_spending,
       AVG(treatable) AS mean_treatable_rate,
       AVG(spend_ppp) AS mean_spend_current_ppp
FROM panel
GROUP BY year;

CREATE VIEW IF NOT EXISTS country_changes AS
SELECT iso3, country, year, treatable,
       treatable - LAG(treatable) OVER (PARTITION BY iso3 ORDER BY year) AS annual_change
FROM panel;

CREATE VIEW IF NOT EXISTS complete_observations AS
SELECT * FROM panel
WHERE treatable IS NOT NULL AND spend_ppp IS NOT NULL
  AND gdp_ppp_constant IS NOT NULL AND age65_pct IS NOT NULL;
