# -*- coding: utf-8 -*-
r"""
finish_video.py — 成片組裝（2026-08-18 建立）

把「無聲原片 → 有聲成片」這段從純手工變一鍵。此前每支片要人工做
剪輯（迴力鏢）＋配音效＋改檔名，D8/D14 各花了約 20 分鐘手工。

流程：
  原片（state 的 video 或 --src）
    → [--boomerang] 正播＋反播迴力鏢（在英文暫存路徑做，避 ffmpeg 中文路徑坑）
    → 音效：優先用 sfx\mix_{key}.py 專屬配方（每支片一檔是定案作法，D6 教訓：
      共用配方會被聽出「聲音怪怪的」）；沒有專屬檔時須明示 --recipe 用通用配方
    → auto\clips\{key}-final.mp4
    → preflight.py 硬檢查
    → 通過且非 --dry-run：state[key]["video"] 改指成片（原值備份到 video_raw），
      並複製到 待審核\{key}-有聲.mp4 給賢賢過目

用法：
  python auto\finish_video.py d8s1 --src auto\clips\d8s1-v02-boomerang.mp4 --dry-run
  python auto\finish_video.py d15s1 --boomerang
  python auto\finish_video.py d16s1 --recipe portal   # 無專屬配方時的明示選擇
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTO = Path(__file__).resolve().parent
PROJECT = AUTO.parent
CLIPS = AUTO / "clips"
SFX = PROJECT / "sfx"
REVIEW = PROJECT / "待審核"
STATE = AUTO / "state.json"


def sh(cmd, timeout=900):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                       timeout=timeout, env=env, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def boomerang(src: Path, dst: Path):
    """正播＋反播（影像軌；原片本來就無聲）。在英文暫存路徑做。"""
    with tempfile.TemporaryDirectory(prefix="boom_") as td:
        tin, tout = Path(td) / "in.mp4", Path(td) / "out.mp4"
        shutil.copy2(src, tin)
        rc, out = sh(["ffmpeg", "-y", "-v", "error", "-i", tin,
                      "-filter_complex",
                      "[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0[v]",
                      "-map", "[v]", "-an", tout])
        if rc != 0 or not tout.exists():
            print("[X] 迴力鏢剪輯失敗：", out[-400:])
            sys.exit(1)
        shutil.copy2(tout, dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key", help="影片 key，如 d8s1")
    ap.add_argument("--src", default=None, help="原片路徑（預設取 state 的 video）")
    ap.add_argument("--boomerang", action="store_true", help="先做正播＋反播")
    ap.add_argument("--recipe", default=None,
                    help="通用配方名（僅在沒有 sfx\\mix_{key}.py 時允許）")
    ap.add_argument("--dry-run", action="store_true",
                    help="輸出 -final-test.mp4，不動 state、不進待審核")
    args = ap.parse_args()
    key = args.key

    state = json.loads(STATE.read_text(encoding="utf-8"))
    raw_src = args.src or (state.get(key) or {}).get("video", "")
    # 空字串會變成 Path(".")，exists() 誤回 True，所以先擋空值再用 is_file
    if not raw_src or not Path(raw_src).is_file():
        print(f"[X] 找不到原片：{raw_src!r}（用 --src 明示）")
        sys.exit(1)
    src = Path(raw_src)

    suffix = "-final-test.mp4" if args.dry_run else "-final.mp4"
    final = CLIPS / f"{key}{suffix}"

    # 1) 剪輯
    work = src
    if args.boomerang:
        work = CLIPS / f"{key}-boomerang.mp4"
        boomerang(src, work)
        print(f"[ok] 迴力鏢：{work.name}")

    # 2) 音效：專屬配方優先（定案作法）
    per_video = SFX / f"mix_{key}.py"
    if per_video.exists():
        if args.recipe:
            print(f"[!] 已有專屬配方 {per_video.name}，忽略 --recipe {args.recipe}")
        rc, out = sh([sys.executable, per_video, work, final], timeout=900)
    elif args.recipe:
        rc, out = sh([sys.executable, SFX / "mix.py", work, final, args.recipe], timeout=900)
        print(f"[!] 用通用配方 {args.recipe} —— 記得對齊畫面事件，必要時寫 sfx\\mix_{key}.py")
    else:
        print(f"[X] 這支還沒有音效配方。定案作法是每支片一檔：先寫 sfx\\mix_{key}.py")
        print(f"    （臨時要用通用配方請明示 --recipe，可選：blackhole/flour/flour_shake/"
              f"lava/soil_shake/soil_still/portal/portal_boomerang）")
        sys.exit(1)
    if rc != 0 or not final.exists():
        print("[X] 音效混音失敗：", out[-600:])
        sys.exit(1)
    print(f"[ok] 音效完成：{final.name}")

    # 3) preflight 硬檢查
    rc, out = sh([sys.executable, AUTO / "preflight.py", final, "--key", key], timeout=600)
    print(out.strip())
    if rc != 0:
        print("[X] preflight 未過，成片保留但不進待審核、不動 state")
        sys.exit(2)

    # 4) 收尾
    if args.dry_run:
        print(f"[ok] dry-run 完成：{final}（未動 state）")
        return
    st = state.get(key) or {}
    if st.get("video") and st["video"] != str(final):
        st["video_raw"] = st["video"]
    st["video"] = str(final)
    state[key] = st
    # 原子性寫入：先寫暫存檔再 os.replace，crash 也不會留下半個 state.json
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STATE)
    dst = REVIEW / f"{key}-有聲.mp4"
    shutil.copy2(final, dst)
    print(f"[ok] state.video 已指向成片（原值在 video_raw）；已送待審：{dst}")
    print(f"     賢賢過目後跑： python auto\\pipeline.py ok {key}")


if __name__ == "__main__":
    main()
