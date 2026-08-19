# -*- coding: utf-8 -*-
r"""
gen_scene_flux.py — FLUX schnell 場景圖產線化（2026-08-18 建立）

背景：8/17 D14S1 的場景圖是手動逐次送 ComfyUI API 做的，流程沒有沉澱。
本腳本把那晚的做法變成可重跑的一支：讀 prompt → FLUX schnell 出圖 →
複製回 auto\clips\。

用法：
  python auto\gen_scene_flux.py --key d14s1
      （讀 auto\clips\d14s1_scene_flux.txt，輸出 auto\clips\d14s1_scene.png）
  python auto\gen_scene_flux.py --prompt-file X.txt --out Y.png [--seed 42]

鐵律（沿襲 comfy_api）：不啟不關 ComfyUI；禮讓佇列中的 Wan 工作；
切模型前先 free_memory。
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comfy_api  # noqa: E402

WORKFLOW = Path(r"C:\Users\TUF Gaming\ai-video-local\workflows\flux_schnell_api.json")
CLIPS = Path(__file__).resolve().parent / "clips"

# 抗 AI 感尾段（BENCHMARK 08-exp-realism 三臂同 seed 實測的 B 版，2026-08-19）。
# 原則：AI 感來自「零缺陷」，場景缺陷靠 prompt 要（模型畫得出「東西」）；
# 顆粒／失焦／歪斜這類「相機行為」模型畫不出來，交給 postfx.py 後製，不要寫在這。
REALISM_TAIL = (
    "Amateur iPhone snapshot, harsh direct phone flash, slightly overexposed highlights, "
    "everyday clutter in the background, scuffed floor, a few crumbs and a stray sock on the floor, "
    "nothing staged, nothing tidied up."
)
REALISM_MARKER = "nothing staged"  # prompt 裡已有這句就不重複接


def apply_realism(prompt: str) -> tuple[str, list]:
    """回傳 (處理後 prompt, 動了什麼的說明清單)。"""
    notes = []
    low = prompt.lower()
    # 「Photorealistic photo」會把模型推向完美攝影作品，是 AI 感的幫兇 → 換掉
    for bad in ("photorealistic photo of", "photorealistic photo,", "photorealistic photo"):
        if low.startswith(bad):
            prompt = "Amateur iPhone snapshot of" + prompt[len(bad):] if bad.endswith("of") \
                else "Amateur iPhone snapshot," + prompt[len(bad):]
            notes.append("開頭 Photorealistic photo → Amateur iPhone snapshot")
            break
    if REALISM_MARKER not in prompt.lower():
        tail = REALISM_TAIL
        if "amateur iphone snapshot" in prompt.lower():
            tail = tail.replace("Amateur iPhone snapshot, ", "", 1).capitalize()
        prompt = prompt.rstrip().rstrip(".") + ". " + tail
        notes.append("已接抗 AI 感尾段（B 版）")
    else:
        notes.append("prompt 已含缺陷句，不重複接")
    return prompt, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", help="影片 key（如 d14s1），自動找 clips\\{key}_scene_flux.txt")
    ap.add_argument("--prompt-file", help="prompt 檔路徑（與 --key 二選一）")
    ap.add_argument("--out", help="輸出 png 路徑（預設 clips\\{key}_scene.png）")
    ap.add_argument("--width", type=int, default=832)
    ap.add_argument("--height", type=int, default=1216)
    ap.add_argument("--seed", type=int, default=None, help="不給就用時間戳")
    ap.add_argument("--steps", type=int, default=4, help="schnell 建議 4")
    ap.add_argument("--no-realism", action="store_true",
                    help="不接抗 AI 感尾段（做對照實驗時用）")
    args = ap.parse_args()

    if args.key:
        pf = CLIPS / f"{args.key}_scene_flux.txt"
        out = Path(args.out) if args.out else CLIPS / f"{args.key}_scene.png"
    elif args.prompt_file:
        pf = Path(args.prompt_file)
        out = Path(args.out) if args.out else pf.with_suffix(".png")
    else:
        ap.error("要嘛給 --key，要嘛給 --prompt-file")

    if not pf.exists():
        print(f"[X] 找不到 prompt 檔：{pf}")
        sys.exit(1)
    prompt = pf.read_text(encoding="utf-8").strip()
    if len(prompt) < 20:
        print(f"[X] prompt 太短（{len(prompt)} 字元），像是空檔")
        sys.exit(1)
    if not args.no_realism:
        prompt, notes = apply_realism(prompt)
        for n in notes:
            print(f"[realism] {n}")

    if not WORKFLOW.is_file():
        print(f"[X] 找不到 FLUX workflow：{WORKFLOW}")
        sys.exit(1)
    wf = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    wf["4"]["inputs"]["text"] = prompt
    wf["6"]["inputs"]["width"] = args.width
    wf["6"]["inputs"]["height"] = args.height
    wf["7"]["inputs"]["seed"] = args.seed if args.seed is not None else int(time.time()) % 2**31
    wf["7"]["inputs"]["steps"] = args.steps
    wf["9"]["inputs"]["filename_prefix"] = f"flux/scene_{args.key or pf.stem}"

    comfy_api.require_server()
    comfy_api.wait_for_free_queue()          # 禮讓 Wan
    comfy_api.free_memory()                  # 換模型前清 VRAM
    pid = comfy_api.submit(wf)
    print(f"[…] 已送單 {pid}，FLUX schnell {args.width}x{args.height} steps={args.steps}")
    t0 = time.time()
    hist = comfy_api.wait(pid, timeout=900)
    if hist is None:
        print("[X] 生成失敗")
        sys.exit(2)
    imgs = comfy_api.collect_images(hist, tag="flux_scene")
    if not imgs:
        print("[X] 沒有收到輸出圖")
        sys.exit(2)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(imgs[0], out)
    print(f"[ok] {time.time()-t0:.0f}s → {out}")


if __name__ == "__main__":
    main()
