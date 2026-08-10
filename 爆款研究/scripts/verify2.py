# -*- coding: utf-8 -*-
"""用 /shorts/<id> 是否被轉址判定真 Shorts（200=Shorts, 303=一般影片）"""
import json, os, urllib.request, concurrent.futures

cands = json.load(open("candidates.json", encoding="utf-8"))
done = {}
if os.path.exists("isshorts.json"):
    done = json.load(open("isshorts.json", encoding="utf-8"))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

opener = urllib.request.build_opener(NoRedirect)

def check(vid):
    req = urllib.request.Request(f"https://www.youtube.com/shorts/{vid}",
                                 headers={"User-Agent": UA}, method="HEAD")
    for _ in range(3):
        try:
            with opener.open(req, timeout=20) as r:
                return vid, (r.status == 200)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                return vid, False
            if e.code == 404:
                return vid, False
        except Exception:
            pass
    return vid, None

todo = [c["id"] for c in cands if c["id"] not in done]
print(f"要判定 {len(todo)} 支（已有 {len(done)}）", flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    for i, (vid, ok) in enumerate(ex.map(check, todo), 1):
        if ok is not None:
            done[vid] = ok
        if i % 100 == 0:
            print(f"  ...{i}/{len(todo)}", flush=True)
            json.dump(done, open("isshorts.json", "w"), ensure_ascii=False)

json.dump(done, open("isshorts.json", "w"), ensure_ascii=False)
yes = sum(1 for v in done.values() if v)
print(f"判定完成：{len(done)} 支有結果，真 Shorts {yes} 支")
