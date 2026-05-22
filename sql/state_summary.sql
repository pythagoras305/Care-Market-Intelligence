SELECT
    state,
    COUNT(*) AS counties,
    ROUND(AVG(business_opportunity_score), 2) AS avg_opportunity,
    ROUND(AVG(care_gap_score), 2) AS avg_care_gap,
    SUM(CASE WHEN market_action = 'Expand' THEN 1 ELSE 0 END) AS expand_markets,
    SUM(CASE WHEN confidence_level = 'Low' THEN 1 ELSE 0 END) AS low_confidence_counties
FROM scored_counties
GROUP BY state
ORDER BY avg_opportunity DESC;

