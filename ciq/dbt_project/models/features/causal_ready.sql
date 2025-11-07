-- Causal-ready features: Final preparation for causal inference
-- Input: cur_events
-- Output: Leakage-free, normalized, causal-safe dataset

-- Purpose: Ensure no post-treatment columns, proper categorical encoding,
-- and standardized missing value handling for causal inference.

select
    customer_id,
    event_time,
    treated,
    y,
    age,
    case
        when gender in ('M', 'F', 'U') then gender
        else 'U'  -- Unknown category for invalid values
    end as gender,
    rfm_score,
    prior_7d_spend,
    web_session_cnt
from {{ ref('cur_events') }}
