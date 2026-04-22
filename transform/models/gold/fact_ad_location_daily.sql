{{config(
    materialized='incremental',
    unique_key='surrogate_key',
    engine='ReplacingMergeTree(created_at)', 
    order_by='(surrogate_key)'
)}}

SELECT
    surrogate_key,
    created_at,
    ad_id,
    date_start,
    date_stop,
    region, 
    spend,
    impressions,
    cpc,
    cpm,
    ctr,
    clicks,
    total_messaging_connection
    
FROM {{ source('marketing_analytics_silver', 'stg_fb_ad_daily_location') }}

{% if is_incremental() %}
  -- Chỉ lấy dữ liệu mới hơn thời điểm lớn nhất hiện có trong bảng
  WHERE created_at > (SELECT max(created_at) FROM {{ this }})
{% endif %}