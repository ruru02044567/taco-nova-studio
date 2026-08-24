-- ============================================================
-- 003_seed_dongsin.sql — 東信的初始設定
-- ------------------------------------------------------------
-- 導入一家新商家＝跑這一支＋改上面的值。不用寫程式。
-- ⚠ 下面的單位與價格層級是**假設**，等看過東信實際 Excel 再校正。
--   品項與價格刻意留空——茶單目前沒有一款是核實過的，不編。
-- ============================================================

insert into tenants (slug, name, line_basic_id, features)
values (
  'dongsin',
  '東信',                                   -- TODO(王老闆)：招牌與登記用字（茶葉／茶行）確認後改這裡
  null,                                     -- TODO：LINE 官方帳號 ID
  jsonb_build_object(
    'delivery',  true,                      -- 有宅配
    'gift_box',  true,                      -- 有禮盒
    'wholesale', true,                      -- 有批發價
    'line_order', false                     -- 客人自己 LINE 下單＝階段四才開
  )
)
on conflict (slug) do nothing;

-- ------------------------------------------------------------
-- 單位
-- 重量的換算率是定義，不是偏好：1 台斤 = 16 兩 = 600 公克
-- ------------------------------------------------------------
insert into units (tenant_id, code, name, dimension, base_factor, sort_order)
select t.id, v.code, v.name, v.dimension::unit_dimension, v.base_factor, v.sort_order
  from tenants t
  cross join (values
    ('jin',   '台斤', 'weight', 600.0,  10),
    ('liang', '兩',   'weight',  37.5,  20),
    ('kg',    '公斤', 'weight', 1000.0, 30),
    ('g',     '公克', 'weight',   1.0,  40),
    ('pack',  '包',   'count',    1.0,  50),
    ('box',   '盒',   'count',    1.0,  60),
    ('can',   '罐',   'count',    1.0,  70)
  ) as v(code, name, dimension, base_factor, sort_order)
 where t.slug = 'dongsin'
on conflict (tenant_id, code) do nothing;

-- ------------------------------------------------------------
-- 價格層級
-- TODO(Excel)：東信實際分幾種價？Excel 分頁通常就是答案。
-- ------------------------------------------------------------
insert into price_tiers (tenant_id, code, name, is_default, sort_order)
select t.id, v.code, v.name, v.is_default, v.sort_order
  from tenants t
  cross join (values
    ('retail',    '零售',   true,  10),
    ('wholesale', '批發',   false, 20),
    ('vip',       '老客戶', false, 30)
  ) as v(code, name, is_default, sort_order)
 where t.slug = 'dongsin'
on conflict (tenant_id, code) do nothing;

-- ------------------------------------------------------------
-- 品項：**故意不寫**
-- 九款茶的實際名稱、單位、三種價格，全部等東信的 Excel。
-- 現有網站上的茶單自承是「依產地推定的示意茶單」，不能當資料來源。
-- ------------------------------------------------------------

-- ------------------------------------------------------------
-- 老闆的帳號：等他用 LINE 或 Email 註冊過一次拿到 user id，再跑這段
-- ------------------------------------------------------------
-- insert into members (tenant_id, user_id, role, display_name)
-- select t.id, '<auth.users.id>'::uuid, 'owner', '王老闆'
--   from tenants t where t.slug = 'dongsin';
