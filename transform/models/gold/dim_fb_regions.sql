{{config(
    materialized='incremental',
    unique_key='region',
    engine='ReplacingMergeTree(created_at)', 
    order_by='(region)'
)}}

SELECT 
    s.region,
    s.country,
    m.region_code,
    m.region_type,
    coalesce(m.macro_region, 'Unknown') as macro_region,
    now() as created_at
FROM {{ source('marketing_analytics_silver', 'stg_fb_ad_daily_location') }} s
LEFT JOIN {{ ref('vietnam_region_mapping') }} m 
    ON trim(s.region) = trim(m.region_name)