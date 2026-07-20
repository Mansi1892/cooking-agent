-- Smart Meal AI credit/admin setup
-- Run this once in Supabase SQL Editor.

alter table public.users
  add column if not exists credits integer not null default 3,
  add column if not exists role text not null default 'user';

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'users_credits_non_negative'
  ) then
    alter table public.users
      add constraint users_credits_non_negative check (credits >= 0);
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'users_role_allowed'
  ) then
    alter table public.users
      add constraint users_role_allowed check (role in ('user', 'admin'));
  end if;
end $$;

-- Make the first/admin profile an admin.
-- Replace 11 with your backend user id if different.
update public.users
set role = 'admin'
where id = 11;

-- Optional: add or correct starting credits for existing users.
update public.users
set credits = 3
where credits is null;
