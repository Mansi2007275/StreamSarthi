-- StreamSaathi v1 schema
-- Run in Supabase: SQL Editor -> New query -> paste -> Run.
-- v2/v3 columns (trust_score, expert_score, ...) already exist so later versions need no breaking migration.

create extension if not exists pgcrypto;

create table if not exists profiles (
  id uuid primary key references auth.users on delete cascade,
  display_name text,
  role text not null default 'citizen' check (role in ('citizen','expert','admin')),
  observer_accuracy numeric default 0.5,
  created_at timestamptz default now()
);

create table if not exists observations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id) on delete cascade,
  lat double precision,
  lng double precision,
  status text not null default 'draft'
    check (status in ('draft','submitted','needs_review','verified','corrected','rejected')),
  trust_score numeric,            -- v2
  trust_breakdown jsonb,          -- v2
  created_at timestamptz default now(),
  submitted_at timestamptz
);

create table if not exists indicator_answers (
  id uuid primary key default gen_random_uuid(),
  observation_id uuid not null references observations(id) on delete cascade,
  indicator_id text not null,
  human_score int,
  ai_score int,
  ai_confidence numeric,
  ai_reason text,
  ai_evidence jsonb,
  used_ai_answer boolean default false,
  photo_path text,
  photo_quality jsonb,            -- v2
  flags text[] default '{}',      -- v2
  expert_score int,               -- v3
  created_at timestamptz default now(),
  unique (observation_id, indicator_id)
);

create index if not exists observations_user_created_idx on observations (user_id, created_at desc);
create index if not exists indicator_answers_obs_idx on indicator_answers (observation_id);

-- auto-create profile on signup
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into profiles (id, display_name) values (new.id, split_part(new.email, '@', 1))
  on conflict (id) do nothing;
  return new;
end; $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
for each row execute function public.handle_new_user();

-- Row Level Security (defence in depth; backend uses service key and checks ownership itself)
alter table profiles enable row level security;
alter table observations enable row level security;
alter table indicator_answers enable row level security;

drop policy if exists "own profile" on profiles;
create policy "own profile" on profiles for select using (auth.uid() = id);

drop policy if exists "own observations" on observations;
create policy "own observations" on observations for all using (auth.uid() = user_id);

drop policy if exists "own answers" on indicator_answers;
create policy "own answers" on indicator_answers for all using (
  exists (select 1 from observations o where o.id = observation_id and o.user_id = auth.uid())
);

-- Private storage bucket for photos (8 MB limit, images only)
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('observation-photos', 'observation-photos', false, 8388608, array['image/jpeg','image/png','image/webp'])
on conflict (id) do nothing;
