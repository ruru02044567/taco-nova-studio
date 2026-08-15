# -*- coding: utf-8 -*-
"""開拍前先判斷「這個鏡頭該用哪個模型」，並把決定寫進 state.json。

為什麼要有這支（2026-08-14 賢賢定的規則）：
    過去選模型的邏輯是「Veo 有額度就用 Veo，沒有就退本機」——
    那是看方便，不是看能力。結果 D7 花了兩輪去演「拖鞋被傳送門吞掉」，
    而本機模型**在原理上就做不到**需要物理連續性的漸進消失。
    那兩輪算力是純浪費，而且事前就可以知道會浪費。

    新規則：先判斷動作複雜度 → 查能力表 → 選模型。
    方便但做不好的模型不叫自動化。

能力分數與門檻全部放在 model_policy.json，這支程式只做判斷不存資料。
模型變強了就重跑 benchmark 更新那個檔，程式不用動。

用法：
    python plan_model.py --text "Taco 把拖鞋叼起來丟進傳送門"
    python plan_model.py --shot d8s1 --text "..."      # 順便寫進 state.json
    python plan_model.py --shot d8s1 --text "..." --force-model VEO   # 人工覆寫
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
    # 正確處理是把它標成「待 benchmark」：正式片先走 Veo 確保交得出來，
    # 同時提醒該花一支的成本把這格補起來，能力表才會長大（賢賢的規則十三）。
    unknown = [k for k in hits if tasks[k]["local"] is None]
    if unknown:
        return {
            "model": force or "VEO",
            "motion_class": f"M{m}",
            "matched_tasks": hits,
            "bottleneck": unknown[0],
            "local_min_score": None,
            "reason": f"動作複雜度 M{m}；「{'、'.join(unknown)}」本機從來沒測過，"
                      f"能力表是空的。正式片先走 Veo；"
                      f"想省錢的話另外排一輪 benchmark 把這格填起來再說。",
            "needs_benchmark": unknown,
            "needs_human": False,
            "policy_version": POLICY["version"],
        }

    # 取所有命中任務裡「本機最不行」的那一項當瓶頸 —— 一支片只要有一個鏡頭做不到就是做不到
    worst = min(hits, key=lambda k: tasks[k]["local"])
    local_min = tasks[worst]["local"]

    if force:
        model, reason = force, f"人工指定 {force}（自動判斷原為瓶頸 {worst}={local_min}）"
    elif local_min >= thr["local_ok"]:
        model = "LOCAL_WAN"
        reason = (f"動作複雜度 M{m}；瓶頸任務「{worst}」本機 {local_min} 分 "
                  f"≥ {thr['local_ok']} → 本機可正式使用")
    elif local_min >= thr["local_test"] and m <= thr["local_test_max_m"]:
        model = "LOCAL_WAN_TRIAL"
        reason = (f"動作複雜度 M{m}；瓶頸任務「{worst}」本機 {local_min} 分，"
                  f"可以先本機試拍，但不保證能用；失敗一次就換 Veo，不要重試同一條 workflow")
    else:
        model = "VEO"
        reason = (f"動作複雜度 M{m}；瓶頸任務「{worst}」本機只有 {local_min} 分 "
                  f"< {thr['local_test']} → 本機做不到，直接用 Veo，不要浪費算力試")

    return {
        "model": model,
        "motion_class": f"M{m}",
        "matched_tasks": hits,
        "bottleneck": worst,
        "local_min_score": local_min,
        "reason": reason,
        "needs_human": False,
        "policy_version": POLICY["version"],
    }


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
    if d["needs_human"]:
        print("  ⚠️ 需要人確認")

    if shot:
        st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
        st.setdefault(shot, {})["model_selection"] = {**d, "script": text}
        # 用 Python 改 JSON，不要手改 —— 8/14 手改 rejected.json 漏一個逗號，
        # publish_video.py 讀不到黑名單時會靜默跳過檢查，等於保護整個失效
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已寫進 state.json 的 {shot}.model_selection")
