{{config(
    materialized='incremental',
    unique_key='id',
    engine='ReplacingMergeTree(created_at)', 
    order_by='(id)',
    incremental_strategy='delete+insert'
)}}

SELECT 
    job_id, 
    created_at,
    JSONExtractString(data, 'id') as id,
    JSONExtractString(data, 'name') as name,
    JSONExtractString(data, 'campaign_id') as campaign_id,
    JSONExtractString(data, 'campaign_name') as campaign_name,
    JSONExtractString(data, 'adset_id') as adset_id,
    JSONExtractString(data, 'adset_name') as adset_name,
    JSONExtractString(data, 'creative_id') as creative_id,
    JSONExtractString(data, 'creative_name') as creative_name,
    JSONExtractString(data, 'creative_body') as creative_body,
    JSONExtractString(data, 'creative_title') as creative_title,
    JSONExtractString(data, 'creative_thumbnail_raw_url') as creative_thumbnail_url,  
    JSONExtractString(data, 'creative_link') as creative_link_url,  
    JSONExtractString(data, 'status') as "status",
    JSONExtractString(data, 'page_name') as page_name,
    JSONExtractString(data, 'actor_id') as actor_id

FROM {{ source('facebook_raw', 'raw_fb_metadata_shared') }}

WHERE 
  JSONExtractString(data, '_template') = 'LOCATION_DETAILED_REPORT'

{% if is_incremental() %}
  AND created_at > (SELECT max(created_at) FROM {{ this }})
{% endif %}
