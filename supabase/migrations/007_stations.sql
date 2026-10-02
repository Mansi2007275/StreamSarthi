-- StreamSaathi Guardians: Stream Stations (printable QR poster per site)
-- Run in Supabase: SQL Editor -> New query -> paste -> Run. Idempotent: safe to run twice.
-- Run order: after 001-006. RLS is unchanged: no new tables, so no new policies.
--
-- Numbered 007 because that is the next free number; nothing is skipped.

-- ---------------------------------------------------------------- station numbers
-- A short human number for the poster ("Station #7"), because a uuid on a printed sign is
-- useless to anybody standing in front of it.
create sequence if not exists sites_station_number_seq;

alter table sites add column if not exists station_number int;

-- Backfill sites that predate the column, oldest first so the numbers follow the order the
-- sites were actually created. Only touches nulls, so re-running changes nothing.
do $$
declare r record;
begin
  for r in select id from sites where station_number is null order by created_at, id loop
    update sites set station_number = nextval('sites_station_number_seq') where id = r.id;
  end loop;
end $$;

alter table sites alter column station_number set default nextval('sites_station_number_seq');

create unique index if not exists sites_station_number_uniq on sites (station_number);

-- ---------------------------------------------------------------- where a check came from
-- 'station' means somebody scanned a poster at the water's edge rather than opening the app.
alter table observations add column if not exists source text not null default 'app';

alter table observations drop constraint if exists observations_source_check;
alter table observations add constraint observations_source_check
  check (source in ('app', 'station'));

create index if not exists observations_source_idx on observations (source) where source <> 'app';
