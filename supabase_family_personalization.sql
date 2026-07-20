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

create table if not exists public.person_plan_overrides (
  id bigserial primary key,
  plan_id bigint not null references public.meal_plans(id) on delete cascade,
  person_id text not null,
  person_name text,
  day_name text not null,
  override jsonb not null default '{}'::jsonb,
  feedback text,
  created_at timestamp with time zone default now()
);

create unique index if not exists person_plan_overrides_unique_day
  on public.person_plan_overrides(plan_id, person_id, day_name);
