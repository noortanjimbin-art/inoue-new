-- Applied to the `inoe-annotation` Supabase project (svenzdtasbmhogowknws) as
-- migration `create_inoue_new_annotation_schema`. Kept here as the record of
-- what the API expects.
--
-- These tables live in their own `inoue_new` schema, NOT `public`: that project
-- already has videos/clips/annotations tables of a different shape, and putting
-- these alongside them would collide.

create schema if not exists inoue_new;

create table if not exists inoue_new.users (
  id    uuid primary key references auth.users(id) on delete cascade,
  name  text not null default '',
  email text not null unique,
  role  text not null default 'annotator' check (role in ('admin','annotator'))
);

create table if not exists inoue_new.videos (
  id     uuid primary key default gen_random_uuid(),
  name   text not null,
  dur    double precision default 0,
  size   bigint default 0,
  added  timestamptz not null default now(),
  thumb  text,
  r2_key text not null
);

create table if not exists inoue_new.tasks (
  id       uuid primary key default gen_random_uuid(),
  video_id uuid not null references inoue_new.videos(id) on delete cascade,
  user_id  uuid references inoue_new.users(id) on delete set null,
  status   text not null default 'todo' check (status in ('todo','doing','done')),
  created  timestamptz not null default now(),
  updated  timestamptz not null default now()
);
create index if not exists tasks_user on inoue_new.tasks(user_id);
create index if not exists tasks_video on inoue_new.tasks(video_id);

create table if not exists inoue_new.anns (
  id      uuid primary key default gen_random_uuid(),
  task_id uuid not null references inoue_new.tasks(id) on delete cascade,
  t_start double precision not null,
  t_end   double precision not null,
  caption text not null default '',
  at      timestamptz not null default now()
);
create index if not exists anns_task on inoue_new.anns(task_id, t_start);

-- The API routes hold the service-role key and enforce admin/annotator rules
-- themselves. RLS on with no policies means the anon key reaches nothing here,
-- while service_role (which bypasses RLS) still works.
alter table inoue_new.users  enable row level security;
alter table inoue_new.videos enable row level security;
alter table inoue_new.tasks  enable row level security;
alter table inoue_new.anns   enable row level security;

grant usage on schema inoue_new to service_role;
grant all privileges on all tables in schema inoue_new to service_role;
grant all privileges on all sequences in schema inoue_new to service_role;
alter default privileges in schema inoue_new
  grant all privileges on tables to service_role;
grant usage on schema inoue_new to anon, authenticated;

-- First account registered becomes the admin.
create or replace function inoue_new.promote_first_user() returns trigger
language plpgsql security definer set search_path = inoue_new, public as $$
begin
  if (select count(*) from inoue_new.users) = 1 then
    update inoue_new.users set role = 'admin' where id = new.id;
  end if;
  return new;
end; $$;

drop trigger if exists first_user_is_admin on inoue_new.users;
create trigger first_user_is_admin after insert on inoue_new.users
  for each row execute function inoue_new.promote_first_user();
