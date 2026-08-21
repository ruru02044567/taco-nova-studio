# -*- coding: utf-8 -*-
r"""report.py — 把三個實驗的 results.json 彙整成 EXPERIMENT_REPORT.md（2026-08-21）

## 打分的原則（先講清楚，不然分數只是好看）

滿分 100 分拆成六塊，其中**最後 10 分自動化永遠給不出來**：

| 面向 | 分 | 怎麼給 | 性質 |
|---|---|---|---|
| 接縫品質 transition | 25 | anchor 保真度 ＋ 接縫幀差 | 客觀量測 |
| 動作品質 motion     | 20 | 動作能量 ＋ 速度抖動 | 客觀量測 |
| 連續性 continuity   | 20 | 亮度漂移 ＋ 直方圖漂移 ＋ 前景面積穩定度 | 客觀＋**代理** |
| 畫質 visual         | 15 | Laplacian 銳利度 | 客觀量測 |
| 成本 cost           | 10 | 生成時間 ＋ VRAM 餘裕 | 客觀量測 |
| **人眼項 human**    | 10 | 第三條腿／增生／黑點眉 | **只能由 frame_gate 給，自動一律 0** |

所以**自動分數天花板是 90**。這不是 bug，是設計：
8/20 那次事故的根因就是「視覺類沒東西擋，所以每輪都在打地鼠」。
如果自動打得出 100 分，下一個人就會拿那個 100 分當通行證，跳過逐幀審 ——
把天花板壓在 90，那 10 分只能靠 `auto\frame_gate.py` 換，才擋得住這件事。

門檻的來源一律標註：`實測` ＝ 有量過的數字，`推` ＝ 我訂的、還沒有基線。

用法：python experiments\report.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CHAIN = HERE / "multi_frame_chain" / "out" / "results.json"
PROMPT = HERE / "prompt_ab" / "out" / "results.json"
HIDDEN = HERE / "hidden_cut" / "out" / "results.json"
OUT = HERE / "_docs" / "EXPERIMENT_REPORT.md"


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def band(v, good, bad):
    """v 落在 good（滿分）與 bad（零分）之間，線性給分。good 可以大於或小於 bad。"""
    if good == bad:
        return 1.0
    return clamp((bad - v) / (bad - good))


def score_one(r):
    """回 (總分, 明細 dict)。r 是 chain / prompt 實驗的一筆。"""
    m = r.get("metrics")
    if not m:
        return 0, {"備註": "生成失敗，無法評分"}
    meta = r.get("meta") or {}
    d = {}

    # ── 接縫品質 25 ─────────────────────────────────────────
    # anchor 保真度：生成的前 N 格 vs 餵進去的 N 格。8/20-21 實測落在 2.31–2.74，
    # 那是「VAE 來回一次」的固有誤差，不是品質問題。超過 5 就代表接線出事了。
    af = (m.get("anchor_fidelity") or {}).get("mean_abs_diff")
    if af is None:
        d["接縫保真"] = (12.5, "無接龍或量不到")
    else:
        d["接縫保真"] = (25 * band(af, 2.3, 6.0), f"逐像素平均絕對差 {af}　`實測基線 2.31–2.74`")
    trans = d["接縫保真"][0]

    # ── 動作品質 20 ─────────────────────────────────────────
    # 動作能量：太低＝live wallpaper（Wan 的死穴），太高＝亂動。
    # 已發布片 d10s1 全片 1.809。接龍段量的是新內容，2.5–3.5 是這輪的實際範圍。
    mo = m["motion"]["mean"]
    d["動作幅度"] = (10 * clamp((mo - 1.2) / (3.0 - 1.2)),
                     f"幀間差 {mo}　`推：1.2 以下視為不動、3.0 給滿`")
    # 速度抖動：8/14 十二組實驗量到硬天花板 0.47，越低越流暢
    ji = m["flow"]["jitter"]
    d["速度抖動"] = (10 * band(ji, 0.15, 0.47), f"{ji}　`實測天花板 0.47`")
    motion = d["動作幅度"][0] + d["速度抖動"][0]

    # ── 連續性 20 ───────────────────────────────────────────
    ld = abs(m["luma_drift"]["drift"])
    d["亮度漂移"] = (8 * band(ld, 1.0, 10.0),
                     f"頭尾差 {m['luma_drift']['drift']:+}　`實測：+2.69/+3.35 可接受、-9.81 該校色`")
    hd = m["hist_drift"]["max"]
    d["色彩漂移⚠代理"] = (6 * band(hd, 4.0, 20.0), f"最大卡方距離 {hd}　`推`")
    cv = m["subject_area"]["cv"]
    d["前景穩定⚠代理"] = (6 * band(cv, 0.15, 0.50), f"面積變異係數 {cv}　`推`")
    cont = sum(v[0] for k, v in d.items() if k in ("亮度漂移", "色彩漂移⚠代理", "前景穩定⚠代理"))

    # ── 畫質 15 ─────────────────────────────────────────────
    sh = m["sharpness"]["mean"]
    d["銳利度"] = (15 * clamp((sh - 300) / (700 - 300)),
                   f"Laplacian 變異數 {sh}　`推：d10s1 成品 572`")
    vis = d["銳利度"][0]

    # ── 成本 10 ─────────────────────────────────────────────
    mins = meta.get("minutes") or 0
    vram = meta.get("vram_peak_mb") or 0
    d["生成時間"] = (5 * band(mins, 6.0, 9.0), f"{mins} 分鐘")
    head = 8151 - vram
    d["VRAM 餘裕"] = (5 * clamp(head / 2000), f"峰值 {vram} MB，餘 {head} MB / 8151")
    cost = d["生成時間"][0] + d["VRAM 餘裕"][0]

    # ── 人眼項 10：自動一律 0 ───────────────────────────────
    d["人眼項（第三條腿／增生／黑點眉）"] = (0, "⛔ 自動給不出來，必須跑 auto\\frame_gate.py")

    total = trans + motion + cont + vis + cost
    return round(total, 1), d


def sec_chain():
    if not CHAIN.exists():
        return "（多幀接龍實驗尚未產出 results.json）\n"
    rows = json.loads(CHAIN.read_text(encoding="utf-8"))
    L = ["| 組 | anchor | 新畫面 | 分鐘 | VRAM 峰值 | 接縫保真 | 動作 | 抖動 | 亮度漂移 | 銳利 | **總分/90** |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    detail = []
    for r in rows:
        s, d = score_one(r)
        m, meta = r.get("metrics"), (r.get("meta") or {})
        if not m:
            L.append(f"| {r['id']} | {r['anchor']} | — | — | — | — | — | — | — | — | **失敗** |")
            continue
        af = (m.get("anchor_fidelity") or {}).get("mean_abs_diff", "—")
        L.append(f"| {r['id']} | {r['anchor']} | {121 - r['anchor']} 格 | {meta.get('minutes')} "
                 f"| {meta.get('vram_peak_mb')} MB | {af} | {m['motion']['mean']} "
                 f"| {m['flow']['jitter']} | {m['luma_drift']['drift']:+} "
                 f"| {m['sharpness']['mean']} | **{s}** |")
        detail.append((r["id"], s, d))
    L.append("")
    L.append("### 逐項明細")
    for rid, s, d in detail:
        L.append(f"\n**{rid}（{s}/90）**\n")
        L.append("| 面向 | 得分 | 實測值 |")
        L.append("|---|---|---|")
        for k, (v, note) in d.items():
            L.append(f"| {k} | {v:.1f} | {note} |")
    return "\n".join(L) + "\n"


def sec_prompt():
    if not PROMPT.exists():
        return "（prompt A/B 實驗尚未產出 results.json）\n"
    rows = json.loads(PROMPT.read_text(encoding="utf-8"))
    L = ["| 組 | prompt 字元 | 分鐘 | 接縫保真 | 動作 | 抖動 | 色彩漂移⚠ | 前景穩定⚠ | 銳利 | **總分/90** |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        s, _ = score_one(r)
        m, meta = r.get("metrics"), (r.get("meta") or {})
        if not m:
            L.append(f"| {r['id']} | {r['chars']} | — | — | — | — | — | — | — | **失敗** |")
            continue
        af = (m.get("anchor_fidelity") or {}).get("mean_abs_diff", "—")
        L.append(f"| {r['id']} | {r['chars']} | {meta.get('minutes')} | {af} "
                 f"| {m['motion']['mean']} | {m['flow']['jitter']} | {m['hist_drift']['max']} "
                 f"| {m['subject_area']['cv']} | {m['sharpness']['mean']} | **{s}** |")
    return "\n".join(L) + "\n"


def sec_hidden():
    if not HIDDEN.exists():
        return "（藏切實驗尚未產出 results.json）\n"
    rows = json.loads(HIDDEN.read_text(encoding="utf-8"))
    by = {}
    for r in rows:
        by.setdefault(r.get("method"), {})[r.get("scenario")] = r
    L = ["| 方法 | 甲 prominence | 甲 ratio | 乙 prominence | 乙 ratio | 判定 | 適用情境 |",
         "|---|---|---|---|---|---|---|"]
    def key(m):
        a = by[m].get("甲", {}).get("cut_prominence") or 9
        b = by[m].get("乙", {}).get("cut_prominence") or 9
        return (a + b)
    for me in sorted(by, key=key):
        a, b = by[me].get("甲", {}), by[me].get("乙", {})
        pa, pb = a.get("cut_prominence"), b.get("cut_prominence")
        ok = sum(1 for p in (pa, pb) if p is not None and p < 0.5)
        v = {2: "✅✅ 兩情境全過", 1: "✅ 只有同場景過", 0: "❌ 兩情境都藏不住"}[ok]
        L.append(f"| {me} | {pa} | {a.get('cut_ratio')} | {pb} | {b.get('cut_ratio')} "
                 f"| {v} | {a.get('note', '')} |")
    return "\n".join(L) + "\n"


def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    doc = f"""# EXPERIMENT_REPORT — 第一輪實驗結果

> 產生：{ts}（由 `experiments\\report.py` 自動生成，改資料不改這份，重跑就更新）
> 環境：RTX 5050 Laptop 8 GB (8151 MiB) ／ RAM 16 GB ／ Wan 2.2 5B Turbo GGUF Q4_K_M
> 固定參數：steps 8 ／ shift 8.0 ／ length 121 ／ euler + simple ／ cfg 1.0 ／ 704x1280 → 1080x1920

## 評分怎麼算的

滿分 100 拆成六塊，**自動化天花板是 90** —— 最後 10 分是「第三條腿／增生第二隻狗／
黑點眉在不在」，程式量不出來，只能跑 `auto\\frame_gate.py` 逐幀人眼審才拿得到。

這不是偷懶，是刻意的：8/20 那次事故的根因就是「數字類有東西擋所以從不出錯，
視覺類沒東西擋所以每輪都在打地鼠」。如果自動打得出 100 分，下一個人就會拿它當通行證。

| 面向 | 分 | 性質 |
|---|---|---|
| 接縫品質 | 25 | 客觀量測 |
| 動作品質 | 20 | 客觀量測 |
| 連續性 | 20 | 客觀 ＋ ⚠️代理 |
| 畫質 | 15 | 客觀量測 |
| 成本 | 10 | 客觀量測 |
| 人眼項 | 10 | ⛔ 自動一律 0 |

門檻標註：`實測` ＝ 有量過的數字；`推` ＝ 我訂的、還沒有基線，看到就別當定論。

---

## 實驗一：多幀接龍 anchor 掃描

**單變數**：anchor ∈ {{1, 13, 17, 21, 25}}。其餘全部鎖死
（接龍來源 `d10s1.raw704.mp4`、prompt 1870 字元「抬起單邊前腳」、seed 990821）。

⚠️ 無法消除的耦合：length 鎖 121 的情況下 anchor 越大新畫面越少（120→96 格）。
所有段內指標都**跳過前 anchor 格**再量，只量新生出來的部分。

{sec_chain()}
---

## 實驗二：I2V prompt 最小化 A/B

**單變數**：prompt 文字。其餘全部鎖死（接龍來源同上、anchor 17、seed 990821）。
PA 組直接沿用實驗一的 A17（同一組設定），沒有重跑。

{sec_prompt()}
---

## 實驗三：藏切（零 GPU、零下載）

情境甲 ＝ 同場景殘餘接縫（`d10s1` ＋ `d10s1_s2` 從第 17 格起）
情境乙 ＝ 換場景硬切（`d10s1` 蛋液房 ＋ `d12s1` 藍漆房）
指標 `cut_prominence` ＝ 接縫幀差 ÷ 轉場視窗最大幀差，< 0.5 ＝ 刀口被蓋住。

{sec_hidden()}
詳細說明與選用決策表見 [HIDDEN_CUT_PLAYBOOK.md](HIDDEN_CUT_PLAYBOOK.md)。

---

## 目視觀察

自動指標看不到「第三條腿／腳掌顏色／鏡頭有沒有自己推進」這類東西。
6 幀目視的觀察、以及**這輪哪兩個自動指標失效了**，寫在
[VISUAL_NOTES.md](VISUAL_NOTES.md)。

## 已發布多段片的基線（訂門檻用）

`baseline_published.json`（d9s1 / d11s1 / d12s1 / d10s1-cut / d12s1-cut 實測）。
⚠️ 那幾個數字是**全片頭尾**量的，混進了鏡頭切換，不能直接跟本輪的「段內漂移」比。

## 還沒做的（下一輪）

1. 對每一組跑 `auto\\frame_gate.py --init` 拿那 10 分 —— 現在全部是 0 分
2. 單張場景圖起頭的 prompt A/B（這輪只跑了接龍起頭）
3. 3 段接龍串成 14.9 秒的端到端試作
4. `grade.py` 段間統一調色的效果驗證
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(f"[ok] → {OUT}")


if __name__ == "__main__":
    main()
