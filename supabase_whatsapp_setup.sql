-- Smart Meal AI WhatsApp setup
-- Run this once in Supabase SQL Editor.

alter table public.users
  add column if not exists whatsapp_number text;

alter table public.family_members
  add column if not exists whatsapp text;

create index if not exists users_whatsapp_number_idx
  on public.users(whatsapp_number);

