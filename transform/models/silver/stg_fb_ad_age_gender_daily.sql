{{config(
    materialized='incremental',
    unique_key='surrogate_key',
    engine='ReplacingMergeTree(created_at)', 
    order_by='(surrogate_key)'
)}}

SELECT 
    -- Surrogate key: account_id + ad_id + date_start + age + gender
    concat(
        JSONExtractString(data, 'account_id'), '_',
        JSONExtractString(data, 'ad_id'), '_',
        JSONExtractString(data, 'date_start'), '_',
        JSONExtractString(data, 'age'), '_',
        JSONExtractString(data, 'gender')
    ) as surrogate_key,

    job_id,
    created_at,

    -- Định danh
    JSONExtractString(data, 'account_id')   as account_id,
    JSONExtractString(data, 'account_name') as account_name,
    JSONExtractString(data, 'ad_id')        as ad_id,
    toDate(JSONExtractString(data, 'date_start')) as date_start,
    toDate(JSONExtractString(data, 'date_stop'))  as date_stop,

    -- Chiều phân tích (breakdowns)
    JSONExtractString(data, 'age')    as age,
    JSONExtractString(data, 'gender') as gender,

    -- Chỉ số hiệu suất cơ bản
    JSONExtractFloat(data, 'spend')       as spend,
    JSONExtractFloat(data, 'impressions') as impressions,
    JSONExtractFloat(data, 'reach')       as reach,
    JSONExtractFloat(data, 'clicks')      as clicks,
    JSONExtractFloat(data, 'ctr')         as ctr,
    JSONExtractFloat(data, 'cpc')         as cpc,
    JSONExtractFloat(data, 'cpm')         as cpm,
    JSONExtractFloat(data, 'frequency')   as frequency,

    -- Link clicks
    JSONExtractFloat(data, 'inline_link_clicks')        as inline_link_clicks,
    JSONExtractFloat(data, 'unique_inline_link_clicks')  as unique_inline_link_clicks,
    JSONExtractFloat(data, 'inline_link_click_ctr')     as inline_link_click_ctr,

    -- Actions: Messaging
    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.total_messaging_connection',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as total_messaging_connection,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_welcome_message_view',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as messaging_welcome_message_view,

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

    -- Actions: Engagement
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
            x -> JSONExtractString(x, 'action_type') = 'link_click',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as link_clicks,

    -- Actions: Video
    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'video_view',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as video_view_count,

    -- Video watched actions
    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'video_view',
            JSONExtractArrayRaw(data, 'video_play_actions')
        ),
        'value'
    ) as video_play_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'video_view',
            JSONExtractArrayRaw(data, 'video_thruplay_watched_actions')
        ),
        'value'
    ) as video_thruplay_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'video_view',
            JSONExtractArrayRaw(data, 'video_p25_watched_actions')
        ),
        'value'
    ) as video_p25_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'video_view',
            JSONExtractArrayRaw(data, 'video_p50_watched_actions')
        ),
        'value'
    ) as video_p50_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'video_view',
            JSONExtractArrayRaw(data, 'video_p75_watched_actions')
        ),
        'value'
    ) as video_p75_count,

    -- Cost per action
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
    ) as cost_per_page_engagement

FROM {{ source('facebook_raw', 'raw_fb_age___gender_detailed_report_metrics') }}
{% if is_incremental() %}
  WHERE created_at > (SELECT max(created_at) FROM {{ this }})
{% endif %}