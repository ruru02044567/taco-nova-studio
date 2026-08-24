-- ============================================================
-- 000_local_stub.sql — 只給本機驗證用，**不要在 Supabase 上跑**
-- ------------------------------------------------------------
-- Supabase 已經有 auth schema、auth.users 表與 auth.uid()。
-- 這支檔案在本機補出等價的最小替身，讓 001/002/003 能原封不動
-- 在一般 PostgreSQL 上跑過一次，證明 DDL 與 RLS 政策沒有語法或
-- 邏輯錯誤。上 Supabase 時請從 001 開始。
-- ============================================================

create schema if not exists auth;

create table if not exists auth.users (
  id    uuid primary key default gen_random_uuid(),
  email text
);

-- 本機用：以 session 變數 app.user_id 模擬登入者
create or replace function auth.uid() returns uuid
language sql stable as $$
  select nullif(current_setting('app.user_id', true), '')::uuid
$$;

-- Supabase 內建的三個角色，本機補出來才能測 RLS
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin noinherit bypassrls;
  end if;
end $$;

grant usage on schema public to anon, authenticated, service_role;
grant usage on schema auth   to anon, authenticated, service_role;
grant select on auth.users   to authenticated, service_role;
