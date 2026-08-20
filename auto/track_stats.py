# -*- coding: utf-8 -*-
"""抓已發布影片的實際成效，累積成時間序列。

為什麼要有這支（2026-08-20 賢賢指示）：
    8/12 到 8/20 之間發了 8 支片，一支的成效都沒有被記錄下來。
    產線一路在加閘門、加自審、加對標稽核，全部在回答「片子做得好不好」，
    沒有一項在回答「發出去有沒有人看」。沒有量測就沒有可行性驗證。

    更關鍵的是 8/12 那份分析踩過的坑：它拿「發布 48 小時」的數字判生死，
    把 D3S1 記成 64 觀看的失敗品。那支後來跑到 31,845。
    **Shorts 會延遲綻放，單一時間點的快照會騙人**，所以這支存的是時間序列不是快照。

用法：
    python auto\track_stats.py            # 抓一輪，附加一筆快照，重寫 md
    python auto\track_stats.py --md-only  # 不連網，只從既有資料重畫 md
"""
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
ROOT = HERE.parent
STATE = HERE / "state.json"
DATA = HERE / "成效追蹤.json"
REPORT = ROOT / "成效追蹤.md"
TPE = timezone(timedelta(hours=8))

# 對標頻道 Tim and Jeffy 的同題材片（2026-08-20 抓的快照）。
# 存在這裡是為了回答「同一個題材，對方做起來是幾百萬，我做起來是幾百」——
# 題材是抄的，所以題材不是變因。這張表是拿來把變因排除掉的，不是拿來選題的。
BENCH = {
    "d1s1":  ("Tries To Hide A Black Hole",        535_000_000),
    "d2s1":  ("Clean Chocolate Off A White Rug",    52_000_000),
    "d5s1":  ("Tries to Save Tim From Lava",         1_200_000),
    "d6s1":  ("Knocks Over a Plant",                74_000_000),
    "d7s1":  ("Finds a Purple Portal",              75_000_000),
    "d8s1":  ("Spills Pink Slime and Tries to Hide", 57_000_000),
    "d9s1":  ("Spills Drink and Tries to Clean",    51_000_000),
    "d10s1": ("Clean Raw Egg Mess Off The Bed",     25_000_000),
    "d11s1": ("Turns Into A Panda",                 21_000_000),
    "d12s1": ("Spills Black Ink On A White Rug",     1_400_000),
    "d14s1": ("Everything Touches Turns Into Gold",  1_700_000),
}

FIELDS = "%(id)s|%(view_count)s|%(like_count)s|%(comment_count)s|%(duration)s|%(upload_date)s|%(title)s"


def _num(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def fetch_one(url):
    """yt-dlp 單支。抓不到回 None，不讓一支失敗打斷整輪。"""
    try:
        r = subprocess.run(
            ["yt-dlp", "--skip-download", "--no-warnings", "--print", FIELDS, url],
            capture_output=True, text=True, encoding="utf-8", timeout=90,
        )
    except subprocess.TimeoutExpired:
        return None
    line = (r.stdout or "").strip().splitlines()
    if not line:
        return None
    p = line[-1].split("|", 6)
    if len(p) < 7:
        return None
    return {
        "videoId": p[0], "views": _num(p[1]), "likes": _num(p[2]),
        "comments": _num(p[3]), "duration": _num(p[4]),
        "uploadDate": p[5], "title": p[6],
    }


def load(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def snapshot():
    state = load(STATE, {})
    targets = [(k, v["url"]) for k, v in state.items()
               if isinstance(v, dict) and v.get("published") and v.get("url")]
    now = datetime.now(TPE).isoformat(timespec="seconds")
    rows = []
    for key, url in targets:
        got = fetch_one(url)
        if not got:
            print(f"  ✗ {key} 抓不到，跳過（不算失敗，下輪再抓）")
            continue
        got.update({"key": key, "url": url,
                    "source": state[key].get("source"),
                    "publishedAt": state[key].get("at")})
        rows.append(got)
        print(f"  ✓ {key:12s} {got['views']:>10,} 觀看")
    db = load(DATA, {"snapshots": []})
    db["snapshots"].append({"takenAt": now, "rows": rows})
    DATA.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    return db


def bucket(v):
    """雙峰分類。實測這個頻道沒有中間值：不是被推進 feed 就是死透。"""
    if v is None:
        return "?"
    if v >= 10_000:
        return "推了"
    if v >= 1_000:
        return "半推"
    return "沒推"


def render(db):
    snaps = db["snapshots"]
    latest = snaps[-1]
    prev = snaps[-2] if len(snaps) > 1 else None
    prev_map = {r["key"]: r["views"] for r in prev["rows"]} if prev else {}

    rows = sorted(latest["rows"], key=lambda r: r["views"] or 0, reverse=True)
    total = sum(r["views"] or 0 for r in rows)
    hits = [r for r in rows if (r["views"] or 0) >= 10_000]

    L = []
    L.append("# 成效追蹤 — Taco & Nova")
    L.append("")
    L.append(f"> 最後更新：{latest['takenAt'][:16]}（台北）　"
             f"｜　資料點 {len(snaps)} 筆　｜　重跑：`python auto\track_stats.py`")
    L.append("")
    L.append("⚠️ **不要拿發布 48 小時內的數字判生死。** 8/12 那份分析把 D3S1 記成 "
             "64 觀看的失敗品，那支後來跑到 3 萬。Shorts 會延遲綻放。")
    L.append("")
    L.append(f"## 總覽")
    L.append("")
    L.append(f"- 已發布 **{len(rows)}** 支，總觀看 **{total:,}**")
    L.append(f"- 破萬 **{len(hits)}** 支，佔 **{len(hits)/len(rows)*100:.0f}%**")
    L.append(f"- 最好 **{rows[0]['views']:,}**　最差 **{rows[-1]['views']:,}**　"
             f"相差 **{(rows[0]['views'] or 1)//max(rows[-1]['views'] or 1,1):,} 倍**")
    L.append("")
    L.append("## 逐支成效")
    L.append("")
    L.append("| 影片 | 觀看 | 較上次 | 讚 | 讚/看 | 生成 | 發布 | 狀態 | 對標同題材 |")
    L.append("|---|--:|--:|--:|--:|:--:|---|:--:|--:|")
    for r in rows:
        v = r["views"] or 0
        d = v - prev_map[r["key"]] if r["key"] in prev_map else None
        dtxt = f"+{d:,}" if d and d > 0 else ("—" if d is None else f"{d:,}")
        lk = r["likes"] or 0
        rate = f"{lk / v * 100:.2f}%" if v else "—"
        b = BENCH.get(r["key"])
        btxt = f"{b[1]:,}" if b else "—"
        title = (r["title"] or "")[:46]
        L.append(f"| {r['key']}　{title} | {v:,} | {dtxt} | {lk:,} | {rate} "
                 f"| {r['source'] or '?'} | {(r['publishedAt'] or '')[:10]} "
                 f"| {bucket(v)} | {btxt} |")
    L.append("")
    L.append("## 怎麼讀這張表")
    L.append("")
    L.append("1. **雙峰，沒有中間值**。破萬的和不到一千的中間幾乎是空的 —— 這是")
    L.append("   YouTube 推薦的閘門在開關，不是品質的漸層。同一條產線、同一隻狗、")
    L.append("   同樣的自審分數，結果差三個數量級。")
    L.append("2. **題材已經不是變因**。整張排程表都是照對標頻道抄的，最右欄就是證據：")
    L.append("   對方巧克力那支 5,200 萬，我們同題材做出來 157。抄對題材不保證會被推。")
    L.append("3. **本機不是死因**。破萬的幾支裡有本機生的。`source` 欄可以直接比對。")
    L.append("4. **最近幾支數字低不一定是失敗**，可能還沒到綻放期。看「較上次」那欄，")
    L.append("   連續兩三次都不動才是真的死了。")
    L.append("")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\n報告寫好：{REPORT}")


if __name__ == "__main__":
    if "--md-only" in sys.argv:
        render(load(DATA, {"snapshots": []}))
    else:
        print("抓取中…")
        render(snapshot())
