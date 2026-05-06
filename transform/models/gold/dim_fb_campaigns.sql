{{config(
    materialized='incremental',
    unique_key='campaign_id',
    engine='ReplacingMergeTree(created_at)', 
    order_by='(campaign_id)'
)}}

SELECT DISTINCT
    campaign_id,
    account_id,
    campaign_name,
    created_at
FROM {{ ref('stg_fb_campaign_daily') }}

{% if is_incremental() %}
  -- Chỉ lấy dữ liệu mới hơn thời điểm lớn nhất hiện có trong bảng
  WHERE created_at > (SELECT max(created_at) FROM {{ this }})
{% endif %}