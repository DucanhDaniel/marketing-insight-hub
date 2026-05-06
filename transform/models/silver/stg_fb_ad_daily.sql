{{config(
    materialized='incremental',
    unique_key='surrogate_key',
    engine='ReplacingMergeTree(created_at)', 
    order_by='(surrogate_key)'
)}}

SELECT 
    concat(JSONExtractString(data, 'id'), '_', JSONExtractString(data, 'date_start')) as surrogate_key,
    job_id, 
    created_at,
    JSONExtractString(data, 'id') as ad_id,
    JSONExtractString(data, 'account_id') as account_id,
    JSONExtractString(data, 'account_name') as account_name,
    JSONExtractString(data, 'campaign_id') as campaign_id,
    JSONExtractString(data, 'campaign_name') as campaign_name,
    toDate(JSONExtractString(data, 'date_start')) as date_start,
    toDate(JSONExtractString(data, 'date_stop')) as date_stop,


    JSONExtractFloat(data, 'spend') as spend,
    JSONExtractFloat(data, 'reach') as reach,
    JSONExtractFloat(data, 'impressions') as impressions,
    JSONExtractFloat(data, 'cpc') as cpc,
    JSONExtractFloat(data, 'cpm') as cpm,
    JSONExtractFloat(data, 'ctr') as ctr,
    JSONExtractFloat(data, 'clicks') as clicks,
    JSONExtractFloat(data, 'frequency') as frequency,
    JSONExtractFloat(data, 'cost_per_unique_inline_link_click') as cost_per_unique_inline_link_click,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'post_engagement',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as post_engagement_count,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'page_engagement',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as page_engagement,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_welcome_message_view',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as onsite_conversion_messaging_welcome_message,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'comment',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as comment_count,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'video_view',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as video_view_count,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'post_reaction',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as post_reaction_count


FROM {{ source('facebook_raw', 'raw_fb_ad_daily_report_metrics') }}

{% if is_incremental() %}
  -- Chỉ lấy dữ liệu mới hơn thời điểm lớn nhất hiện có trong bảng
  WHERE created_at > (SELECT max(created_at) FROM {{ this }})
{% endif %}