-- ============================================================
-- 004_smoke_test.sql — 驗證這套 schema 真的擋得住該擋的事
-- ------------------------------------------------------------
-- 本機用（跑完自動 rollback，不留資料）：
--   psql -f sql/000_local_stub.sql -f sql/001_core_schema.sql \
--        -f sql/002_rls.sql -f sql/004_smoke_test.sql
--
-- 驗七件事：
--   1 單號每家每天各自從 001 起跳
--   2 訂單金額由明細自動加總
--   3 庫存由異動加總，台斤／兩自動換算
--   4 包／盒這種非物理換算，要有 product_units 才算得出來
--   5 沒設定換算率就直接報錯，不會靜靜算錯
--   6 A 家看不到 B 家的任何一列（RLS）
--   7 A 家不能把資料寫進 B 家（RLS with check）
-- ============================================================
\set ON_ERROR_STOP on
begin;

-- ---------- 準備兩家店、兩個人 ----------
insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'a@example.com'),
  ('22222222-2222-2222-2222-222222222222', 'b@example.com');

insert into tenants (id, slug, name) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'shop-a', '測試茶行'),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'shop-b', '測試乾貨行');

insert into members (tenant_id, user_id, role) values
  ('aaaaaaaa-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'owner'),
  ('bbbbbbbb-0000-0000-0000-000000000002', '22222222-2222-2222-2222-222222222222', 'owner');

insert into units (tenant_id, code, name, dimension, base_factor) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'jin',   '台斤', 'weight', 600),
  ('aaaaaaaa-0000-0000-0000-000000000001', 'liang', '兩',   'weight', 37.5),
  ('aaaaaaaa-0000-0000-0000-000000000001', 'pack',  '包',   'count',  1),
  ('aaaaaaaa-0000-0000-0000-000000000001', 'box',   '盒',   'count',  1),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'jin',   '台斤', 'weight', 600);

insert into price_tiers (tenant_id, code, name, is_default) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'retail',    '零售', true),
  ('aaaaaaaa-0000-0000-0000-000000000001', 'wholesale', '批發', false),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'retail',    '零售', true);

-- A 家一款茶，庫存論台斤
insert into products (id, tenant_id, name, stock_unit_id, low_stock_qty)
select 'cccccccc-0000-0000-0000-000000000003', 'aaaaaaaa-0000-0000-0000-000000000001',
       '測試茶', u.id, 5
  from units u
 where u.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001' and u.code = 'jin';

-- 一包＝四兩＝0.25 台斤；一盒＝兩包＝0.5 台斤
insert into product_units (tenant_id, product_id, unit_id, qty_in_stock_unit)
select 'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000003', u.id, v.f
  from units u
  join (values ('pack', 0.25), ('box', 0.5)) as v(code, f) on v.code = u.code
 where u.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001';

insert into customers (id, tenant_id, name, phone)
values ('dddddddd-0000-0000-0000-000000000004', 'aaaaaaaa-0000-0000-0000-000000000001', '測試客戶', '0900000000');

-- ---------- 1／2：單號與金額 ----------
insert into orders (id, tenant_id, customer_id, customer_name, price_tier_id, channel)
select 'eeeeeeee-0000-0000-0000-000000000005', 'aaaaaaaa-0000-0000-0000-000000000001',
       'dddddddd-0000-0000-0000-000000000004', '測試客戶', pt.id, 'line'
  from price_tiers pt
 where pt.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001' and pt.code = 'retail';

insert into order_items (tenant_id, order_id, line_no, product_id, product_name, unit_id, unit_name, qty, unit_price)
select 'aaaaaaaa-0000-0000-0000-000000000001', 'eeeeeeee-0000-0000-0000-000000000005', 1,
       'cccccccc-0000-0000-0000-000000000003', '測試茶', u.id, '兩', 3, 250
  from units u where u.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001' and u.code = 'liang';

do $$
declare v_no text; v_total numeric;
begin
  select order_no, total into v_no, v_total from orders where id = 'eeeeeeee-0000-0000-0000-000000000005';
  assert v_no like to_char((now() at time zone 'Asia/Taipei')::date, 'YYYYMMDD') || '-001', '單號格式錯：' || v_no;
  assert v_total = 750, '訂單金額應為 750，實得 ' || v_total;
  raise notice '[1][2] 單號 % ／ 金額 % — OK', v_no, v_total;
end $$;

-- ---------- 3：庫存加總與重量換算 ----------
-- 進貨 10 台斤，賣掉 3 兩（＝0.1875 台斤）→ 剩 9.8125 台斤
insert into stock_moves (tenant_id, product_id, reason, qty, unit_id)
select 'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000003', 'purchase', 10, u.id
  from units u where u.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001' and u.code = 'jin';

insert into stock_moves (tenant_id, product_id, reason, qty, unit_id, order_id)
select 'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000003', 'sale', -3, u.id,
       'eeeeeeee-0000-0000-0000-000000000005'
  from units u where u.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001' and u.code = 'liang';

do $$
declare v_qty numeric; v_low boolean;
begin
  select stock_qty, is_low into v_qty, v_low
    from v_product_stock where product_id = 'cccccccc-0000-0000-0000-000000000003';
  assert v_qty = 9.8125, '庫存應為 9.8125 台斤，實得 ' || v_qty;
  assert v_low = false, '9.8125 > 低量門檻 5，不該亮低量';
  raise notice '[3] 庫存 % 台斤（10 台斤進、3 兩出）— OK', v_qty;
end $$;

-- ---------- 4：包／盒的品項專屬換算 ----------
insert into stock_moves (tenant_id, product_id, reason, qty, unit_id)
select 'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000003', 'sale', -2, u.id
  from units u where u.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001' and u.code = 'box';

do $$
declare v_qty numeric;
begin
  select stock_qty into v_qty from v_product_stock where product_id = 'cccccccc-0000-0000-0000-000000000003';
  assert v_qty = 8.8125, '賣 2 盒（＝1 台斤）後應為 8.8125，實得 ' || v_qty;
  raise notice '[4] 賣 2 盒後庫存 % 台斤 — OK', v_qty;
end $$;

-- ---------- 5：沒設換算率就報錯，不會靜靜算錯 ----------
do $$
declare v_unit uuid;
begin
  select id into v_unit from units
   where tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001' and code = 'pack';
  delete from product_units where unit_id = v_unit;
  begin
    insert into stock_moves (tenant_id, product_id, reason, qty, unit_id)
    values ('aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000003', 'sale', -1, v_unit);
    raise exception '不該成功：包沒有換算率卻讓它扣了庫存';
  exception when others then
    if sqlerrm like '%無法換算%' then
      raise notice '[5] 未設換算率 → 擋下並報錯 — OK';
    else
      raise;
    end if;
  end;
end $$;

-- ---------- 6／7：RLS ----------
set local role authenticated;

-- B 家的人
select set_config('app.user_id', '22222222-2222-2222-2222-222222222222', true);

do $$
declare n int;
begin
  select count(*) into n from orders;        assert n = 0, 'B 竟看得到 A 的訂單';
  select count(*) into n from order_items;   assert n = 0, 'B 竟看得到 A 的明細';
  select count(*) into n from customers;     assert n = 0, 'B 竟看得到 A 的客戶';
  select count(*) into n from products;      assert n = 0, 'B 竟看得到 A 的品項';
  select count(*) into n from stock_moves;   assert n = 0, 'B 竟看得到 A 的庫存異動';
  select count(*) into n from v_product_stock; assert n = 0, 'B 竟看得到 A 的庫存';
  select count(*) into n from tenants;       assert n = 1, 'B 應該只看得到自己那一家，實得 ' || n;
  raise notice '[6] B 家查 A 家的資料：全部 0 列 — OK';
end $$;

do $$
begin
  begin
    insert into customers (tenant_id, name)
    values ('aaaaaaaa-0000-0000-0000-000000000001', '偷塞進 A 家的客戶');
    raise exception '不該成功：B 竟能寫進 A 家';
  exception when insufficient_privilege then
    raise notice '[7] B 家寫入 A 家 → 被 RLS 擋下 — OK';
  end;
end $$;

-- A 家的人看得到自己的
select set_config('app.user_id', '11111111-1111-1111-1111-111111111111', true);
do $$
declare n int;
begin
  select count(*) into n from orders; assert n = 1, 'A 應看得到自己的 1 張單，實得 ' || n;
  raise notice '[6b] A 家看得到自己的訂單 — OK';
end $$;

reset role;
rollback;
