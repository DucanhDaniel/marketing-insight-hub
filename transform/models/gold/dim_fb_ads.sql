{{config(
    materialized='incremental',
    unique_key='ad_id',
    engine='ReplacingMergeTree(created_at)', 
    order_by='(ad_id)'
)}}

SELECT DISTINCT
    campaign_id,
    adset_id,
    id as ad_id,
    name as ad_name,
    creative_id,
    creative_name,
    creative_body,
    creative_title,
    creative_thumbnail_url,
    creative_link_url,
    "status",
    page_name,
    actor_id,
    created_at
FROM {{ ref('stg_fb_ad_metadata') }}

{% if is_incremental() %}
  -- Chỉ lấy dữ liệu mới hơn thời điểm lớn nhất hiện có trong bảng
  WHERE created_at > (SELECT max(created_at) FROM {{ this }})
{% endif %}