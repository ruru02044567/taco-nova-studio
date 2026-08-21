# -*- coding: utf-8 -*-
r"""多幀接龍 anchor 掃描（2026-08-21）—— 餵幾格才夠？

## 這輪要回答的唯一問題

8/20 加了 `--anchor`，8/21 凌晨驗了「接龍 vs 單張圖」，證明**接龍擋得住
身體拉伸與增生肢體**。但 anchor 預設 17 是當初隨手挑的（0.7 秒，看起來合理），
**從來沒有人比較過 13/17/21/25**。這輪就掃這一個變數。

## 單變數鎖死

| 固定 | 值 |
|---|---|
| 接龍來源 | `auto\clips\d10s1.raw704.mp4`（121 格原生 704x1280，不是放大成品） |
| prompt | `prompt.txt`（＝8/21 那輪的「抬起單邊前腳」，已證實有分辨力） |
| seed | 990821 |
| steps / shift / length / sampler | 8 / 8.0 / 121 / euler+simple（現行最佳實測設定，不動） |
| 解析度 | 704x1280 原生 → 1080x1920 |

**唯一變數：anchor ∈ {1, 13, 17, 21, 25}**（Wan 的潛在空間時間軸 4 倍壓縮，只能取 4n+1）

## 一個無法消除的耦合，先講清楚

length 鎖死 121 的情況下，anchor 變大 → **新內容變少**（121−anchor ＝ 120/108/104/100/96 格）。
這是接龍在數學上的必然，不是設計疏失：要嘛新內容等長（那 length 就得跟著變，
變成兩個變數），要嘛總長等長（那新內容就得變）。
賢賢的規格書指定「同一影片長度」，所以選後者，並且**所有段內指標一律跳過前 anchor 格再量**
—— 只量新生出來的部分，不讓「被鎖死的那幾格」把數字洗漂亮。

## 免費的重現性檢查

anchor=17 這組跟 8/21 01:17 那支 `B2_抬前腳_接龍.mp4` 是同來源、同 prompt、同 seed。
兩者量出來若不一致，底下所有排名都不能信 —— 這是 8/14 那輪 `E00_base` 的同款設計。

## 用法

    python experiments\multi_frame_chain\run.py            # 全跑（已存在的跳過）
    python experiments\multi_frame_chain\run.py A13 A17    # 只跑指定組
    python experiments\multi_frame_chain\run.py --measure-only   # 不生片，只重算指標
"""
import json
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
PROMPT = HERE / "prompt.txt"
SEED = 990821
FIXED = dict(seed=SEED, steps=8, shift=8.0, length=121, sampler="euler")

# (id, anchor, 說明)
RUNS = [
    ("A01", 1,  "只餵最後 1 格（＝傳統單張圖接龍，走同一條 LoadVideo 路徑）"),
    ("A13", 13, "最後 13 格 = 0.54 秒"),
    ("A17", 17, "最後 17 格 = 0.71 秒（現行預設；同時是重現性檢查）"),
    ("A21", 21, "最後 21 格 = 0.88 秒"),
    ("A25", 25, "最後 25 格 = 1.04 秒"),
]

# 為什麼 A01 也走 LoadVideo 而不是 LoadImage：
# 只有這樣「圖形結構」才在五組之間完全一致，唯一差別才真的只有格數。
# 走 LoadImage 的那個對照（PNG → LoadImage 節點）8/21 01:11 已經跑過（A2_抬前腳_單張圖.mp4），
# 結論是身體嚴重拉伸 —— 不重跑，省 6.3 分鐘算力。


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    measure_only = "--measure-only" in sys.argv
    force = "--force" in sys.argv
    todo = [r for r in RUNS if not args or r[0] in args]

    if not PREV.exists():
        print(f"[X] 接龍來源不存在：{PREV}")
        return 1
    if not PROMPT.exists():
        print(f"[X] prompt 不存在：{PROMPT}")
        return 1
    info = measure.probe(PREV)
    print(f"接龍來源：{PREV.name}　{info['width']}x{info['height']}　{info['frames']} 格")
    print(f"prompt：{len(PROMPT.read_text(encoding='utf-8').strip())} 字元　seed {SEED}")
    print(f"固定參數：{FIXED}\n")

    results = []
    for rid, anchor, desc in todo:
        out_mp4 = OUT / f"{rid}_anchor{anchor:02d}.mp4"
        print(f"── {rid}｜anchor {anchor}｜{desc}")
        if measure_only:
            meta_p = out_mp4.with_suffix(".json")
            if not meta_p.exists():
                print("   （沒有生成紀錄，跳過）")
                continue
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
        else:
            meta = runner.gen(out_mp4, PROMPT, prev=PREV, anchor=anchor, force=force, **FIXED)
        if not meta.get("ok"):
            results.append({"id": rid, "anchor": anchor, "desc": desc, "meta": meta,
                            "metrics": None})
            continue

        # 量測一律跳過前 anchor 格 —— 那幾格是被 mask 鎖死的前段還原版，
        # 不是這一輪生出來的東西，算進去等於幫大 anchor 作弊。
        raw = out_mp4.with_name(out_mp4.stem + ".raw704.mp4")
        m = measure.full_report(out_mp4, skip_frames=anchor)
        # 接縫保真度要用原生 704 檔比（成品經過 lanczos 放大＋裁切，比出來是縮放誤差不是接縫誤差）
        fed = OUT / f"_fed_{rid}.mp4"
        _cut_tail(PREV, anchor, fed)
        if raw.exists():
            m["anchor_fidelity"] = measure.anchor_fidelity(fed, raw, anchor)
        measure.contact_sheet(out_mp4, OUT / f"{rid}_sheet.png", n=6,
                              label=f"{rid} anchor={anchor} {desc}")
        results.append({"id": rid, "anchor": anchor, "desc": desc,
                        "meta": {k: meta[k] for k in ("minutes", "vram_peak_mb", "ok")},
                        "metrics": m})
        print(f"   量測完成：動作 {m['motion']['mean']}　光流 {m['flow']['flow_mean']}"
              f"　抖動 {m['flow']['jitter']}　亮度漂移 {m['luma_drift']['drift']}")

    (OUT / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[ok] {len(results)} 組 → {OUT / 'results.json'}")
    return 0


def _cut_tail(video, n, dst):
    """切出 video 的最後 n 格（跟 make_video_local_5s.py 同一套參數，才比得準）。"""
    import subprocess
    total = measure.probe(video)["frames"]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf",
                    f"trim=start_frame={total - n},setpts=N/24/TB,"
                    f"scale=704:1280:force_original_aspect_ratio=increase,crop=704:1280",
                    "-an", "-r", "24", "-c:v", "libx264", "-crf", "0",
                    "-pix_fmt", "yuv420p", str(dst)], check=True)


if __name__ == "__main__":
    sys.exit(main())
