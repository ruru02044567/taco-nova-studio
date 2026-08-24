-- ============================================================
-- 002_rls.sql — Row Level Security
-- ------------------------------------------------------------
-- 柱一：資料隔離靠資料庫，不靠程式碼。
--
-- 多租戶最常見的事故是「某支查詢忘了加 where tenant_id」。
-- RLS 讓這件事在資料庫層就不可能發生——就算後端寫錯，
-- Postgres 也只會回傳這個登入者所屬商家的資料。
--
-- 前提：後端一律用使用者的 JWT 連線（Supabase anon key + user session）。
--       用 service_role key 連線會繞過 RLS，那把鑰匙只能放在
--       伺服器端、且只給真正需要跨租戶的工作（例如平台開通新商家）。
-- ============================================================

-- ------------------------------------------------------------
-- 我屬於哪幾家？
-- security definer：這支函式自己不受 RLS 限制，
-- 否則查 members 會觸發 members 的政策而無限遞迴。
-- ------------------------------------------------------------
create or replace function current_tenant_ids()
returns setof uuid
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select m.tenant_id
    from members m
   where m.user_id = auth.uid()
     and m.is_active
$$;

create or replace function is_tenant_owner(p_tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from members m
     where m.user_id = auth.uid()
       and m.tenant_id = p_tenant_id
       and m.is_active
       and m.role = 'owner'
  )
$$;

revoke all on function current_tenant_ids() from public, anon;
revoke all on function is_tenant_owner(uuid) from public, anon;
grant execute on function current_tenant_ids() to authenticated;
grant execute on function is_tenant_owner(uuid) to authenticated;


-- ------------------------------------------------------------
-- 業務表：一律「屬於我的商家才看得到、才改得動」
-- 用迴圈套，避免十一張表手抄十一次、抄漏一張就是一個資料外洩。
-- ------------------------------------------------------------
do $$
declare
  t text;
  business_tables text[] := array[
    'units', 'price_tiers', 'products', 'product_units', 'product_prices',
    'customers', 'orders', 'order_items', 'stock_moves'
  ];
begin
  foreach t in array business_tables loop
    execute format('alter table %I enable row level security', t);
    execute format('alter table %I force  row level security', t);

    execute format($p$
      create policy tenant_select on %I for select to authenticated
        using (tenant_id in (select current_tenant_ids()))
    $p$, t);

    execute format($p$
      create policy tenant_insert on %I for insert to authenticated
        with check (tenant_id in (select current_tenant_ids()))
    $p$, t);

    execute format($p$
      create policy tenant_update on %I for update to authenticated
        using (tenant_id in (select current_tenant_ids()))
        with check (tenant_id in (select current_tenant_ids()))
    $p$, t);

    execute format($p$
      create policy tenant_delete on %I for delete to authenticated
        using (tenant_id in (select current_tenant_ids()))
    $p$, t);

    execute format('grant select, insert, update, delete on %I to authenticated', t);
  end loop;
end $$;


-- ------------------------------------------------------------
-- tenants：看得到自己家；只有老闆能改店家設定。
-- 開通新商家不走這條路（那是平台的事，用 service_role）。
-- ------------------------------------------------------------
alter table tenants enable row level security;
alter table tenants force  row level security;

create policy tenant_self_select on tenants for select to authenticated
  using (id in (select current_tenant_ids()));

create policy tenant_self_update on tenants for update to authenticated
  using (is_tenant_owner(id))
  with check (is_tenant_owner(id));

grant select, update on tenants to authenticated;


-- ------------------------------------------------------------
-- members：同一家的人互相看得到；只有老闆能加人、改角色、停用。
-- ------------------------------------------------------------
alter table members enable row level security;
alter table members force  row level security;

create policy members_select on members for select to authenticated
  using (tenant_id in (select current_tenant_ids()));

create policy members_insert on members for insert to authenticated
  with check (is_tenant_owner(tenant_id));

create policy members_update on members for update to authenticated
  using (is_tenant_owner(tenant_id))
  with check (is_tenant_owner(tenant_id));

create policy members_delete on members for delete to authenticated
  using (is_tenant_owner(tenant_id));

grant select, insert, update, delete on members to authenticated;


-- ------------------------------------------------------------
-- 檢視表：v_product_stock 建成 security_invoker，
-- 看得到什麼由查詢者自己在 stock_moves／products 上的 RLS 決定，
-- 但仍然要單獨授權才拿得到 select。
-- ------------------------------------------------------------
grant select on v_product_stock to authenticated;


-- ------------------------------------------------------------
-- 未登入者（anon）：什麼都不給。
-- 階段四客人用 LINE 下單時，是 LIFF 換到的 Supabase session，
-- 那時他也是 authenticated，但**不是 member**——所以會另外開一組
-- 以 customers.line_user_id 比對的政策。v0 先不開，免得留下一道
-- 沒人記得的門。
-- ------------------------------------------------------------
revoke all on all tables in schema public from anon;

-- 檢查用：列出所有沒開 RLS 的表。這支查詢應該回傳 0 列。
-- select tablename from pg_tables t
--  where schemaname = 'public'
--    and not exists (select 1 from pg_class c
--                     where c.relname = t.tablename and c.relrowsecurity);
