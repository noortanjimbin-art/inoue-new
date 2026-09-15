-- Run this in the Supabase SQL editor for your project.

create table if not exists users (
  id    uuid primary key references auth.users(id) on delete cascade,
  name  text not null default '',
  email text not null unique,
  role  text not null default 'annotator' check (role in ('admin','annotator'))
);

create table if not exists videos (
  id     uuid primary key default gen_random_uuid(),
  name   text not null,
  dur    double precision default 0,
  size   bigint default 0,
  added  timestamptz not null default now(),
  thumb  text,
  r2_key text not null
);

create table if not exists tasks (
  id       uuid primary key default gen_random_uuid(),
  video_id uuid not null references videos(id) on delete cascade,
  user_id  uuid references users(id) on delete set null,
  status   text not null default 'todo' check (status in ('todo','doing','done')),
  created  timestamptz not null default now(),
  updated  timestamptz not null default now()
);
create index if not exists tasks_user on tasks(user_id);

create table if not exists anns (
  id      uuid primary key default gen_random_uuid(),
  task_id uuid not null references tasks(id) on delete cascade,
  t_start double precision not null,
  t_end   double precision not null,
  caption text not null default '',
  at      timestamptz not null default now()
);
create index if not exists anns_task on anns(task_id, t_start);

-- The API routes use the service-role key and enforce admin/annotator rules
-- themselves, so RLS is enabled with no public policies: nothing reaches these
-- tables with the anon key alone.
alter table users  enable row level security;
alter table videos enable row level security;
alter table tasks  enable row level security;
alter table anns   enable row level security;

-- First account to sign up becomes the admin.
create or replace function promote_first_user() returns trigger as $$
begin
  if (select count(*) from users) = 1 then
    update users set role = 'admin' where id = new.id;
  end if;
  return new;
end; $$ language plpgsql security definer;

drop trigger if exists first_user_is_admin on users;
create trigger first_user_is_admin after insert on users
  for each row execute function promote_first_user();
