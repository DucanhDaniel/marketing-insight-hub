{{config(
    materialized='incremental',
    unique_key='campaign_id'
)}}

SELECT job_id, created_at,
    JSONExtractString(data, 'account_id') as account_id,
    JSONExtractString(data, 'account_name') as account_name,
    JSONExtractString(data, 'id') as campaign_id,
    JSONExtractString(data, 'name') as campaign_name,
    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'post_reaction',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as post_reaction_count,
    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'post_engagement',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as post_engagement_count,
    toDate(JSONExtractString(data, 'date_start')) as date_start,
    toDate(JSONExtractString(data, 'date_stop')) as date_stop
FROM {{ source('facebook_raw', 'raw_fb_campaign_overview_report') }}

{% if is_incremental() %}
  -- Chỉ lấy dữ liệu mới hơn thời điểm lớn nhất hiện có trong bảng
  WHERE created_at > (SELECT max(created_at) FROM {{ this }})
{% endif %}