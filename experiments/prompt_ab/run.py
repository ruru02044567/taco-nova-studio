# -*- coding: utf-8 -*-
r"""I2V prompt 最小化 A/B（2026-08-21）—— 那 1100 字的外觀描述到底有沒有在做事？

## 背景

現行 videoPrompt 一支 1870 字元，其中約 60% 是**重複描述角色外觀**
（純白吉娃娃、兩顆對稱黑點、藍項圈銀吊牌、不准換品種、不准第二隻狗…）。
這些字是一路被崩壞事故逼出來的：D4 的幻覺幼犬、D9 的博美、D11 的雙狗。
但那些事故**全部發生在「單張場景圖起頭」的時代** ——
起始圖只有一瞬間的樣子，模型只能靠文字想像角色長怎樣。

8/21 已經證明多幀接龍會把身分鎖住（B2：身體、頭、耳朵、項圈全部正常）。
如果身分是被那 17 格畫面鎖住的，那 1100 字的文字身分鎖就是在花 token 買心安。
**但也可能不是。** umt5 對長 prompt 的注意力分佈沒人量過，砍掉可能立刻長出第二隻狗。
不預設答案，跑出來看。

## 三組（唯一變數＝prompt 文字）

| 組 | prompt | 字元 | 內容 |
|---|---|---|---|
| A  | `prompt_A_full.txt` | 1870 | 現行完整版（＝多幀接龍實驗的 A17 那一組，**直接複用不重跑**） |
| B  | `prompt_B_min.txt` | 706 | 只留鏡頭＋動作＋環境不動＋風格。外觀與身分鎖全砍 |
| B2 | `prompt_B2_min_plus_count.txt` | 943 | B ＋「只有一隻狗、四條腿、有關節」的數量／解剖鎖 |

**為什麼要有 B2**：B 一次砍掉兩種東西（外觀描述＋數量解剖鎖）。
只跑 A/B 的話，萬一 B 長出第二隻狗，分不清是「少了外觀描述」還是「少了數量鎖」害的。
B2 把這兩件事拆開 —— 多燒 6.3 分鐘，換一個能歸因的結論，划算。

## 其餘條件鎖死

接龍來源 `d10s1.raw704.mp4`、anchor 17、seed 990821、steps 8 / shift 8.0 /
length 121 / euler+simple、704x1280。與 `multi_frame_chain` 的 A17 完全同一組設定，
所以 A 組可以直接沿用它的輸出，不必重燒算力。

## 為什麼跑在「接龍」而不是「單張場景圖」上

因為要回答的是**新架構**（多鏡接龍）該怎麼寫 prompt。
單張圖起頭那條路的答案 8/21 已經有了（沒有身分錨 → 身體拉伸）。
單張圖版本的 A/B 列在下一輪，不是這輪。

## 用法

    python experiments\prompt_ab\run.py              # 跑 B 與 B2（A 沿用 A17）
    python experiments\prompt_ab\run.py --measure-only
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "_lib"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import measure  # noqa: E402
import runner  # noqa: E402

PROJECT = HERE.parents[1]
OUT = HERE / "out"
OUT.mkdir(parents=True, exist_ok=True)

PREV = PROJECT / "auto" / "clips" / "d10s1.raw704.mp4"
ANCHOR = 17
SEED = 990821
FIXED = dict(seed=SEED, steps=8, shift=8.0, length=121, sampler="euler")

# A 組＝多幀接龍實驗的 A17。同來源、同 anchor、同 seed、同參數，唯一差別是 prompt。
A_FROM_CHAIN = PROJECT / "experiments" / "multi_frame_chain" / "out" / "A17_anchor17.mp4"

RUNS = [
    ("PA",  HERE / "prompt_A_full.txt",            "現行完整 prompt（外觀＋身分鎖全開）"),
    ("PB",  HERE / "prompt_B_min.txt",             "最小 prompt：鏡頭＋動作＋環境＋風格"),
    ("PB2", HERE / "prompt_B2_min_plus_count.txt", "最小 prompt ＋ 數量／解剖鎖"),
]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    measure_only = "--measure-only" in sys.argv
    force = "--force" in sys.argv
    todo = [r for r in RUNS if not args or r[0] in args]

    results = []
    for rid, pf, desc in todo:
        out_mp4 = OUT / f"{rid}.mp4"
        chars = len(pf.read_text(encoding="utf-8").strip())
        print(f"── {rid}｜{chars} 字元｜{desc}")

        if rid == "PA" and not out_mp4.exists():
            # 沿用接龍實驗的 A17，不重燒 6.3 分鐘。連 .raw704 一起搬，接縫指標才算得出來。
            if A_FROM_CHAIN.exists():
                shutil.copy2(A_FROM_CHAIN, out_mp4)
                raw = A_FROM_CHAIN.with_name(A_FROM_CHAIN.stem + ".raw704.mp4")
                if raw.exists():
                    shutil.copy2(raw, out_mp4.with_name(out_mp4.stem + ".raw704.mp4"))
                mj = A_FROM_CHAIN.with_suffix(".json")
                if mj.exists():
                    m = json.loads(mj.read_text(encoding="utf-8"))
                    m["note"] = "沿用 multi_frame_chain/A17（同設定，未重跑）"
                    out_mp4.with_suffix(".json").write_text(
                        json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
                print("   ↳ 沿用 multi_frame_chain 的 A17，未重跑")
            else:
                print("   ! 還沒有 A17，請先跑 multi_frame_chain/run.py A17")
                continue

        if measure_only:
            mp = out_mp4.with_suffix(".json")
            meta = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {"ok": out_mp4.exists()}
        elif rid == "PA":
            meta = json.loads(out_mp4.with_suffix(".json").read_text(encoding="utf-8"))
        else:
            meta = runner.gen(out_mp4, pf, prev=PREV, anchor=ANCHOR, force=force, **FIXED)

        if not meta.get("ok") or not out_mp4.exists():
            results.append({"id": rid, "chars": chars, "desc": desc,
                            "meta": meta, "metrics": None})
            continue

        m = measure.full_report(out_mp4, skip_frames=ANCHOR)
        measure.contact_sheet(out_mp4, OUT / f"{rid}_sheet.png", n=6,
                              label=f"{rid} {chars}字元 {desc}")
        results.append({"id": rid, "chars": chars, "desc": desc,
                        "meta": {k: meta.get(k) for k in ("minutes", "vram_peak_mb", "ok")},
                        "metrics": m})
        print(f"   動作 {m['motion']['mean']}　光流 {m['flow']['flow_mean']}"
              f"　直方圖漂移 {m['hist_drift']['max']}　前景面積 CV {m['subject_area']['cv']}")

    (OUT / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[ok] {len(results)} 組 → {OUT / 'results.json'}")
    print("⚠️ 「有沒有長出第二隻狗／第三條腿」自動指標判不了，"
          "看 *_sheet.png，必要時跑 auto\\frame_gate.py 逐幀審。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
