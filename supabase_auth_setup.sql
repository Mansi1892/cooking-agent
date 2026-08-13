-- Smart Meal AI basic password + reset setup
-- Run this once in Supabase SQL Editor before testing forgot password.

alter table public.users
  add column if not exists password_hash text,
  add column if not exists password_reset_token text,
  add column if not exists password_reset_expires_at timestamp with time zone;

create index if not exists users_password_reset_token_idx
  on public.users(password_reset_token)
  where password_reset_token is not null;
