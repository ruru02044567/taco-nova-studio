# -*- coding: utf-8 -*-
r"""
fetch_views.py — 公開觀看數回寫（2026-08-18 建立）

方法沿用 8/17 首次量測：讀 YouTube 公開 watch page 的 ytInitialData
viewCount（不需登入、不碰 Studio、不需 Edge）。曝光／CTR／完播率
要 Studio 才有，不在本腳本範圍。

動作：
  1. 從公司 metrics.jsonl 取全部 publish 事件（URL 清單）
  2. 逐支抓公開觀看數（每支間隔 1.5 秒，禮貌爬取）
  3. 以 measure 事件 append 回 metrics.jsonl（同 8/17 的格式）
用法：python auto\fetch_views.py
建議：發布滿 24 小時後量一次；之後跑 sync_ledger.py 讓 LEDGER 顯示最新數字。
"""
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

METRICS = Path(r"C:\AI-COMPANY\06_OPERATIONS\metrics.jsonl")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
SOURCE = "youtube watch page ytInitialData viewCount（公開數據，非 Studio）"


def video_id(url: str):
    m = re.search(r"[?&]v=([\w-]{6,})", url)
    if m:
        return m.group(1)
    return url.rstrip("/").split("/")[-1].split("?")[0]


def fetch_view_count(url: str):
    watch = f"https://www.youtube.com/watch?v={video_id(url)}"
    req = urllib.request.Request(watch, headers={"User-Agent": UA,
                                                 "Accept-Language": "en-US,en;q=0.8"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    # 只認 videoDetails 區塊內的 viewCount；寬鬆 fallback 會抓到別支影片的數字，
    # 錯數據比沒數據糟，所以抓不到就回 None 讓上層跳過。
    m = re.search(r'"videoDetails"\s*:\s*\{.*?"viewCount"\s*:\s*"(\d+)"', html, re.S)
    return int(m.group(1)) if m else None


def main():
    raw = METRICS.read_text(encoding="utf-8")
    pubs, titles = [], {}
    for ln in raw.splitlines():
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        if rec.get("event") == "publish":
            pubs.append(rec)
        if rec.get("title") and rec.get("url"):
            titles[rec["url"]] = rec["title"]

    today = date.today()
    new_lines = []
    for p in pubs:
        # 單筆壞資料（如壞 date）只跳過該筆，不中斷整輪
        try:
            url = p["url"]
            views = fetch_view_count(url)
            if views is None:
                print(f"[!] {p.get('shot')} 頁面解析不到 viewCount（版面可能改了），跳過")
                continue
            age = (today - date.fromisoformat(p["date"])).days
        except Exception as e:
            print(f"[!] {p.get('shot')} 抓取失敗：{e}")
            continue
        rec = {
            "date": today.isoformat(), "rel": p.get("rel"), "project": "TOCO",
            "shot": p.get("shot"), "event": "measure", "platform": "youtube_shorts",
            "url": url, "title": titles.get(url),
            "views": views, "impressions": None, "ctr": None, "retention": None,
            "age_days": age, "source": SOURCE,
            "note": "fetch_views.py 自動量測",
        }
        new_lines.append(json.dumps(rec, ensure_ascii=False))
        print(f"[ok] {p.get('shot'):>14} {views:>8,} views (day {age})")
        time.sleep(1.5)

    # 真 append-only：附加模式寫新行，絕不重寫整檔（避免 crash 半途毀帳、蓋掉他人寫入）
    if new_lines:
        with open(METRICS, "a", encoding="utf-8") as f:
            if raw and not raw.endswith("\n"):
                f.write("\n")
            f.write("\n".join(new_lines) + "\n")
    print(f"共寫入 {len(new_lines)} 筆 measure（{today}）")


if __name__ == "__main__":
    main()
