# -*- coding: utf-8 -*-
"""用 ios client 繞過 bot 檢查，補上傳日期／按讚數／訂閱數"""
import json, os, subprocess, concurrent.futures

shorts = json.load(open("final.json", encoding="utf-8"))
meta = {}
if os.path.exists("stats.json"):
    meta = json.load(open("stats.json", encoding="utf-8"))

CMD = ["yt-dlp", "--extractor-args", "youtube:player_client=ios",
       "--ignore-no-formats-error", "--no-warnings", "--skip-download", "--no-playlist",
       "--print", "%(upload_date)s|%(like_count)s|%(comment_count)s|%(channel_follower_count)s|%(view_count)s|%(duration)s"]

def grab(vid):
    for _ in range(2):
        try:
            p = subprocess.run(CMD + [f"https://www.youtube.com/watch?v={vid}"],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=75)
            line = (p.stdout or "").strip().split("\n")[-1]
            f = line.split("|")
            if len(f) < 6:
                continue
            num = lambda x: int(x) if x.isdigit() else None
            return vid, {"upload": f[0] if f[0].isdigit() else None,
                         "likes": num(f[1]), "comments": num(f[2]),
                         "subs": num(f[3]), "views2": num(f[4]), "dur2": num(f[5])}
        except Exception:
            pass
    return vid, None

todo = [s["id"] for s in shorts if s["id"] not in meta]
print(f"要補 {len(todo)} 支（已有 {len(meta)}）", flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
    for i, (vid, d) in enumerate(ex.map(grab, todo), 1):
        if d:
            meta[vid] = d
        if i % 50 == 0:
            print(f"  ...{i}/{len(todo)}  成功 {len(meta)}", flush=True)
            json.dump(meta, open("stats.json", "w", encoding="utf-8"), ensure_ascii=False)

json.dump(meta, open("stats.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"完成：{len(meta)}/{len(shorts)} 支拿到完整數據")
