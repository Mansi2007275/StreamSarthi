-- StreamSaathi Guardians Phase 6: Adopt-a-Stream
-- Run in Supabase: SQL Editor -> New query -> paste -> Run. Idempotent: safe to run twice.
-- Run order: after 001-005. This is the only migration for Phase 6.

create table if not exists site_adoptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  site_id uuid not null references sites(id) on delete cascade,
  adopted_at timestamptz not null default now(),
  released_at timestamptz          -- null = still adopted
);

-- One ACTIVE adoption per person per site. A partial unique index rather than a plain
-- unique constraint, so releasing and re-adopting later is allowed and the old row stays
-- as history instead of being overwritten.
create unique index if not exists site_adoptions_active_uniq
  on site_adoptions (user_id, site_id)
  where released_at is null;

-- "My adopted sites" is the hot read, and it only ever wants the active ones.
create index if not exists site_adoptions_user_active_idx
  on site_adoptions (user_id)
  where released_at is null;

create index if not exists site_adoptions_site_idx on site_adoptions (site_id);

alter table site_adoptions enable row level security;   -- no policies: backend service key only
