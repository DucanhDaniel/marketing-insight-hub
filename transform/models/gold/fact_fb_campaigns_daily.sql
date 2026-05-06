{{config(
    materialized='incremental',
    unique_key='surrogate_key',
    engine='ReplacingMergeTree(created_at)', 
    order_by='(surrogate_key)'
)}}

SELECT
    surrogate_key,
    created_at,
    account_id,
    campaign_id,
    date_start,
    date_stop,
    spend,
    reach,
    impressions,
    cpc,
    cpm,
    ctr,
    clicks,
    frequency,
    cost_per_unique_inline_link_click,
    post_engagement_count AS post_engagement,
    page_engagement,
    comment_count,
    video_view_count,
    post_reaction_count,
    onsite_conversion_messaging_welcome_message as message_count
    
FROM {{ ref('stg_fb_campaign_daily') }}

{% if is_incremental() %}
  -- Chỉ lấy dữ liệu mới hơn thời điểm lớn nhất hiện có trong bảng
  WHERE created_at > (SELECT max(created_at) FROM {{ this }})
{% endif %}