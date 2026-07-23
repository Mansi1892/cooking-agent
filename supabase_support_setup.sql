-- Smart Meal AI support ticket setup
-- Run this once in Supabase SQL Editor.

create table if not exists public.support_tickets (
  id bigserial primary key,
  user_id bigint references public.users(id) on delete set null,
  category text not null default 'bug',
  title text not null,
  description text not null,
  page_url text,
  severity text not null default 'normal',
  status text not null default 'open',
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'support_tickets_category_allowed'
  ) then
    alter table public.support_tickets
      add constraint support_tickets_category_allowed
      check (category in ('bug', 'meal_plan', 'grocery', 'telegram', 'account', 'billing', 'other'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'support_tickets_severity_allowed'
  ) then
    alter table public.support_tickets
      add constraint support_tickets_severity_allowed
      check (severity in ('low', 'normal', 'high', 'urgent'));
  end if;

  if not exists (
    select 1 from pg_constraint where conname = 'support_tickets_status_allowed'
  ) then
    alter table public.support_tickets
      add constraint support_tickets_status_allowed
      check (status in ('open', 'reviewing', 'resolved'));
  end if;
end $$;

create index if not exists support_tickets_status_idx on public.support_tickets(status);
create index if not exists support_tickets_user_id_idx on public.support_tickets(user_id);
