-- StreamSaathi v4 schema: micro-lessons, One Health, map, seed marker
-- Run in Supabase: SQL Editor -> New query -> paste -> Run. Idempotent: safe to run twice.

-- F10 micro-lessons
create table if not exists lessons (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  observation_id uuid not null references observations(id) on delete cascade,
  indicator_id text not null,
  your_score int,
  expert_score int not null,
  why text not null,
  seen boolean not null default false,
  seen_at timestamptz,
  created_at timestamptz default now(),
  unique (observation_id, indicator_id)          -- one lesson per corrected indicator, safe to retry
);
create index if not exists lessons_user_unseen_idx on lessons (user_id, seen, created_at desc);
alter table lessons enable row level security;
drop policy if exists "own lessons" on lessons;
create policy "own lessons" on lessons for select using (auth.uid() = user_id);

-- F11 One Health result stored on the observation (recomputed on submit and after review)
alter table observations add column if not exists one_health jsonb;

-- F13 mark demo rows so they can be filtered or cleaned
alter table observations add column if not exists is_seed boolean not null default false;

-- F12 map query speed
create index if not exists observations_map_idx on observations (status, trust_score) where lat is not null;
