# -*- coding: utf-8 -*-
import json, html

rows = json.load(open("dataset.json", encoding="utf-8"))

def clean(s):
    """修掉寫檔時被系統編碼弄壞的字元（多為右單引號）"""
    return (s or "").replace("��", "’").replace("�", "").strip()

slim = [{
    "t": clean(r["title"]), "c": clean(r["channel"]), "v": r["views"], "l": r["likes"],
    "lr": r["like_rate"], "d": r["dur"], "u": r["upload"], "a": r["animal"],
    "g": r["genre"], "ai": 1 if r["ai_made"] else 0, "h": clean(r["hook"]),
    "s": r["subs"], "id": r["id"],
} for r in rows]

DATA = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))

page = """<title>YouTube 動物爆款 Shorts 榜｜5000 萬觀看以上</title>
<style>
:root{
  --ground:#F2F3F5; --surface:#FFFFFF; --surface-2:#FAFBFC;
  --ink:#16181D; --ink-2:#4A5058; --ink-3:#858C96;
  --line:#DFE2E7; --line-soft:#EDEFF2;
  --cat:#D2691E; --dog:#2F7D8E; --ai:#6B5CC4; --bar:#C9CDD4;
  --focus:#2F7D8E;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#131519; --surface:#1B1E24; --surface-2:#20242B;
    --ink:#E9EBEF; --ink-2:#A9B0BA; --ink-3:#727A85;
    --line:#2C313A; --line-soft:#242830;
    --cat:#E8934F; --dog:#5FB3C4; --ai:#9A8BE8; --bar:#3A404A;
    --focus:#5FB3C4;
  }
}
:root[data-theme="dark"]{
  --ground:#131519; --surface:#1B1E24; --surface-2:#20242B;
  --ink:#E9EBEF; --ink-2:#A9B0BA; --ink-3:#727A85;
  --line:#2C313A; --line-soft:#242830;
  --cat:#E8934F; --dog:#5FB3C4; --ai:#9A8BE8; --bar:#3A404A;
  --focus:#5FB3C4;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"Segoe UI","Microsoft JhengHei","PingFang TC","Hiragino Sans",system-ui,-apple-system,sans-serif;
  font-size:15px; line-height:1.6;
}
.wrap{max-width:1240px;margin:0 auto;padding:40px 24px 80px}
h1{font-size:clamp(26px,3.4vw,40px);line-height:1.15;letter-spacing:-.022em;font-weight:700;margin:0;text-wrap:balance}
.sub{color:var(--ink-2);margin:10px 0 0;max-width:62ch}
.eyebrow{font-size:11px;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3);font-weight:600;margin:0 0 12px}
.num{font-variant-numeric:tabular-nums}

/* 摘要帶 */
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1px;
  background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:32px 0 0}
.cell{background:var(--surface);padding:16px 18px}
.cell .k{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);font-weight:600}
.cell .v{font-size:26px;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums;margin-top:4px}
.cell .n{font-size:12px;color:var(--ink-3);margin-top:2px}

/* 洞察 */
.insights{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px;margin:16px 0 0}
.ins{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:18px 20px}
.ins h3{margin:0 0 8px;font-size:15px;font-weight:650;letter-spacing:-.01em}
.ins p{margin:0;font-size:13.5px;color:var(--ink-2);line-height:1.65}
.ins .stat{font-variant-numeric:tabular-nums;font-weight:650;color:var(--ink)}
.ins.hi{border-color:var(--ai);box-shadow:inset 3px 0 0 var(--ai)}

/* 控制列 */
.controls{position:sticky;top:0;z-index:20;background:var(--ground);
  padding:14px 0 12px;margin:32px 0 0;border-bottom:1px solid var(--line);
  display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.chip{font:inherit;font-size:13px;padding:6px 13px;border-radius:99px;cursor:pointer;
  border:1px solid var(--line);background:var(--surface);color:var(--ink-2);transition:.13s}
.chip:hover{border-color:var(--ink-3);color:var(--ink)}
.chip[aria-pressed="true"]{background:var(--ink);color:var(--ground);border-color:var(--ink)}
.chip:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
input[type=search],select{font:inherit;font-size:13px;padding:6px 11px;border-radius:7px;
  border:1px solid var(--line);background:var(--surface);color:var(--ink)}
input[type=search]{min-width:190px}
.spacer{flex:1}
.count{font-size:12.5px;color:var(--ink-3);font-variant-numeric:tabular-nums;white-space:nowrap}

/* 榜單 */
.list{margin:0;padding:0;list-style:none}
.row{display:grid;grid-template-columns:44px 1fr 118px 60px 70px 92px;gap:14px;align-items:center;
  padding:11px 14px;border-bottom:1px solid var(--line-soft);background:var(--surface)}
.row:first-child{border-top-left-radius:10px;border-top-right-radius:10px;margin-top:14px}
.row:hover{background:var(--surface-2)}
.rank{font-size:12px;color:var(--ink-3);font-variant-numeric:tabular-nums;text-align:right}
.main{min-width:0}
.ttl{display:block;color:var(--ink);text-decoration:none;font-weight:550;font-size:14px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ttl:hover{text-decoration:underline;text-decoration-color:var(--ink-3)}
.meta{font-size:12px;color:var(--ink-3);margin-top:3px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.tag{font-size:10.5px;letter-spacing:.04em;padding:1px 7px;border-radius:4px;border:1px solid currentColor;font-weight:600}
.t-cat{color:var(--cat)} .t-dog{color:var(--dog)} .t-ai{color:var(--ai)} .t-o{color:var(--ink-3)}
.views{text-align:right}
.views .n{font-variant-numeric:tabular-nums;font-weight:650;font-size:14px}
.track{height:3px;background:var(--line-soft);border-radius:2px;margin-top:5px;overflow:hidden}
.fill{height:100%;background:var(--bar);border-radius:2px}
.fill.cat{background:var(--cat)} .fill.dog{background:var(--dog)}
.dur,.lr{text-align:right;font-variant-numeric:tabular-nums;font-size:13px;color:var(--ink-2)}
.date{text-align:right;font-variant-numeric:tabular-nums;font-size:12px;color:var(--ink-3)}
.hook{font-size:12.5px;color:var(--ink-2);margin-top:3px}
.empty{padding:48px;text-align:center;color:var(--ink-3);background:var(--surface);border-radius:10px;margin-top:14px}
.more{display:block;width:100%;margin:16px 0 0;padding:12px;font:inherit;font-size:14px;cursor:pointer;
  background:var(--surface);border:1px solid var(--line);border-radius:10px;color:var(--ink-2)}
.more:hover{border-color:var(--ink-3);color:var(--ink)}
.foot{margin-top:56px;padding-top:22px;border-top:1px solid var(--line);font-size:12.5px;color:var(--ink-3);line-height:1.8}
@media(max-width:820px){
  .row{grid-template-columns:1fr 100px;gap:8px 12px}
  .rank,.dur,.lr,.date{display:none}
}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>

<div class="wrap">
<p class="eyebrow">YouTube Shorts 爬取 · 2026-08-10</p>
<h1>動物爆款 Shorts 全榜</h1>
<p class="sub">觀看數 5000 萬以上、經逐支驗證的直式 Shorts，共 861 支。以 86 組跨語言關鍵字按觀看數降冪掃過 YouTube 搜尋，再逐支確認畫面比例與真實數據。貓與狗排在最前。</p>

<div class="summary">
  <div class="cell"><div class="k">總計</div><div class="v num">861</div><div class="n">支 · ≥5000 萬觀看</div></div>
  <div class="cell"><div class="k">貓</div><div class="v num" style="color:var(--cat)">221</div><div class="n">最高 11.6 億</div></div>
  <div class="cell"><div class="k">狗</div><div class="v num" style="color:var(--dog)">195</div><div class="n">最高 7.8 億</div></div>
  <div class="cell"><div class="k">貓狗同框</div><div class="v num">7</div><div class="n">最高 1.9 億</div></div>
  <div class="cell"><div class="k">其他動物</div><div class="v num">332</div><div class="n">鳥 83 · 野生 86</div></div>
  <div class="cell"><div class="k">AI 生成</div><div class="v num" style="color:var(--ai)">143</div><div class="n">貓狗中占 55 支</div></div>
</div>

<h2 class="eyebrow" style="margin:40px 0 12px">從 423 支貓狗爆款讀出來的事</h2>
<div class="insights">
  <div class="ins hi">
    <h3>AI 生成衝得到觀看，換不到認同</h3>
    <p>AI 生成貓狗的觀看中位數 <span class="stat">8900 萬</span>，真實拍攝 <span class="stat">9600 萬</span>，幾乎打平。但按讚率中位數 AI 只有 <span class="stat">0.71%</span>，真拍是 <span class="stat">1.31%</span>——演算法願意推，觀眾卻不願意按。</p>
  </div>
  <div class="ins">
    <h3>越短衝觀看，越長換互動</h3>
    <p>10 秒內：觀看中位 <span class="stat">9500 萬</span>、讚率 <span class="stat">0.57%</span>。60 秒以上：觀看掉到 <span class="stat">7600 萬</span>，讚率卻升到 <span class="stat">2.35%</span>。秒數是在觀看量和黏著度之間做交換。</p>
  </div>
  <div class="ins">
    <h3>訂閱數不是入場券</h3>
    <p>423 支貓狗爆款裡有 <span class="stat">61 支</span>來自訂閱不到 100 萬的頻道。最猛的一支只有 <span class="stat">25.6 萬</span>訂閱，衝出 <span class="stat">7.8 億</span>觀看。</p>
  </div>
  <div class="ins">
    <h3>一隻貓可以複利 22 次</h3>
    <p>俄語頻道 Sonyakisa8 TT 靠一隻叫 Sonya 的貓，<span class="stat">22 支</span>上榜、合計 <span class="stat">55.9 億</span>觀看。標題常常只有一個 emoji 加 #cat #cats。角色固定，題材才敢重複。</p>
  </div>
  <div class="ins">
    <h3>搞笑最多，但科普最被按讚</h3>
    <p>題材以搞笑意外 <span class="stat">154 支</span>（36%）壓倒性最多；但按讚率最高的是知識科普 <span class="stat">3.2%</span> 和挑戰實驗 <span class="stat">2.08%</span>，搞笑只有 1.19%。</p>
  </div>
  <div class="ins">
    <h3>這是一份很新的榜</h3>
    <p>2025 年上傳的有 <span class="stat">155 支</span>、2026 年至今 <span class="stat">48 支</span>，兩年就占了近一半。爆款不是老片累積出來的，紅利還在。</p>
  </div>
</div>

<div class="controls" role="group" aria-label="篩選與排序">
  <button class="chip" data-f="all" aria-pressed="true">全部</button>
  <button class="chip" data-f="貓" aria-pressed="false">貓</button>
  <button class="chip" data-f="狗" aria-pressed="false">狗</button>
  <button class="chip" data-f="貓狗同框" aria-pressed="false">貓狗同框</button>
  <button class="chip" data-f="other" aria-pressed="false">其他動物</button>
  <button class="chip" data-f="ai" aria-pressed="false">僅 AI 生成</button>
  <select id="genre" aria-label="題材"><option value="">所有題材</option></select>
  <select id="sort" aria-label="排序">
    <option value="v">觀看數高→低</option>
    <option value="lr">按讚率高→低</option>
    <option value="u">上傳日期新→舊</option>
    <option value="d">片長短→長</option>
    <option value="s">頻道訂閱少→多</option>
  </select>
  <input type="search" id="q" placeholder="搜尋標題或頻道…" aria-label="搜尋">
  <span class="spacer"></span>
  <span class="count" id="count"></span>
</div>

<ul class="list" id="list"></ul>
<button class="more" id="more" hidden>載入更多</button>

<p class="foot">
資料來源：yt-dlp 掃 YouTube 搜尋結果（86 組關鍵字，涵蓋英／中／日／韓／西／印地／阿拉伯／印尼語），按觀看數降冪各取前 120 筆，篩出 5000 萬以上、3 分鐘內者共 1165 支，再逐支請求 <code>/shorts/</code> 端點確認未被轉址（861 支為真 Shorts，304 支是橫式影片已剔除）。標題、頻道、上傳日、按讚數、訂閱數為逐支重新取得的實際值。<br>
物種與題材由 AI 逐支判讀標題、頻道名與 hashtag，非人工核對，少數可能誤判。觀看數為擷取當下數值。
</p>
</div>

<script>
const DATA = __DATA__;
const list = document.getElementById('list');
const moreBtn = document.getElementById('more');
const countEl = document.getElementById('count');
const OTHER = new Set(['貓','狗','貓狗同框']);
let filter = 'all', shown = 0, current = [];
const PAGE = 60;
const MAXV = Math.max(...DATA.map(d => d.v));

const genres = [...new Set(DATA.map(d => d.g))].sort();
const gsel = document.getElementById('genre');
genres.forEach(g => { const o = document.createElement('option'); o.value = o.textContent = g; gsel.append(o); });

const fmt = v => v >= 1e8 ? (v/1e8).toFixed(2).replace(/\\.?0+$/,'') + ' 億' : Math.round(v/1e4).toLocaleString() + ' 萬';
const fmtSub = v => v >= 1e8 ? (v/1e8).toFixed(1) + ' 億'
  : v >= 1e6 ? Math.round(v/1e4).toLocaleString() + ' 萬'
  : v >= 1e4 ? (v/1e4).toFixed(1).replace(/\\.0$/,'') + ' 萬' : String(v);
const esc = s => { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; };

function compute(){
  const q = document.getElementById('q').value.trim().toLowerCase();
  const g = gsel.value;
  const sort = document.getElementById('sort').value;
  let r = DATA.filter(d => {
    if (filter === 'ai') { if (!d.ai) return false; }
    else if (filter === 'other') { if (OTHER.has(d.a)) return false; }
    else if (filter !== 'all') { if (d.a !== filter) return false; }
    if (g && d.g !== g) return false;
    if (q && !(d.t.toLowerCase().includes(q) || d.c.toLowerCase().includes(q) || d.h.includes(q))) return false;
    return true;
  });
  const key = {v:d=>-d.v, lr:d=>-(d.lr||0), u:d=>d.u?-Number(d.u.replace(/-/g,'')):0, d:d=>d.d, s:d=>d.s||9e15};
  r.sort((a,b) => key[sort](a) - key[sort](b));
  return r;
}

function render(reset){
  if (reset){ current = compute(); shown = 0; list.innerHTML = ''; }
  const slice = current.slice(shown, shown + PAGE);
  const frag = document.createDocumentFragment();
  slice.forEach((d, i) => {
    const li = document.createElement('li');
    li.className = 'row';
    const cls = d.a === '貓' ? 'cat' : d.a === '狗' ? 'dog' : '';
    const tag = d.a === '貓' ? 't-cat' : d.a === '狗' ? 't-dog' : 't-o';
    li.innerHTML =
      '<div class="rank num">' + (shown + i + 1) + '</div>' +
      '<div class="main">' +
        '<a class="ttl" href="https://www.youtube.com/shorts/' + d.id + '" target="_blank" rel="noopener">' + esc(d.t || '(無標題)') + '</a>' +
        '<div class="hook">' + esc(d.h) + '</div>' +
        '<div class="meta">' +
          '<span class="tag ' + tag + '">' + esc(d.a) + '</span>' +
          (d.ai ? '<span class="tag t-ai">AI 生成</span>' : '') +
          '<span>' + esc(d.g) + '</span><span>·</span><span>' + esc(d.c) + '</span>' +
          (d.s ? '<span>·</span><span class="num">' + fmtSub(d.s) + '訂閱</span>' : '') +
        '</div>' +
      '</div>' +
      '<div class="views"><div class="n">' + fmt(d.v) + '</div>' +
        '<div class="track"><div class="fill ' + cls + '" style="width:' + (d.v/MAXV*100).toFixed(1) + '%"></div></div></div>' +
      '<div class="dur num">' + d.d + 's</div>' +
      '<div class="lr num">' + (d.lr ? d.lr + '%' : '—') + '</div>' +
      '<div class="date num">' + (d.u || '—') + '</div>';
    frag.append(li);
  });
  list.append(frag);
  shown += slice.length;
  moreBtn.hidden = shown >= current.length;
  moreBtn.textContent = '載入更多（還有 ' + (current.length - shown) + ' 支）';
  countEl.textContent = current.length + ' 支符合 · 顯示 ' + shown;
  if (!current.length && !list.querySelector('.empty')){
    list.innerHTML = '<li class="empty">沒有符合條件的影片</li>';
  }
}

document.querySelectorAll('.chip').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.chip').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  filter = b.dataset.f;
  render(true);
}));
['q','genre','sort'].forEach(id => document.getElementById(id).addEventListener('input', () => render(true)));
moreBtn.addEventListener('click', () => render(false));
render(true);
</script>
"""

page = page.replace("__DATA__", DATA)
open("shorts-report.html", "w", encoding="utf-8").write(page)
print(f"寫出 shorts-report.html  {len(page)/1024:.0f} KB  ({len(slim)} 支)")
