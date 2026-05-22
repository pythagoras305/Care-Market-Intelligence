SELECT
    county,
    state,
    ROUND(business_opportunity_score, 2) AS opportunity,
    ROUND(care_gap_score, 2) AS care_gap,
    market_action,
    confidence_level
FROM market_opportunity
WHERE market_action = 'Expand'
ORDER BY business_opportunity_score DESC
LIMIT 25;

