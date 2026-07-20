-- Smart Meal AI family personalization setup
-- Run this once in Supabase SQL Editor.

alter table public.users
  add column if not exists gender text;

alter table public.family_members
  add column if not exists goal text not null default 'maintenance',
  add column if not exists gender text,
  add column if not exists weight_kg numeric,
  add column if not exists height_cm numeric;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'family_members_goal_allowed'
  ) then
    alter table public.family_members
      add constraint family_members_goal_allowed check (goal in ('weight_loss', 'muscle_gain', 'maintenance'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'users_gender_allowed'
  ) then
    alter table public.users
      add constraint users_gender_allowed check (
        gender is null or gender in ('female', 'male', 'other', '')
      );
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'family_members_gender_allowed'
  ) then
    alter table public.family_members
      add constraint family_members_gender_allowed check (
        gender is null or gender in ('female', 'male', 'other', '')
      );
  end if;
end $$;
