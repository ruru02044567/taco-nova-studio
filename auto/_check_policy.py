# -*- coding: utf-8 -*-
"""回歸測試：把 schedule.json 全部 19 支丟進 plan_model，印出判定分布。

用途：改動 model_policy.json 的關鍵字之後，確認
  (1) 本機做不到的鏡頭真的會被擋下來（不再因為中英文錯配而放行）
  (2) 沒有矯枉過正，把整條產線鎖死

用法：cd auto && python _check_policy.py
"""
import json
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

import plan_model

sched = json.load(open("schedule.json", encoding="utf-8"))["schedule"]

POL = plan_model.POLICY["tasks"]


def evidence(prompt, task):
    """回傳這個任務在 prompt 裡實際命中的關鍵字，當佐證。"""
    t = prompt.lower()
    return [k for k in POL[task]["keywords"] if k.lower() in t]


rows = []
for it in sched:
    key = f"d{it['day']}s{it['slot']}"
    topic = " ".join(str(it.get(f, "")) for f in ("title", "oneLine", "scenePrompt"))
    d = plan_model.decide(it["videoPrompt"], topic_text=topic)
    verdict = d.get("model", "?")
    if d.get("blocked_by") == "material":
        verdict = "BLOCKED(材質)"
    bn = d.get("bottleneck") or ""
    # 材質規則的 bottleneck 是「材質：發光體」，不在 tasks 表裡 —— 直接用它自己的命中詞
    if d.get("material"):
        ev = d["material"]["hits"]
    else:
        ev = evidence(it["videoPrompt"], bn) if bn in POL else []
    rows.append((key, verdict, bn, ev))

print("判定分布：", dict(Counter(v for _, v, _, _ in rows)))
print()
for key, verdict, bn, ev in rows:
    mark = "★" if key == "d9s1" else " "
    print(f"{mark} {key:7} {verdict:16} 瓶頸={bn:8} 命中={ev[:6]}")
