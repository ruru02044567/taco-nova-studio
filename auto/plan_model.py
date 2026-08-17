# -*- coding: utf-8 -*-
"""開拍前先判斷「這個鏡頭該用哪個模型」，並把決定寫進 state.json。

為什麼要有這支（2026-08-14 賢賢定的規則）：
    過去選模型的邏輯是「Veo 有額度就用 Veo，沒有就退本機」——
    那是看方便，不是看能力。結果 D7 花了兩輪去演「拖鞋被傳送門吞掉」，
    而本機模型**在原理上就做不到**需要物理連續性的漸進消失。
    那兩輪算力是純浪費，而且事前就可以知道會浪費。

    新規則：先判斷動作複雜度 → 查能力表 → 選模型。
    方便但做不好的模型不叫自動化。

2026-08-16 改為全本機（賢賢定案）：
    Veo 這條出路關掉了，所以這支程式的輸出從「選哪個模型」變成
    「這個劇本本機拍不拍得出來」。本機做不到時不再退 Veo，而是回 BLOCKED
    並附上改寫方向 —— 因為現在唯一的出路是改劇本，不是換模型。

    這支程式的價值反而變大了：以前判錯只是多花 15 點雲端額度，
    現在判錯是白燒 6.5 分鐘算力再加一輪審片。

能力分數與門檻全部放在 model_policy.json，這支程式只做判斷不存資料。
模型變強了就重跑 benchmark 更新那個檔，程式不用動。
（policy 的 veo 欄位保留當分數錨點，但不再是可選的出路。）

用法：
    python plan_model.py --text "Taco 把拖鞋叼起來丟進傳送門"
    python plan_model.py --shot d8s1 --text "..."      # 順便寫進 state.json
    python plan_model.py --shot d8s1 --text "..." --force-model LOCAL_WAN   # 人工覆寫
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
POLICY = json.loads((HERE / "model_policy.json").read_text(encoding="utf-8"))
STATE = HERE / "state.json"


def classify(text):
    """把劇本描述比對到能力表上的任務類型。

    刻意用關鍵字而不是叫 AI 判斷：這支要能在無人排程裡跑，
    結果必須可重現、可稽核。比對不到就回空，由上層退到「人工判斷」，
    不要讓它自己猜 —— 猜錯的代價是燒掉半小時算力生一支必崩的片。
    """
    t = text.lower()
    hits = []
    for task, spec in POLICY["tasks"].items():
        if any(k.lower() in t for k in spec["keywords"]):
            hits.append(task)
    return hits


def decide(text, force=None):
    hits = classify(text)
    tasks = POLICY["tasks"]

    if not hits:
        return {
            "model": force or POLICY["defaults"]["unmatched_model"],
            "motion_class": None,
            "matched_tasks": [],
            "local_min_score": None,
            "reason": "劇本描述比對不到任何已知任務類型 → 依規則退到人工判斷"
                      f"，暫定 {POLICY['defaults']['unmatched_model']}。"
                      "請補關鍵字到 model_policy.json，或直接指定 --force-model。",
            "needs_human": True,
        }

    m = max(tasks[k]["m_level"] for k in hits)
    thr = POLICY["thresholds"]

    # 能力表上還是空格（local: null）＝這件事我們從來沒測過。
    # 這種情況不可以用猜的填一個分數然後照它走 —— 那就變成把推測當成證據。
    # 舊版遇到這格是退 Veo 確保交得出來；全本機之後沒有這條退路了，
    # 改成「試拍一次順便把這格填起來」，並標 needs_human 讓人知道這支是在補能力表。
    unknown = [k for k in hits if tasks[k]["local"] is None]
    if unknown:
        return {
            "model": force or "LOCAL_WAN_TRIAL",
            "motion_class": f"M{m}",
            "matched_tasks": hits,
            "bottleneck": unknown[0],
            "local_min_score": None,
            "reason": f"動作複雜度 M{m}；「{'、'.join(unknown)}」本機從來沒測過，"
                      f"能力表是空的。全本機模式沒有退路可退 → 本機試拍一支，"
                      f"順便把這格填進能力表；結果好壞都要回填 MODEL_CAPABILITY.md。",
            "needs_benchmark": unknown,
            "needs_human": True,
            "policy_version": POLICY["version"],
        }

    # 取所有命中任務裡「本機最不行」的那一項當瓶頸 —— 一支片只要有一個鏡頭做不到就是做不到
    worst = min(hits, key=lambda k: tasks[k]["local"])
    local_min = tasks[worst]["local"]
    rewrite = tasks[worst].get("rewrite")

    out = {
        "motion_class": f"M{m}",
        "matched_tasks": hits,
        "bottleneck": worst,
        "local_min_score": local_min,
        "needs_human": False,
        "policy_version": POLICY["version"],
    }

    if force:
        out["model"] = force
        out["reason"] = f"人工指定 {force}（自動判斷原為瓶頸 {worst}={local_min}）"
    elif local_min >= thr["local_ok"]:
        out["model"] = "LOCAL_WAN"
        out["reason"] = (f"動作複雜度 M{m}；瓶頸任務「{worst}」本機 {local_min} 分 "
                         f"≥ {thr['local_ok']} → 本機可正式使用")
    elif local_min >= thr["local_test"] and m <= thr["local_test_max_m"]:
        out["model"] = "LOCAL_WAN_TRIAL"
        out["reason"] = (f"動作複雜度 M{m}；瓶頸任務「{worst}」本機 {local_min} 分，"
                         f"可以先本機試拍，但不保證能用；失敗一次就改劇本，"
                         f"不要重試同一條 workflow（實測重試不會變好）")
    else:
        # 全本機模式的核心分支：本機做不到就擋下來要求改劇本。
        # 舊版這裡是 return VEO —— 那條路已經關了，而「照生讓審片擋」等於
        # 每次白燒 6.5 分鐘算力再加一輪審片，事前就知道會浪費的事不該做。
        out["model"] = "BLOCKED"
        out["needs_human"] = True
        out["rewrite_hint"] = rewrite
        play = POLICY.get("rewrite_playbook", {})
        out["playbook"] = {k: play[k] for k in play
                           if not k.startswith("_") and rewrite and k in rewrite}
        out["reason"] = (f"動作複雜度 M{m}；瓶頸任務「{worst}」本機只有 {local_min} 分 "
                         f"< {thr['local_test']} → ⛔ 本機做不到，這輪不生。"
                         f"改劇本繞開，不要硬拍。")

    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    text = a[a.index("--text") + 1] if "--text" in a else None
    shot = a[a.index("--shot") + 1] if "--shot" in a else None
    force = a[a.index("--force-model") + 1] if "--force-model" in a else None
    if not text:
        print(__doc__)
        sys.exit(1)

    d = decide(text, force)
    print(f"\n劇本：{text}")
    print(f"  動作複雜度   {d['motion_class']}")
    print(f"  命中任務     {', '.join(d['matched_tasks']) or '（無）'}")
    print(f"  MODEL_SELECTION = {d['model']}")
    print(f"  理由         {d['reason']}")
    if d.get("rewrite_hint"):
        print(f"\n  ✏️ 建議改寫   {d['rewrite_hint']}")
        for name, how in d.get("playbook", {}).items():
            print(f"     └ {name}：{how}")
    if d["needs_human"]:
        print("\n  ⚠️ 需要賢賢確認")

    if shot:
        st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
        st.setdefault(shot, {})["model_selection"] = {**d, "script": text}
        # 用 Python 改 JSON，不要手改 —— 8/14 手改 rejected.json 漏一個逗號，
        # publish_video.py 讀不到黑名單時會靜默跳過檢查，等於保護整個失效
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已寫進 state.json 的 {shot}.model_selection")
