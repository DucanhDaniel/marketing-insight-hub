{{config(
    materialized='incremental',
    unique_key='surrogate_key',
    engine='ReplacingMergeTree(created_at)', 
    order_by='(surrogate_key)'
)}}

SELECT 
    -- Surrogate key: account_id + date_start
    concat(
        JSONExtractString(data, 'account_id'), '_',
        JSONExtractString(data, 'date_start')
    ) as surrogate_key,

    job_id,
    created_at,

    -- Định danh
    JSONExtractString(data, 'account_id')       as account_id,
    JSONExtractString(data, 'account_name')     as account_name,
    JSONExtractString(data, 'account_currency') as account_currency,
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
    JSONExtractFloat(data, 'cost_per_unique_inline_link_click') as cost_per_unique_inline_link_click,

    -- Purchase ROAS
    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'omni_purchase',
            JSONExtractArrayRaw(data, 'purchase_roas')
        ),
        'value'
    ) as purchase_roas,

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
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_user_depth_3_message_send',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as messaging_user_depth_3_message_send,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_user_depth_5_message_send',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as messaging_user_depth_5_message_send,

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

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_block',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as messaging_block,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_order_created_v2',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as messaging_order_created,

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
            x -> JSONExtractString(x, 'action_type') = 'like',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as page_like_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'post',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as post_share_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'photo_view',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as photo_view_count,

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

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.post_unlike',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as post_unlike_count,

    -- Video
    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'video_view',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as video_view_count,

    -- Landing page
    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'landing_page_view',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as landing_page_view_count,

    -- Conversion: Lead
    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'lead',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as lead_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.lead_grouped',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as lead_grouped_count,

    -- Conversion: Purchase
    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'omni_purchase',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as purchase_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'view_content',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as view_content_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'add_to_cart',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as add_to_cart_count,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'initiate_checkout',
            JSONExtractArrayRaw(data, 'actions')
        ),
        'value'
    ) as initiate_checkout_count,

    -- ===== ACTION VALUES (Revenue) =====

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'omni_purchase',
            JSONExtractArrayRaw(data, 'action_values')
        ),
        'value'
    ) as purchase_value,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'add_to_cart',
            JSONExtractArrayRaw(data, 'action_values')
        ),
        'value'
    ) as add_to_cart_value,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'view_content',
            JSONExtractArrayRaw(data, 'action_values')
        ),
        'value'
    ) as view_content_value,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'initiate_checkout',
            JSONExtractArrayRaw(data, 'action_values')
        ),
        'value'
    ) as initiate_checkout_value,

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
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_welcome_message_view',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_messaging_welcome_message_view,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_first_reply',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_messaging_first_reply,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_user_depth_2_message_send',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_messaging_user_depth_2_message_send,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_user_depth_3_message_send',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_messaging_user_depth_3_message_send,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_user_depth_5_message_send',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_messaging_user_depth_5_message_send,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_conversation_started_7d',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_messaging_conversation_started_7d,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_conversation_replied_7d',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_messaging_conversation_replied_7d,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'onsite_conversion.messaging_order_created_v2',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_messaging_order_created,

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
    ) as cost_per_page_engagement,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'post_interaction_gross',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_post_interaction_gross,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'like',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_page_like,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'landing_page_view',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_landing_page_view,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'lead',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_lead,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'omni_purchase',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_purchase,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'view_content',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_view_content,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'add_to_cart',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_add_to_cart,

    JSONExtractFloat(
        arrayFirst(
            x -> JSONExtractString(x, 'action_type') = 'initiate_checkout',
            JSONExtractArrayRaw(data, 'cost_per_action_type')
        ),
        'value'
    ) as cost_per_initiate_checkout

FROM {{ source('facebook_raw', 'raw_fb_account_daily_report_metrics') }}

{% if is_incremental() %}
  WHERE created_at > (SELECT max(created_at) FROM {{ this }})
{% endif %}
