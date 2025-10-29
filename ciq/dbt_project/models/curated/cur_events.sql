-- Curated model: Deduplication, cleaning, normalization
-- Input: stg_events
-- Output: Clean, deduplicated table ready for feature engineering

with base as (
    select *,
        md5(concat(customer_id::varchar, '|', event_time::varchar)) as row_id
    from {{ ref('stg_events') }}
),

dedup as (
    select *
    from base
    qualify row_number() over(partition by row_id order by event_time desc) = 1
),

clean as (
    select
        customer_id,
        event_time,
        treated,
        y,
        nullif(age, -1) as age,  -- Convert sentinel value to null
        upper(gender) as gender,  -- Normalize to uppercase
        rfm_score,
        coalesce(prior_7d_spend, 0) as prior_7d_spend,  -- Impute missing with 0
        web_session_cnt
    from dedup
)

select * from clean
