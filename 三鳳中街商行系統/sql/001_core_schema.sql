-- ============================================================
-- 001_core_schema.sql — 老街商行系統．核心資料表 v0
-- ------------------------------------------------------------
-- 目標：一套系統整條街用。每張業務表都帶 tenant_id，
--       跨租戶的參照在資料庫層就不可能發生（複合外鍵）。
--
-- v0 的意思：欄位可以改，結構不該改。看過東信實際 Excel 之後
--            會補欄位、補預設值，但表的切法不預期會動。
--            未定案的地方都用 TODO(Excel) / TODO(王老闆) 標出來。
--
-- 執行順序：001 → 002（RLS）→ 003（種子）
-- ============================================================

create extension if not exists pgcrypto;

-- ------------------------------------------------------------
-- 列舉：這些是「程式碼」不是「設定」——刻意不讓每家自訂
-- ------------------------------------------------------------

-- 訂單狀態流程：待確認 → 備貨 → 已出貨 → 完成（可隨時取消）
create type order_status as enum ('pending', 'preparing', 'shipped', 'done', 'cancelled');

-- 下單管道：來店／電話／LINE／系統自動（階段四客人自己下的單）
create type order_channel as enum ('walk_in', 'phone', 'line', 'self_service');

-- 交貨方式：自取／宅配
create type delivery_method as enum ('pickup', 'shipping');

-- 單位量綱：重量／容量／件數。只有同量綱且非件數才能自動換算
create type unit_dimension as enum ('weight', 'volume', 'count');

-- 庫存異動原因
create type stock_reason as enum ('purchase', 'sale', 'return_in', 'adjust', 'waste');

-- 角色：老闆（可管設定與帳號）／店員（只做業務）
create type member_role as enum ('owner', 'staff');


-- ------------------------------------------------------------
-- 共用：updated_at 自動更新
-- ------------------------------------------------------------
create or replace function set_updated_at() returns trigger
language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end $$;


-- ============================================================
-- 1. tenants — 商家
-- ============================================================
create table tenants (
  id           uuid primary key default gen_random_uuid(),
  slug         text not null unique,          -- 網址用短代號，例：dongsin
  name         text not null,                 -- 店名
  tax_id       text,                          -- 統編
  phone        text,
  address      text,

  -- LINE：**金鑰不落庫**。這裡只存「金鑰放在 Supabase Vault 的哪個名字」，
  -- 實際 channel secret / access token 由後端從 Vault 或環境變數取。
  line_channel_id      text,
  line_basic_id        text,                  -- 官方帳號 @xxxx
  line_secret_ref      text,

  -- 功能開關：關掉的功能前端就不顯示。差異是資料，不是程式碼。
  -- 例：{"delivery": true, "gift_box": true, "wholesale": true}
  features     jsonb not null default '{}'::jsonb,

  timezone     text not null default 'Asia/Taipei',
  is_active    boolean not null default true,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),

  constraint tenants_slug_format check (slug ~ '^[a-z0-9][a-z0-9-]{1,30}$')
);
create trigger tenants_set_updated_at before update on tenants
  for each row execute function set_updated_at();


-- ============================================================
-- 2. members — 誰能登入哪一家
-- ============================================================
create table members (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null references tenants(id) on delete cascade,
  user_id      uuid not null references auth.users(id) on delete cascade,
  role         member_role not null default 'staff',
  display_name text,
  is_active    boolean not null default true,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),

  unique (tenant_id, user_id)
);
create index members_user_idx on members (user_id) where is_active;
create trigger members_set_updated_at before update on members
  for each row execute function set_updated_at();


-- ============================================================
-- 3. units — 單位目錄（台斤／兩／包／盒…）
-- ------------------------------------------------------------
-- base_factor = 換算到該量綱的基準：weight→公克、volume→毫升、count→件
--   台斤 600、兩 37.5、公斤 1000、公克 1、包 1、盒 1
-- 件數單位之間（一盒＝幾包）沒有通用答案，那是**品項**的事，
-- 放在 product_units。
-- ============================================================
create table units (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  code        text not null,                       -- 'jin' / 'liang' / 'pack' / 'box'
  name        text not null,                       -- '台斤' / '兩' / '包' / '盒'
  dimension   unit_dimension not null,
  base_factor numeric(16,6) not null,
  sort_order  int not null default 0,
  is_active   boolean not null default true,
  created_at  timestamptz not null default now(),

  unique (tenant_id, code),
  unique (tenant_id, id),                          -- 給複合外鍵用
  constraint units_base_factor_positive check (base_factor > 0)
);


-- ============================================================
-- 4. price_tiers — 價格層級（零售／批發／老客戶…）
-- ============================================================
create table price_tiers (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references tenants(id) on delete cascade,
  code       text not null,                        -- 'retail' / 'wholesale' / 'vip'
  name       text not null,
  is_default boolean not null default false,
  sort_order int not null default 0,
  is_active  boolean not null default true,
  created_at timestamptz not null default now(),

  unique (tenant_id, code),
  unique (tenant_id, id)
);
-- 每家只能有一個預設層級
create unique index price_tiers_one_default on price_tiers (tenant_id) where is_default;


-- ============================================================
-- 5. products — 品項
-- ------------------------------------------------------------
-- stock_unit_id：這個品項的**庫存記帳單位**。所有進出貨都會換算成它。
--                茶論台斤，禮盒論盒——選錯了之後盤點會很痛。
-- ============================================================
create table products (
  id                   uuid primary key default gen_random_uuid(),
  tenant_id            uuid not null references tenants(id) on delete cascade,
  sku                  text,                       -- 店家自己的貨號，可空
  name                 text not null,
  category             text,                       -- 茶／禮盒／乾貨…先用文字，成形再獨立成表
  stock_unit_id        uuid not null,
  default_sell_unit_id uuid,
  low_stock_qty        numeric(14,3),              -- 低於此量提醒（庫存單位計）
  is_active            boolean not null default true,  -- 下架不刪除，歷史訂單要查得到
  note                 text,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),

  unique (tenant_id, id),
  unique (tenant_id, sku),
  constraint products_stock_unit_fk
    foreign key (tenant_id, stock_unit_id) references units (tenant_id, id),
  constraint products_default_sell_unit_fk
    foreign key (tenant_id, default_sell_unit_id) references units (tenant_id, id)
);
create index products_tenant_active_idx on products (tenant_id) where is_active;
create trigger products_set_updated_at before update on products
  for each row execute function set_updated_at();


-- ============================================================
-- 6. product_units — 品項專屬的單位換算
-- ------------------------------------------------------------
-- 只有「通用換算算不出來」的時候才需要建一列：
--   一盒＝2 包、一包＝四兩裝 —— 這些是品項的包裝方式，不是物理定律。
-- 台斤↔兩↔公克這種同量綱換算不用建，product_unit_factor() 會自己算。
--
-- ⚠ 這是架構圖九張表之外多出來的一張。理由寫在 01-資料表定義.md，
--   結論是：不獨立出來，就得把換算寫進程式碼，那就違反「差異是資料」。
-- ============================================================
create table product_units (
  id                uuid primary key default gen_random_uuid(),
  tenant_id         uuid not null references tenants(id) on delete cascade,
  product_id        uuid not null,
  unit_id           uuid not null,
  qty_in_stock_unit numeric(14,6) not null,   -- 1 個這個單位 = 幾個庫存單位
  sort_order        int not null default 0,
  is_active         boolean not null default true,
  created_at        timestamptz not null default now(),

  unique (tenant_id, product_id, unit_id),
  constraint product_units_qty_positive check (qty_in_stock_unit > 0),
  constraint product_units_product_fk
    foreign key (tenant_id, product_id) references products (tenant_id, id) on delete cascade,
  constraint product_units_unit_fk
    foreign key (tenant_id, unit_id) references units (tenant_id, id)
);


-- ------------------------------------------------------------
-- 換算函式：這個品項用這個單位賣，等於幾個庫存單位？
--   1. 有 product_units 設定 → 用設定值
--   2. 同量綱且非件數 → 用 units.base_factor 算（台斤/兩/公克）
--   3. 都不是 → 直接報錯。寧可開單失敗，也不要庫存悄悄算錯。
-- ------------------------------------------------------------
create or replace function product_unit_factor(p_product_id uuid, p_unit_id uuid)
returns numeric
language plpgsql stable as $$
declare
  v_override   numeric;
  v_sell       units%rowtype;
  v_stock      units%rowtype;
begin
  select qty_in_stock_unit into v_override
    from product_units
   where product_id = p_product_id and unit_id = p_unit_id and is_active;
  if found then
    return v_override;
  end if;

  select u.* into v_stock
    from products p join units u on u.id = p.stock_unit_id
   where p.id = p_product_id;
  if not found then
    raise exception '找不到品項 % 或其庫存單位', p_product_id;
  end if;

  select * into v_sell from units where id = p_unit_id;
  if not found then
    raise exception '找不到單位 %', p_unit_id;
  end if;

  if v_sell.dimension = v_stock.dimension and v_sell.dimension <> 'count' then
    return v_sell.base_factor / v_stock.base_factor;
  end if;

  raise exception '單位「%」無法換算成品項的庫存單位「%」，請在 product_units 設定換算率',
    v_sell.name, v_stock.name;
end $$;


-- ============================================================
-- 7. product_prices — 品項 × 層級 × 單位 → 單價
-- ------------------------------------------------------------
-- 這裡只存**現行價**。歷史價格靠 order_items 的快照，
-- 不做 effective_from 版本表——一天 5–10 單的規模，多一層只是負擔。
-- ============================================================
create table product_prices (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references tenants(id) on delete cascade,
  product_id uuid not null,
  tier_id    uuid not null,
  unit_id    uuid not null,
  unit_price numeric(12,2) not null,
  updated_at timestamptz not null default now(),

  unique (tenant_id, product_id, tier_id, unit_id),
  constraint product_prices_nonneg check (unit_price >= 0),
  constraint product_prices_product_fk
    foreign key (tenant_id, product_id) references products (tenant_id, id) on delete cascade,
  constraint product_prices_tier_fk
    foreign key (tenant_id, tier_id) references price_tiers (tenant_id, id) on delete cascade,
  constraint product_prices_unit_fk
    foreign key (tenant_id, unit_id) references units (tenant_id, id)
);
create trigger product_prices_set_updated_at before update on product_prices
  for each row execute function set_updated_at();


-- ============================================================
-- 8. customers — 客戶
-- ------------------------------------------------------------
-- 來店散客可以不建檔（orders.customer_id 允許為空），
-- 但只要留過電話或 LINE，就該有一列——回購查得到才有意義。
-- ============================================================
create table customers (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references tenants(id) on delete cascade,
  name            text not null,
  phone           text,
  line_user_id    text,                       -- LINE 的 userId（U 開頭），階段四綁定
  default_tier_id uuid,
  address         text,
  note            text,
  is_active       boolean not null default true,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),

  unique (tenant_id, id),
  constraint customers_default_tier_fk
    foreign key (tenant_id, default_tier_id) references price_tiers (tenant_id, id)
);
create index customers_phone_idx on customers (tenant_id, phone) where phone is not null;
create unique index customers_line_uid_idx on customers (tenant_id, line_user_id)
  where line_user_id is not null;
create trigger customers_set_updated_at before update on customers
  for each row execute function set_updated_at();


-- ============================================================
-- 9. orders — 訂單
-- ------------------------------------------------------------
-- 「四種業務型態」（零售／禮盒／批發／宅配）其實是三個不同的軸，
-- 混成一個欄位以後一定會打架，所以拆開：
--   零售 vs 批發 → price_tier_id（價格層級）
--   宅配 vs 自取 → delivery（交貨方式）
--   禮盒         → 是品項的分類，不是訂單的型態
-- ============================================================
create table orders (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references tenants(id) on delete cascade,
  order_no      text not null,                    -- 顯示用單號，見下方觸發器
  -- 台灣時間的「今天」。預設值不能引用 tenants.timezone（欄位預設不能查別的表），
  -- 這條街全在台灣，先寫死；真要跨時區再改成由後端帶入。
  order_date    date not null default (now() at time zone 'Asia/Taipei')::date,

  customer_id   uuid,
  -- 快照：客戶改名或刪檔，舊單顯示的仍是當時的名字
  customer_name  text,
  customer_phone text,

  price_tier_id uuid not null,
  channel       order_channel not null,
  status        order_status  not null default 'pending',

  delivery         delivery_method not null default 'pickup',
  ship_to_name     text,
  ship_to_phone    text,
  ship_to_address  text,
  due_date         date,                          -- 客人要的交貨日（年節很重要）

  subtotal      numeric(12,2) not null default 0, -- 由 order_items 自動加總
  discount      numeric(12,2) not null default 0,
  shipping_fee  numeric(12,2) not null default 0,
  total         numeric(12,2) not null generated always as
                  (subtotal - discount + shipping_fee) stored,

  -- TODO(王老闆)：批發是月結還是現結、有沒有賒帳。
  -- 有月結就要另做應收帳款與對帳單，v0 先只記「收了沒」。
  is_paid       boolean not null default false,
  paid_at       timestamptz,

  note          text,
  created_by    uuid references auth.users(id),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),

  unique (tenant_id, order_no),
  unique (tenant_id, id),
  constraint orders_amounts_nonneg check (discount >= 0 and shipping_fee >= 0),
  constraint orders_customer_fk
    foreign key (tenant_id, customer_id) references customers (tenant_id, id),
  constraint orders_tier_fk
    foreign key (tenant_id, price_tier_id) references price_tiers (tenant_id, id),
  -- 宅配一定要有地址，否則出貨時才發現就來不及了
  constraint orders_shipping_needs_address
    check (delivery <> 'shipping' or coalesce(ship_to_address, '') <> '')
);
create index orders_tenant_date_idx   on orders (tenant_id, order_date desc);
create index orders_tenant_status_idx on orders (tenant_id, status);
create index orders_customer_idx      on orders (tenant_id, customer_id);
create trigger orders_set_updated_at before update on orders
  for each row execute function set_updated_at();

-- 單號：每家每天各自從 001 起跳，例 20260824-003
create or replace function orders_assign_order_no() returns trigger
language plpgsql as $$
declare
  v_seq int;
begin
  if new.order_no is not null and new.order_no <> '' then
    return new;
  end if;
  -- 同一家同一天的併發開單排隊，避免撞號
  perform pg_advisory_xact_lock(hashtext(new.tenant_id::text || new.order_date::text));
  select count(*) + 1 into v_seq
    from orders
   where tenant_id = new.tenant_id and order_date = new.order_date;
  new.order_no := to_char(new.order_date, 'YYYYMMDD') || '-' || lpad(v_seq::text, 3, '0');
  return new;
end $$;
create trigger orders_assign_order_no_trg before insert on orders
  for each row execute function orders_assign_order_no();


-- ============================================================
-- 10. order_items — 訂單明細
-- ------------------------------------------------------------
-- 品名、單位、單價一律**快照**。改價、改品名、下架，都不能動到舊單。
-- ============================================================
create table order_items (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null references tenants(id) on delete cascade,
  order_id     uuid not null,
  line_no      int  not null,
  product_id   uuid,                             -- 品項刪不掉（有外鍵），但允許臨時品項留空
  product_name text not null,                    -- 快照
  unit_id      uuid,
  unit_name    text not null,                    -- 快照
  qty          numeric(14,3) not null,
  unit_price   numeric(12,2) not null,           -- 快照
  amount       numeric(12,2) not null generated always as (round(qty * unit_price)) stored,
  note         text,
  created_at   timestamptz not null default now(),

  unique (tenant_id, id),
  unique (order_id, line_no),
  constraint order_items_qty_positive check (qty > 0),
  constraint order_items_price_nonneg check (unit_price >= 0),
  constraint order_items_order_fk
    foreign key (tenant_id, order_id) references orders (tenant_id, id) on delete cascade,
  constraint order_items_product_fk
    foreign key (tenant_id, product_id) references products (tenant_id, id),
  constraint order_items_unit_fk
    foreign key (tenant_id, unit_id) references units (tenant_id, id)
);
create index order_items_order_idx on order_items (order_id);

-- 明細一動，訂單金額就重算。不讓前端自己算，算錯了對不出來。
create or replace function orders_recalc_subtotal() returns trigger
language plpgsql as $$
declare
  v_order uuid := coalesce(new.order_id, old.order_id);
begin
  update orders o
     set subtotal = coalesce((select sum(i.amount) from order_items i where i.order_id = v_order), 0)
   where o.id = v_order;
  return null;
end $$;
create trigger order_items_recalc_trg
  after insert or update or delete on order_items
  for each row execute function orders_recalc_subtotal();


-- ============================================================
-- 11. stock_moves — 庫存異動
-- ------------------------------------------------------------
-- 不存「現有庫存」欄位。任何時間點的庫存都由異動加總算出來，
-- 改帳一定留痕。代價是查詢要 sum()——一天 5–10 單完全不是問題。
--
-- qty 帶正負號：進貨為正、出貨為負、盤點修正兩者皆可。
-- factor 是**當下**的換算率，寫進這一列。日後包裝改了（一盒從 2 包
-- 變 3 包），舊帳不會跟著變。
-- ============================================================
create table stock_moves (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references tenants(id) on delete cascade,
  product_id uuid not null,
  moved_at   timestamptz not null default now(),
  reason     stock_reason not null,

  qty        numeric(14,3) not null,             -- 以 unit_id 計，帶正負號
  unit_id    uuid not null,
  factor     numeric(16,6) not null,             -- 1 unit = 幾個庫存單位（快照）
  base_qty   numeric(16,4) not null generated always as (qty * factor) stored,

  order_id   uuid,                               -- 出貨異動來自哪張單
  note       text,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),

  constraint stock_moves_qty_nonzero check (qty <> 0),
  constraint stock_moves_factor_positive check (factor > 0),
  constraint stock_moves_sign check (
    case reason
      when 'purchase'  then qty > 0
      when 'return_in' then qty > 0
      when 'sale'      then qty < 0
      when 'waste'     then qty < 0
      else true                                   -- adjust 可正可負
    end
  ),
  constraint stock_moves_product_fk
    foreign key (tenant_id, product_id) references products (tenant_id, id),
  constraint stock_moves_unit_fk
    foreign key (tenant_id, unit_id) references units (tenant_id, id),
  constraint stock_moves_order_fk
    foreign key (tenant_id, order_id) references orders (tenant_id, id)
);
create index stock_moves_product_idx on stock_moves (tenant_id, product_id, moved_at);
create index stock_moves_order_idx   on stock_moves (order_id) where order_id is not null;

-- 沒填 factor 就自己算一個，開單時前端不用管換算
create or replace function stock_moves_fill_factor() returns trigger
language plpgsql as $$
begin
  if new.factor is null then
    new.factor := product_unit_factor(new.product_id, new.unit_id);
  end if;
  return new;
end $$;
create trigger stock_moves_fill_factor_trg before insert on stock_moves
  for each row execute function stock_moves_fill_factor();
-- 註：BEFORE 觸發器在 NOT NULL 檢查之前跑，所以 factor 仍然可以是 not null。


-- ------------------------------------------------------------
-- 現有庫存：view，不是表
-- security_invoker → 查的人看得到什麼，由他自己的 RLS 決定
-- ------------------------------------------------------------
create view v_product_stock with (security_invoker = true) as
select
  p.tenant_id,
  p.id                as product_id,
  p.name              as product_name,
  u.name              as stock_unit,
  coalesce(sum(m.base_qty), 0) as stock_qty,
  p.low_stock_qty,
  (p.low_stock_qty is not null and coalesce(sum(m.base_qty), 0) <= p.low_stock_qty) as is_low
from products p
join units u on u.id = p.stock_unit_id
left join stock_moves m on m.product_id = p.id
group by p.tenant_id, p.id, p.name, u.name, p.low_stock_qty;
