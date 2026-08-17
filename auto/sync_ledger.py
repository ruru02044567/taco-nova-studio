# -*- coding: utf-8 -*-
r"""
sync_ledger.py — 公司帳本自動同步（2026-08-18 建立）

唯一資料源：財富密碼\auto\state.json（產線發布真相）
動作：
  1. C:\AI-COMPANY\06_OPERATIONS\metrics.jsonl 缺的 publish 事件自動補登
     （以 URL 去重，REL 編號接續既有最大值）
  2. 重新生成 C:\AI-COMPANY\06_OPERATIONS\LEDGER_AUTO.md（即時帳本，勿手改）
用法：python auto\sync_ledger.py（發布後跑一次）
設計原則：只追加不改寫 metrics.jsonl；LEDGER_AUTO.md 整檔重生；不碰任何手寫文件。
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOCO = Path(r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼")
OPS = Path(r"C:\AI-COMPANY\06_OPERATIONS")
STATE = TOCO / "auto" / "state.json"
SCHEDULE = TOCO / "auto" / "schedule.json"
METRICS = OPS / "metrics.jsonl"
LEDGER = OPS / "LEDGER_AUTO.md"


def load_titles():
    titles = {}
    try:
        sc = json.loads(SCHEDULE.read_text(encoding="utf-8"))
        for item in sc.get("schedule", []):
            key = f"d{item['day']}s{item['slot']}"
            titles[key] = item.get("title", "")
    except Exception as e:
        print(f"[warn] schedule.json 讀取失敗，標題留空：{e}")
    return titles


def main():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    titles = load_titles()

    published = []
    awaiting, approved_unpub, blocked = [], [], []
    for key, e in state.items():
        if not isinstance(e, dict):
            continue
        if e.get("published"):
            published.append({
                "key": key,
                "at": e.get("at", ""),
                "url": e.get("url", ""),
                "title": titles.get(key, "（不在 schedule，可能是 archived）"),
            })
        elif e.get("awaiting_review"):
            awaiting.append(key)
        elif e.get("approved"):
            approved_unpub.append(key)
        elif (e.get("model_selection") or {}).get("model") == "BLOCKED":
            blocked.append(key)
    published.sort(key=lambda x: x["at"])

    # ── metrics.jsonl 補登（append-only，URL 去重）──
    lines = METRICS.read_text(encoding="utf-8").splitlines() if METRICS.exists() else []
    known_urls, max_rel = set(), 0
    for ln in lines:
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        if rec.get("event") == "publish":
            known_urls.add(rec.get("url"))
        m = re.match(r"REL-(\d+)", str(rec.get("rel", "")))
        if m:
            max_rel = max(max_rel, int(m.group(1)))

    added = []
    for p in published:
        if p["url"] in known_urls:
            continue
        max_rel += 1
        rec = {
            "date": p["at"][:10],
            "rel": f"REL-{max_rel:03d}",
            "project": "TOCO",
            "shot": p["key"],
            "event": "publish",
            "platform": "youtube_shorts",
            "url": p["url"],
            "views": None, "impressions": None, "ctr": None, "retention": None,
            "source": "auto/state.json（sync_ledger.py 自動補登）",
            "note": "效能數據待補",
        }
        lines.append(json.dumps(rec, ensure_ascii=False))
        added.append(f"REL-{max_rel:03d} {p['key']}")
    if added:
        METRICS.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ── REL 對照（含剛補的）──
    url_rel = {}
    for ln in lines:
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        if rec.get("event") == "publish":
            url_rel[rec.get("url")] = rec.get("rel", "")

    # ── LEDGER_AUTO.md 整檔重生 ──
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = "\n".join(
        f"| {url_rel.get(p['url'], '?')} | {p['key']} | {p['at'][:16].replace('T', ' ')} | {p['title']} | {p['url']} |"
        for p in published
    )
    LEDGER.write_text(f"""# LEDGER_AUTO — 公司即時帳本（腳本生成，勿手改）

> 生成時間：{now}｜生成器：財富密碼 `auto\\sync_ledger.py`｜資料源：`auto\\state.json`
> 手寫文件與本頁衝突時，以本頁為準。

## 總覽

- 已發布：**{len(published)} 支**（最近 {published[-1]['at'][:16].replace('T', ' ') if published else '—'}）
- 待審核：{len(awaiting)} 支{'（' + '、'.join(awaiting) + '）' if awaiting else ''}
- 已核准未發布：{len(approved_unpub)} 支{'（' + '、'.join(approved_unpub) + '）' if approved_unpub else ''}
- BLOCKED（等改劇本）：{len(blocked)} 支{'（' + '、'.join(blocked) + '）' if blocked else ''}

## 發布明細

| REL | key | 發布時間 | 標題 | URL |
|---|---|---|---|---|
{rows}
""", encoding="utf-8")

    print(f"published={len(published)} awaiting={len(awaiting)} added_to_metrics={len(added)}")
    for a in added:
        print("  +", a)
    print(f"LEDGER_AUTO.md regenerated at {now}")


if __name__ == "__main__":
    main()
