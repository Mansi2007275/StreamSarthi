-- Remove all seed data. Run in the Supabase SQL editor.
-- audit_events is append-only (a trigger blocks UPDATE/DELETE), so the trigger
-- must be disabled for this cleanup and re-enabled right after.

alter table audit_events disable trigger audit_no_change;
delete from audit_events where observation_id in (select id from observations where is_seed);
alter table audit_events enable trigger audit_no_change;
delete from observations where is_seed;   -- lessons and answers cascade

-- Then delete the seed users (seed-citizen-1..4@demo.streamsaathi.app,
-- seed-expert@demo.streamsaathi.app) from the Supabase Auth dashboard by hand -
-- the admin API used to create them has no matching bulk-delete-by-email call here.
