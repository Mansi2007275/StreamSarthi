-- StreamSaathi v3 schema: expert review + tamper-evident audit log
-- Run in Supabase: SQL Editor -> New query -> paste -> Run. Idempotent: safe to run twice.

alter table observations add column if not exists reviewed_by uuid references profiles(id);
alter table observations add column if not exists reviewed_at timestamptz;
alter table observations add column if not exists review_note text;

create table if not exists audit_events (
  id bigint generated always as identity primary key,
  observation_id uuid not null references observations(id),   -- no cascade: audited data is not deleted
  actor_id uuid references profiles(id),
  event text not null,
  payload jsonb not null default '{}',
  prev_hash text not null,
  hash text not null,
  created_at timestamptz not null,
  unique (observation_id, prev_hash)       -- two events cannot share a parent: detects forks and races
);
create index if not exists audit_obs_idx on audit_events (observation_id, id);
alter table audit_events enable row level security;   -- no policies: only the backend service key can access it

create or replace function public.audit_append_only() returns trigger language plpgsql as $$
begin raise exception 'audit_events is append-only'; end; $$;
drop trigger if exists audit_no_change on audit_events;
create trigger audit_no_change before update or delete on audit_events
for each row execute function public.audit_append_only();

create index if not exists observations_review_idx on observations (status, trust_score);

-- Make a demo expert account (run after the account has signed up once):
-- update profiles set role = 'expert' where id = (select id from auth.users where email = 'expert@demo.com');
