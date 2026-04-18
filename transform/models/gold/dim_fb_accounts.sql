{{config(
    materialized='incremental',
    unique_key='account_id',
    engine='ReplacingMergeTree(created_at)', 
    order_by='(account_id)'
)}}

SELECT DISTINCT
    account_id,
    account_name,
    created_at
FROM {{ source('marketing_analytics_silver', 'stg_fb_campaign_daily') }}

{% if is_incremental() %}
  -- Chỉ lấy dữ liệu mới hơn thời điểm lớn nhất hiện có trong bảng
  WHERE created_at > (SELECT max(created_at) FROM {{ this }})
{% endif %}