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
    JSONExtractString(data, 'campaign_name') as campaign_name

FROM {{ source('facebook_raw', 'raw_fb_metadata_shared') }}

WHERE 
  (
    JSONExtractString(data, '_template') = 'Ad Set Daily Report'
  )

{% if is_incremental() %}
  AND created_at > (SELECT max(created_at) FROM {{ this }})
{% endif %}
