# -*- coding: utf-8 -*-
"""從 raw/ 抓到的搜尋結果篩出 5000 萬以上、疑似 Shorts 的影片"""
import os, glob, json, sys

THRESHOLD = 50_000_000
MAX_DUR = 185  # Shorts 上限 3 分鐘，留點餘裕

rows = {}
for f in glob.glob("raw/*.txt"):
    for line in open(f, encoding="utf-8", errors="replace"):
        parts = line.rstrip("\n").split("\\t")
        if len(parts) < 5:
            continue
        vc, dur, vid, ch, title = parts[0], parts[1], parts[2], parts[3], " ".join(parts[4:])
        try:
            vc = int(vc)
        except ValueError:
            continue
        try:
            dur = int(float(dur))
        except ValueError:
            dur = -1
        if vc < THRESHOLD:
            continue
        if dur < 0 or dur > MAX_DUR:
            continue
        prev = rows.get(vid)
        if prev is None or vc > prev["views"]:
            rows[vid] = {"id": vid, "views": vc, "dur": dur, "channel": ch, "title": title}

out = sorted(rows.values(), key=lambda r: -r["views"])
json.dump(out, open("candidates.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"候選 {len(out)} 支 (>= {THRESHOLD:,} 觀看, <= {MAX_DUR}s)")
for r in out[:15]:
    print(f'{r["views"]:>12,}  {r["dur"]:>4}s  {r["title"][:60]}')
