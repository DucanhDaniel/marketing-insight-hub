{{config(
    materialized='incremental',
    unique_key='surrogate_key',
    engine='ReplacingMergeTree(created_at)', 
    order_by='(surrogate_key)'
)}}

SELECT 
    concat(JSONExtractString(data, 'account_id'), '_', JSONExtractString(data, 'ad_id'), '_', JSONExtractString(data, 'date_start'), '_', JSONExtractString(data, 'region')) as surrogate_key,
    job_id, 
    created_at,
    JSONExtractString(data, 'account_id') as account_id,
    JSONExtractString(data, 'account_name') as account_name,
    JSONExtractString(data, 'ad_id') as ad_id,
    toDate(JSONExtractString(data, 'date_start')) as date_start,
    toDate(JSONExtractString(data, 'date_stop')) as date_stop,


    JSONExtractFloat(data, 'spend') as spend,
    JSONExtractFloat(data, 'impressions') as impressions,
    JSONExtractFloat(data, 'cpc') as cpc,
    JSONExtractFloat(data, 'cpm') as cpm,
    JSONExtractFloat(data, 'ctr') as ctr,
    JSONExtractFloat(data, 'clicks') as clicks,
    JSONExtractFloat(data, 'inline_link_clicks') as inline_link_clicks,
    JSONExtractFloat(data, 'inline_link_click_ctr') as inline_link_click_ctr,
    JSONExtractString(data, 'region') as region,
    JSONExtractString(data, 'country') as country,


    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.total_messaging_connection',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as total_messaging_connection,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'link_click',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as link_clicks,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'page_engagement',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as page_engagement,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'post_engagement',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as post_engagement_count,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'post_interaction_gross',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as post_interaction_gross_count,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'post_interaction_net',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as post_interaction_net_count,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_user_depth_2_message_send',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as onsite_conversion_messaging_user_depth_2_message_send,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_first_reply',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as onsite_conversion_messaging_first_reply,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.post_net_like',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as onsite_conversion_post_net_like,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_conversation_replied_7d',
        JSONExtractArrayRaw(data, 'actions')
      ),
      'value'
    ) as onsite_conversion_messaging_conversation_replied_7d,

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
    ) as post_reaction_count,

    -- Cost per action types
    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.total_messaging_connection',
        JSONExtractArrayRaw(data, 'cost_per_action_type')
      ),
      'value'
    ) as cost_per_total_messaging_connection,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'video_view',
        JSONExtractArrayRaw(data, 'cost_per_action_type')
      ),
      'value'
    ) as cost_per_video_view,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'link_click',
        JSONExtractArrayRaw(data, 'cost_per_action_type')
      ),
      'value'
    ) as cost_per_link_click,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'post_interaction_gross',
        JSONExtractArrayRaw(data, 'cost_per_action_type')
      ),
      'value'
    ) as cost_per_post_interaction_gross,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_user_depth_2_message_send',
        JSONExtractArrayRaw(data, 'cost_per_action_type')
      ),
      'value'
    ) as cost_per_messaging_user_depth_2_message_send,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_conversation_replied_7d',
        JSONExtractArrayRaw(data, 'cost_per_action_type')
      ),
      'value'
    ) as cost_per_messaging_conversation_replied_7d,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'post_engagement',
        JSONExtractArrayRaw(data, 'cost_per_action_type')
      ),
      'value'
    ) as cost_per_post_engagement,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'page_engagement',
        JSONExtractArrayRaw(data, 'cost_per_action_type')
      ),
      'value'
    ) as cost_per_page_engagement,

    JSONExtractFloat(
      arrayFirst(
        x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_first_reply',
        JSONExtractArrayRaw(data, 'cost_per_action_type')
      ),
      'value'
    ) as cost_per_messaging_first_reply


FROM {{ source('facebook_raw', 'raw_fb_location_detailed_report_metrics') }}

{% if is_incremental() %}
  -- Chỉ lấy dữ liệu mới hơn thời điểm lớn nhất hiện có trong bảng
  WHERE created_at > (SELECT max(created_at) FROM {{ this }})
{% endif %}