# -*- coding: utf-8 -*-
r"""角色聖經接線（2026-08-23 建立，賢賢裁示「以後製作影片就把角色聖經掛上」）。

## 為什麼需要

在此之前 `character\角色設定.md` 是一份**沒有任何程式讀的文件**
（`grep -rn "角色設定" --include="*.py"` 零命中），而角色描述被整段複製在
schedule.json 裡 —— 19 支排程有 17 支各存一份，改角色要改 17 個地方。
文件裡自己寫的機制「每次生成都附定裝照＋角色描述句一字不改」也早就沒在執行。

這支把它變成**生成前的硬檢查**：招牌特徵沒寫進 prompt 就擋下來，
不要等生完 6.3 分鐘才發現 Taco 沒有黑點眉。

## 用法

    import character_bible as cb
    cb.require(prompt, ["taco", "nova"])      # 缺特徵就 sys.exit(11)
    ok, problems = cb.check(prompt, ["taco"]) # 只回報不中斷
    cb.taco()                                  # 取 canonical 描述句

真相在 `character\角色聖經.json`（程式讀這個），
`character\角色設定.md` 是給人看的沿革，**有過期內容，程式不讀**。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BIBLE = Path(__file__).resolve().parent.parent / "character" / "角色聖經.json"


def load():
    if not BIBLE.is_file():
        print(f"[!] 找不到角色聖經：{BIBLE}")
        return None
    return json.loads(BIBLE.read_text(encoding="utf-8"))


def canonical(who):
    d = load()
    return d["characters"][who]["canonical_prompt"] if d else ""


def taco():
    return canonical("taco")


def nova():
    return canonical("nova")


def check(prompt, who=("taco",)):
    """回傳 (是否合格, 問題清單)。比對 must_appear 的關鍵詞，不強求整段一字不差
    —— 臉部特寫這類合法變體會改寫描述，強求整段會誤擋（schedule 裡就有 2 支）。"""
    d = load()
    if not d:
        return True, []          # 聖經讀不到就不擋，只在上游印警告
    low = prompt.lower()
    problems = []
    for w in who:
        c = d["characters"].get(w)
        if not c:
            problems.append(f"聖經裡沒有角色「{w}」")
            continue
        missing = [k for k in c["must_appear"] if k.lower() not in low]
        if missing:
            problems.append(f"{c['name']} 缺少招牌特徵：{'／'.join(missing)}　→ {c['signature']}")
    return (not problems), problems


def require(prompt, who=("taco",), skip=False):
    """硬閘門版：不合格就中止（exit 11）。skip=True 時只警告不擋。"""
    ok, problems = check(prompt, who)
    if ok:
        print(f"[bible] 角色聖經檢查通過（{'／'.join(who)}）")
        return True
    print("[bible] ⛔ 角色聖經檢查不過：")
    for p in problems:
        print("   -", p)
    if skip:
        print("   （--skip-bible 已指定，放行，但這支片的角色一致性自己負責）")
        return False
    print("   要改 prompt，或確定要照生就加 --skip-bible")
    sys.exit(11)


def which(prompt):
    """這支 prompt 要檢查哪些角色。

    ⚠️ Taco 一律檢查，不看 prompt 有沒有提到他 —— 第一版寫成「有 chihuahua 才檢查
    taco」，結果一支完全沒寫主角的 prompt 反而全部放行，那正是最該擋的情況。
    Nova 是配角，只有 prompt 打算讓他入鏡時才檢查。"""
    who = ["taco"]
    if "husky" in prompt.lower():
        who.append("nova")
    return who


if __name__ == "__main__":
    d = load()
    if not d:
        sys.exit(1)
    print(f"角色聖經 v{d['version']}")
    for k, c in d["characters"].items():
        print(f"\n── {c['name']}（{c['role']}）")
        print(f"   招牌：{c['signature']}")
        print(f"   必要詞：{'／'.join(c['must_appear'])}")
        print(f"   已知問題：{c['已知問題'][:70]}…")
    print("\n紅線：")
    for r in d["redlines"]:
        print("   -", r)
