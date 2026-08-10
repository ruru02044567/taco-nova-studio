# -*- coding: utf-8 -*-
"""合併：基本資料 + 統計數據 + AI 分類 → 最終資料集"""
import json, csv
from collections import Counter, defaultdict

base = json.load(open("final.json", encoding="utf-8"))
stats = json.load(open("stats.json", encoding="utf-8"))
wf = json.load(open("../tasks/womm5zal0.output", encoding="utf-8"))

ai = {}
for it in wf["result"]["classified"]:
    ai[it["id"]] = it

rows = []
for b in base:
    vid = b["id"]
    s = stats.get(vid, {})
    a = ai.get(vid, {})
    views = s.get("views2") or b["views"]
    likes = s.get("likes")
    up = s.get("upload")
    rows.append({
        "id": vid,
        "url": f"https://www.youtube.com/shorts/{vid}",
        "title": b["title"],
        "channel": b["channel"],
        "channel_url": b.get("channel_url", ""),
        "views": views,
        "likes": likes,
        "comments": s.get("comments"),
        "subs": s.get("subs"),
        "dur": s.get("dur2") or b["dur"],
        "upload": f"{up[:4]}-{up[4:6]}-{up[6:]}" if up and len(up) == 8 else "",
        "year": up[:4] if up and len(up) == 8 else "",
        "animal": a.get("animal", "未知"),
        "genre": a.get("genre", "未知"),
        "ai_made": a.get("ai_made", False),
        "hook": a.get("hook", ""),
        "like_rate": round(likes / views * 100, 2) if likes and views else None,
        "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
    })

# 優先序：貓 > 狗 > 貓狗同框 > 其他動物 > 動畫 > 無動物
PRI = {"貓": 0, "狗": 1, "貓狗同框": 2}
OTHER = ["猴子", "鳥類", "馬", "牛羊豬農場", "兔鼠倉鼠", "野生動物", "爬蟲海洋", "昆蟲蜘蛛", "其他動物"]
for i, k in enumerate(OTHER):
    PRI[k] = 3 + i
PRI["動畫角色"] = 90
PRI["無動物"] = 99
PRI["未知"] = 100
for r in rows:
    r["pri"] = PRI.get(r["animal"], 100)

rows.sort(key=lambda r: (r["pri"], -r["views"]))
json.dump(rows, open("dataset.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

cols = ["animal", "genre", "views", "likes", "like_rate", "dur", "upload", "channel", "subs", "title", "hook", "ai_made", "url"]
with open("爆款Shorts清單.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

c = Counter(r["animal"] for r in rows)
print(f"總計 {len(rows)} 支\n--- 動物分布 ---")
for k, v in sorted(c.items(), key=lambda x: PRI.get(x[0], 100)):
    print(f"  {k:10} {v:4}")

pets = [r for r in rows if r["animal"] in ("貓", "狗", "貓狗同框")]
print(f"\n貓狗合計 {len(pets)} 支")
print("\n--- 貓狗題材分布 ---")
for k, v in Counter(r["genre"] for r in pets).most_common():
    print(f"  {k:12} {v:3}")
print("\n--- 貓狗片長分布 ---")
buckets = defaultdict(int)
for r in pets:
    d = r["dur"]
    b = "0-10s" if d <= 10 else "11-20s" if d <= 20 else "21-30s" if d <= 30 else "31-45s" if d <= 45 else "46-60s" if d <= 60 else "60s+"
    buckets[b] += 1
for k in ["0-10s", "11-20s", "21-30s", "31-45s", "46-60s", "60s+"]:
    print(f"  {k:8} {buckets[k]:3}")
print("\n--- 貓狗上傳年份 ---")
for k, v in sorted(Counter(r["year"] for r in pets if r["year"]).items()):
    print(f"  {k} {v:3}")
print(f"\nAI 生成內容：{sum(1 for r in rows if r['ai_made'])} 支（貓狗中 {sum(1 for r in pets if r['ai_made'])} 支）")
print("\n--- 多支上榜的頻道 TOP 15（全類別）---")
ch = Counter(r["channel"] for r in rows)
for k, v in ch.most_common(15):
    tot = sum(r["views"] for r in rows if r["channel"] == k)
    print(f"  {v:2} 支 | {tot/1e6:7.0f}M | {k}")
