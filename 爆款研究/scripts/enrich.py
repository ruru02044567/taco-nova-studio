# -*- coding: utf-8 -*-
"""用 oEmbed 取回正確 UTF-8 標題與頻道名（修 CJK 亂碼）"""
import json, os, time, urllib.request, urllib.parse, concurrent.futures, random

shorts = json.load(open("shorts_final.json", encoding="utf-8"))
meta = {}
if os.path.exists("oembed.json"):
    meta = json.load(open("oembed.json", encoding="utf-8"))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

def fetch(vid):
    url = ("https://www.youtube.com/oembed?url="
           + urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}", safe="")
           + "&format=json")
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read().decode("utf-8"))
                return vid, {"title": d.get("title", ""),
                             "channel": d.get("author_name", ""),
                             "channel_url": d.get("author_url", "")}
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                return vid, None          # 影片私人化/刪除
            time.sleep(2 + attempt * 3)
        except Exception:
            time.sleep(1 + attempt * 2)
    return vid, None

todo = [s["id"] for s in shorts if s["id"] not in meta]
print(f"要補 {len(todo)} 支（已有 {len(meta)}）", flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    for i, (vid, d) in enumerate(ex.map(fetch, todo), 1):
        if d:
            meta[vid] = d
        if i % 100 == 0:
            print(f"  ...{i}/{len(todo)}  成功 {len(meta)}", flush=True)
            json.dump(meta, open("oembed.json", "w", encoding="utf-8"), ensure_ascii=False)

json.dump(meta, open("oembed.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"完成：{len(meta)}/{len(shorts)} 支拿到正確標題")
