# -*- coding: utf-8 -*-
r"""把產線的真實進度回寫到 G-Brain 的專案索引。

為什麼需要這支：
2026-08-11 發現 `G-Brain\01-專案\_索引.md` 還寫著財富密碼「萬事俱備，只差開拍」，
但那時候已經發了 6 支、12 萬觀看。**過期的共用記憶比沒有記憶更危險** ——
別的對話視窗會照著那句話做事，而且講得跟真的一樣。

會過期的根本原因是「做完沒回寫」，靠人記得沒有用。所以改成產線自己寫。

設計上刻意保守：
- 只重寫 `_索引.md` 裡 AUTO 標記之間的那一段，**人寫的部分一個字都不碰**
- 找不到標記就什麼都不做（不亂插內容）
- 內容全部從 `state.json` 和 `schedule.json` 算出來，不猜
- 被 pipeline.py 呼叫時包在 try/except 裡，**這支掛掉不能影響發布**

用法：
    python sync_gbrain.py          # 回寫
    python sync_gbrain.py --dry    # 只印出會寫什麼，不動檔案
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
STATE = HERE / "state.json"
SCHEDULE = HERE / "schedule.json"
INDEX = Path(r"C:\Users\TUF Gaming\.claude\G-Brain\01-專案\_索引.md")

BEGIN = "<!-- AUTO:財富密碼進度 -->"
END = "<!-- /AUTO:財富密碼進度 -->"


def build_block():
    """從產線的狀態檔算出現況，回傳要寫進索引的那一段 markdown。"""
    state = json.loads(STATE.read_text(encoding="utf-8"))
    sched = json.loads(SCHEDULE.read_text(encoding="utf-8"))

    # 只算真正發布過的（有 url 的才算數，光有 published 旗標不夠）
    published = [(k, v) for k, v in state.items()
                 if v.get("published") and v.get("url")]
    published.sort(key=lambda kv: kv[1].get("at", ""))

    # 卡在等審核的 —— 這是會讓整條產線停住的東西，一定要寫出來
    waiting = [k for k, v in state.items()
               if v.get("awaiting_review") and not v.get("published")]

    titles = {f"d{i['day']}s{i['slot']}": i["title"] for i in sched["schedule"]}
    total = len(sched["schedule"])

    lines = [
        BEGIN,
        f"> 這一段由 `財富密碼\\auto\\sync_gbrain.py` 自動維護，"
        f"最後更新 {datetime.now():%Y-%m-%d %H:%M}（台北）。**不要手動改這裡。**",
        "",
        f"**已發布 {len(published)} 支** / 排程共 {total} 支。",
        "",
    ]

    if published:
        if len(published) > 5:
            lines.append(f"更早之前還有 {len(published) - 5} 支沒列出來。最近 5 支：")
            lines.append("")
        lines += ["| 影片 | 標題 | 發布時間 | 網址 |", "|---|---|---|---|"]
        for k, v in published[-5:]:                      # 只列最近 5 支，索引不要被灌爆
            # archived-* 是開台初期的紀錄，不在現行排程裡，schedule 查不到標題
            title = titles.get(k) or v.get("title") or "（開台初期，不在現行排程）"
            at = (v.get("at") or "")[:16].replace("T", " ")
            lines.append(f"| {k.upper()} | {title[:44]} | {at} | {v['url']} |")
        lines.append("")

    if waiting:
        names = "、".join(k.upper() for k in waiting)
        lines += [
            f"⚠️ **{names} 正卡在「等賢賢過目」，整條產線因此停住。**",
            "`pipeline.py` 的規則是「只要有東西在等過目就完全不動作」，"
            "所以在這支被核准或跳過之前，**下一支不會開始生**。",
            f"處理方式見 `財富密碼\\接手-下次開機.md`。",
            "",
        ]
    else:
        lines += ["目前沒有卡在等審核的片子，產線可以自己往下跑。", ""]

    lines.append(END)
    return "\n".join(lines)


def strip_stamp(s):
    """把「最後更新 …」那一行拿掉再比對。

    不這樣做的話，時間戳每次都不同 → 兩份內容永遠不相等 → 「沒變就不寫檔」
    這個保護等於失效，每次發布都會動到檔案的修改時間，
    看起來像索引有更新，其實只有時間戳在跳。
    """
    return "\n".join(ln for ln in s.splitlines() if "最後更新" not in ln)


def main():
    dry = "--dry" in sys.argv

    if not INDEX.exists():
        print(f"SKIP: 找不到 {INDEX}")
        return 0

    text = INDEX.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        print("SKIP: 索引裡沒有 AUTO 標記，不主動插入（要啟用請先手動加上標記）")
        return 0

    block = build_block()
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    new_text = head + block + tail

    if dry:
        print(block)
        return 0

    if strip_stamp(new_text) == strip_stamp(text):
        print("內容沒變，不寫檔")
        return 0

    INDEX.write_text(new_text, encoding="utf-8")
    print(f"已回寫 {INDEX.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
