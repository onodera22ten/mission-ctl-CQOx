-- Staging model: Type casting and initial standardization
-- Input: staged.parquet from ciq/data/staged/
-- Output: Typed view for downstream transformations

select
    cast(customer_id as bigint) as customer_id,
    cast(event_time as timestamp) as event_time,
    cast(treated as integer) as treated,
    cast(y as double) as y,
    cast(age as smallint) as age,
    cast(gender as varchar) as gender,
    cast(rfm_score as real) as rfm_score,
    cast(prior_7d_spend as real) as prior_7d_spend,
    cast(web_session_cnt as integer) as web_session_cnt
from read_parquet('../data/staged/staged.parquet')
