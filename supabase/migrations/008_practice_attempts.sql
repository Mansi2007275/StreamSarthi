-- StreamSaathi Guardians: practice replay
-- Run in Supabase: SQL Editor -> New query -> paste -> Run. Idempotent: safe to run twice.
-- Run order: after 001-007.
--
-- Replays exist so somebody can keep learning the scale after they have voted on every
-- practice photo. They are scored for encouragement only: XP lives here and nowhere else.
-- Nothing in this table ever reaches points_ledger, validation_votes, skill weights or
-- consensus - a player must not be able to farm voting power by replaying known answers.
-- That is why replays get their own table instead of another row in validation_votes.

create table if not exists practice_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  gold_item_id uuid not null references gold_items(id) on delete cascade,
  score int not null,
  correct boolean not null,
  xp int not null default 0 check (xp >= 0),
  created_at timestamptz default now()
  -- Deliberately no unique constraint: replaying the same photo is the whole point.
);

create index if not exists practice_attempts_user_idx on practice_attempts (user_id, created_at desc);

alter table practice_attempts enable row level security;   -- no policies: backend service key only
