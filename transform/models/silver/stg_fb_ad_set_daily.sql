{{config(
    materialized='incremental',
    unique_key='surrogate_key',
    engine='ReplacingMergeTree(created_at)', 
    order_by='(surrogate_key)'
)}}

SELECT 
    -- Surrogate key: adset_id + date_start
    concat(
        JSONExtractString(data, 'adset_id'), '_',
        JSONExtractString(data, 'date_start')
    ) as surrogate_key,

    job_id,
    created_at,

    -- Định danh
    JSONExtractString(data, 'adset_id')     as adset_id,
    JSONExtractString(data, 'account_id')   as account_id,
    JSONExtractString(data, 'account_name') as account_name,
    toDate(JSONExtractString(data, 'date_start')) as date_start,
    toDate(JSONExtractString(data, 'date_stop'))  as date_stop,

    -- Chỉ số hiệu suất cơ bản
    JSONExtractFloat(data, 'spend')       as spend,
    JSONExtractFloat(data, 'reach')       as reach,
    JSONExtractFloat(data, 'impressions') as impressions,
    JSONExtractFloat(data, 'cpc')         as cpc,
    JSONExtractFloat(data, 'cpm')         as cpm,
    JSONExtractFloat(data, 'ctr')         as ctr,
    JSONExtractFloat(data, 'clicks')      as clicks,
    JSONExtractFloat(data, 'frequency')   as frequency,

    -- ===== ACTIONS =====

    -- Messaging
    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.total_messaging_connection',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as total_messaging_connection,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_first_reply',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as messaging_first_reply,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_user_depth_2_message_send',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as messaging_user_depth_2_message_send,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_conversation_started_7d',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as messaging_conversation_started_7d,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_conversation_replied_7d',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as messaging_conversation_replied_7d,

    -- Engagement
    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'link_click',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as link_clicks,

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
            x -> JSONExtractString(x, 'action_type') = 'comment',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as comment_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'post_reaction',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as post_reaction_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'post',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as post_share_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.post_save',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as post_save_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.post_net_like',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as post_net_like_count,

    -- Video
    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'video_view',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as video_view_count,

    -- ===== COST PER ACTION TYPE =====

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.total_messaging_connection',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_messaging_connection,

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
    ) as cost_per_messaging_first_reply,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_conversation_started_7d',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_messaging_conversation_started_7d

FROM {{ source('facebook_raw', 'raw_fb_ad_set_daily_report_metrics') }}

{% if is_incremental() %}
  -- Chỉ lấy dữ liệu mới hơn thời điểm lớn nhất hiện có trong bảng
  WHERE created_at > (SELECT max(created_at) FROM {{ this }})
{% endif %}
