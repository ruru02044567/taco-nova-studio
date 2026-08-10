# -*- coding: utf-8 -*-
"""把重排好的 19 支併進 schedule.json，並從一天 3 支改成一天 1 支（台北 08:00）"""
import json
import shutil
from pathlib import Path

HERE = Path(__file__).parent
SCHED = HERE / "schedule.json"
STATE = HERE / "state.json"
NEW = HERE / "newsched"

# 1) 備份舊的
shutil.copy(SCHED, HERE / "schedule-v1-三支制.json")
shutil.copy(STATE, HERE / "state-v1.json")

# 2) 收齊 19 支，照原本指定的 (day, slot) 順序排 —— 黑洞排第一
items = []
for f in sorted(NEW.glob("batch-*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    items += d if isinstance(d, list) else d.get("items", [])
items.sort(key=lambda i: (i["day"], i["slot"]))
assert len(items) == 19, f"支數不對：{len(items)}"

# 3) 重新編號成一天 1 支：day 1..19，slot 1（= 台北 08:00 = 美東 20:00 黃金時段）
for n, it in enumerate(items, start=1):
    it["day"], it["slot"] = n, 1

old = json.loads(SCHED.read_text(encoding="utf-8"))
SCHED.write_text(json.dumps({
    "day1_date": "2026-08-08",
    "note": "一天 1 支，台北 08:00 發（美東 20:00 黃金時段）。"
            "題材照對標帳號 Tim and Jeffy 的爆款公式重排：闖禍→藏罪證→越藏越糟→裝無辜。"
            "舊的三支制排程備份在 schedule-v1-三支制.json。",
    "schedule": items,
}, ensure_ascii=False, indent=2), encoding="utf-8")

# 4) 已發布那兩支改名封存，免得跟新的 d1s1 撞 key 害新片被跳過
state = json.loads(STATE.read_text(encoding="utf-8"))
for k in ("d1s1", "d1s2"):
    if k in state:
        state[f"archived-{k}"] = state.pop(k)
STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"排程已更新：{len(items)} 支，一天 1 支，8/8 起算")
for it in items[:5]:
    print(f"  D{it['day']}  {it['title']}")
print(f"  ...（共 {len(items)} 支，到 D{items[-1]['day']}）")
print("state 已封存：", [k for k in state if k.startswith("archived")])
