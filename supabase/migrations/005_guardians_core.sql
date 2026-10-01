-- StreamSaathi Guardians (Track 5) Phase 1: game core
-- Run in Supabase: SQL Editor -> New query -> paste -> Run. Idempotent: safe to run twice.
-- Run order: after 001-004. This is the only migration for Phase 1.

-- ---------------------------------------------------------------- answers
-- How sure the citizen was (Phase 3 asks it), and what the crowd made of the answer.
alter table indicator_answers add column if not exists human_confidence text
  check (human_confidence in ('sure','somewhat','guess'));
alter table indicator_answers add column if not exists crowd_score numeric;
alter table indicator_answers add column if not exists crowd_votes int not null default 0;
alter table indicator_answers add column if not exists crowd_status text not null default 'pending';

-- 'inconclusive' = enough votes, but the crowd landed between agree_max_diff and
-- disagree_min_diff. Without it such answers would sit on 'pending' forever.
alter table indicator_answers drop constraint if exists indicator_answers_crowd_status_check;
alter table indicator_answers add constraint indicator_answers_crowd_status_check
  check (crowd_status in ('pending','agrees','disagrees','inconclusive','not_needed'));

alter table observations add column if not exists crowd_verified boolean not null default false;
alter table profiles add column if not exists onboarded_at timestamptz;

-- ---------------------------------------------------------------- sites
create table if not exists sites (
  id uuid primary key default gen_random_uuid(),
  lat double precision not null,
  lng double precision not null,
  name text,
  created_at timestamptz default now()
);
create index if not exists sites_latlng_idx on sites (lat, lng);
alter table sites enable row level security;   -- no policies: backend service key only

alter table observations add column if not exists site_id uuid references sites(id);
create index if not exists observations_site_idx on observations (site_id, submitted_at desc);

-- The crew that owns an observation. No FK yet: crews land in Phase 7. Set here so the
-- "never vote on your own crew's photo" anti-cheat rule can be enforced from Phase 1.
alter table observations add column if not exists crew_id uuid;
create index if not exists observations_crew_idx on observations (crew_id);

-- ---------------------------------------------------------------- gold items
-- Known expert answers. Used for the practice round and to measure a voter's accuracy.
create table if not exists gold_items (
  id uuid primary key default gen_random_uuid(),
  indicator_id text not null,
  image_path text not null,          -- 'public:/gold/g1.jpg' bundled, or 'storage:<path>' expert-promoted
  expert_score int not null,
  explanation text not null,
  source text not null default 'seed' check (source in ('seed','expert')),
  source_answer_id uuid references indicator_answers(id),
  active boolean not null default true,
  created_at timestamptz default now()
);
create index if not exists gold_items_active_idx on gold_items (indicator_id) where active;
alter table gold_items enable row level security;

-- ---------------------------------------------------------------- votes
create table if not exists validation_votes (
  id uuid primary key default gen_random_uuid(),
  voter_id uuid not null references profiles(id) on delete cascade,
  answer_id uuid references indicator_answers(id) on delete cascade,
  gold_item_id uuid references gold_items(id) on delete cascade,
  score int not null,
  confidence text check (confidence in ('sure','somewhat','guess')),
  is_gold boolean not null,
  correct boolean,                   -- gold: set at once. normal: after consensus or the expert.
  created_at timestamptz default now(),
  check ((answer_id is null) <> (gold_item_id is null)),
  unique (voter_id, answer_id),      -- NULLs are distinct in Postgres, so gold rows don't collide
  unique (voter_id, gold_item_id)
);

-- Denormalised from the gold item / answer at insert time, so per-voter-per-indicator
-- accuracy (the consensus skill weight) is one single-table aggregate, no join.
alter table validation_votes add column if not exists indicator_id text;
-- Snapshot of the voter's skill weight when they voted: consensus stays reproducible.
-- Recomputing it later would silently change results already shown to people.
alter table validation_votes add column if not exists weight numeric;
-- Why a vote was dropped from consensus ('self' | 'same_crew' | 'low_skill'). Kept rather
-- than deleted, so the anti-cheat decision is visible on the expert review screen.
alter table validation_votes add column if not exists excluded_reason text;

create index if not exists votes_voter_indicator_idx on validation_votes (voter_id, indicator_id);
create index if not exists votes_answer_idx on validation_votes (answer_id);
create index if not exists votes_gold_idx on validation_votes (gold_item_id);
alter table validation_votes enable row level security;

-- ---------------------------------------------------------------- points
create table if not exists points_ledger (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  amount int not null check (amount >= 0),     -- fairness: never a negative award
  reason text not null,                        -- stream_check | gold_match | vote_consensus | adopted_bonus
  ref_id uuid not null,                        -- answer / vote / observation id
  status text not null default 'pending' check (status in ('pending','awarded','void')),
  created_at timestamptz default now(),
  settled_at timestamptz,
  unique (user_id, reason, ref_id)             -- idempotent awarding
);
create index if not exists points_user_status_idx on points_ledger (user_id, status);
alter table points_ledger enable row level security;

-- ---------------------------------------------------------------- receipts
create table if not exists receipts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  kind text not null,                 -- verified | crowd_verified | caught_error | used_in_trend | badge | level_up
  message text not null,
  ref_id uuid,
  seen boolean not null default false,
  created_at timestamptz default now()
);
create index if not exists receipts_user_unseen_idx on receipts (user_id, seen, created_at desc);
alter table receipts enable row level security;

-- ---------------------------------------------------------------- badges
create table if not exists user_badges (
  user_id uuid not null references profiles(id) on delete cascade,
  badge_id text not null,
  unlocked_at timestamptz default now(),
  primary key (user_id, badge_id)
);
alter table user_badges enable row level security;

-- ---------------------------------------------------------------- analyst view
-- Reference only, like indicator_disagreement in 004: the backend computes the same
-- numbers in Python (services/game.py) so they stay unit-testable without a database.
create or replace view voter_indicator_accuracy as
select
  v.voter_id,
  v.indicator_id,
  count(*) as gold_votes,
  round(avg((v.correct)::int), 3) as exact_rate,
  round(avg(abs(v.score - g.expert_score)), 3) as mean_abs_error,
  round(avg(v.score - g.expert_score), 3) as mean_signed_error
from validation_votes v
join gold_items g on g.id = v.gold_item_id
where v.is_gold
group by v.voter_id, v.indicator_id;
