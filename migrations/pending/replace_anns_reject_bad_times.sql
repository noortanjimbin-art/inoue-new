-- PENDING: run once in Supabase -> SQL editor (project svenzdtasbmhogowknws).
-- Could not be applied automatically: the Supabase connector lost write permission.
--
-- replace_anns used to SKIP rows whose start or end was null. A client bug could
-- therefore make an annotation vanish on save with no error. This version refuses
-- the whole save instead; the transaction rolls back and nothing is lost.
-- The API already rejects such saves (api/anns.js) - this is a second safety net.

create or replace function inoue_new.replace_anns(p_task uuid, p_items jsonb)
returns integer
language plpgsql
security definer
set search_path = inoue_new, public
as $$
declare
  n integer;
  bad integer;
begin
  select count(*) into bad
  from jsonb_array_elements(coalesce(p_items, '[]'::jsonb)) e
  where jsonb_typeof(e->'start') is distinct from 'number'
     or jsonb_typeof(e->'end')   is distinct from 'number'
     or (e->>'start')::double precision < 0
     or (e->>'end')::double precision < (e->>'start')::double precision;
  if bad > 0 then
    raise exception 'replace_anns: % annotation(s) have a missing or invalid time', bad
      using errcode = '22023';
  end if;

  delete from inoue_new.anns where task_id = p_task;

  insert into inoue_new.anns (task_id, t_start, t_end, caption)
  select p_task,
         (e->>'start')::double precision,
         (e->>'end')::double precision,
         coalesce(e->>'caption', '')
  from jsonb_array_elements(coalesce(p_items, '[]'::jsonb)) e;

  get diagnostics n = row_count;
  return n;
end $$;

revoke all on function inoue_new.replace_anns(uuid, jsonb) from public;
revoke all on function inoue_new.replace_anns(uuid, jsonb) from anon, authenticated;
grant execute on function inoue_new.replace_anns(uuid, jsonb) to service_role;
