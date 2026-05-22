SELECT
    confidence_level,
    COUNT(*) AS counties,
    ROUND(AVG(missing_feature_count), 2) AS avg_missing_inputs,
    SUM(CASE WHEN zero_workforce_flag THEN 1 ELSE 0 END) AS zero_workforce_counties,
    SUM(CASE WHEN small_senior_population_flag THEN 1 ELSE 0 END) AS sparse_senior_counties,
    SUM(CASE WHEN wage_fallback_flag THEN 1 ELSE 0 END) AS wage_fallback_counties
FROM data_quality
GROUP BY confidence_level
ORDER BY
    CASE confidence_level
        WHEN 'High' THEN 1
        WHEN 'Medium' THEN 2
        ELSE 3
    END;

