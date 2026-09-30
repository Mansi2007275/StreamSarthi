-- StreamSaathi v5: Calibration Mode + Disagreement Heatmap
-- Run in Supabase: SQL Editor -> New query -> paste -> Run. Idempotent: safe to run twice.

-- F14 calibration: a new citizen's starting observer_accuracy comes from 3 practice
-- photos with a known expert answer, instead of the default 0.5.
alter table profiles add column if not exists calibrated_at timestamptz;

-- F15 disagreement heatmap: reference view for ad-hoc SQL/analyst use. The backend
-- computes the same stats in Python (services/heatmap.py) so they stay unit-testable
-- without a live database; this view is not queried by the API itself.
create or replace view indicator_disagreement as
select
  indicator_id,
  count(*) filter (where ai_score is not null) as n,
  round(avg(abs(human_score - ai_score)) filter (where ai_score is not null), 2) as mean_abs_diff,
  round(avg(human_score - ai_score) filter (where ai_score is not null), 2) as mean_bias,
  round(avg((abs(human_score - ai_score) >= 2 and ai_confidence > 0.7)::int)
        filter (where ai_score is not null), 3) as strong_rate,
  round(avg((human_score <> expert_score)::int) filter (where expert_score is not null), 3) as human_wrong_rate,
  round(avg((ai_score <> expert_score)::int) filter (where expert_score is not null and ai_score is not null), 3) as ai_wrong_rate
from indicator_answers
group by indicator_id;
