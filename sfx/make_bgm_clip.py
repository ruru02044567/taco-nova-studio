# -*- coding: utf-8 -*-
r"""把 bgm原始\ 的整首曲子剪成一支片要用的 BGM 片段。

在此之前頻道只有兩首 BGM（apple-cider、happyclappy）在輪，而 PUBLISH_GATE 規則 12
禁止同一個音效檔連續兩支重複——2026-08-22 補了六首進 `sfx\bgm原始\`，這支負責剪。

用法：
    python sfx\make_bgm_clip.py cheer-up 12.3
    python sfx\make_bgm_clip.py playful-mood 12.3 --start 18 --name bgm_playful_d17

預設不淡出（PUBLISH_GATE：結尾要戛然而止，不准淡出），要淡出加 --fade-out。
音量不在這裡調——mix.py 的 RECIPE 用 dB 欄控制。
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SFX = Path(__file__).resolve().parent
SRC = SFX / "bgm原始"
DST = SFX / "lib" / "_prerendered"

ap = argparse.ArgumentParser()
ap.add_argument("track", help="bgm原始\\ 裡的檔名（不含 .mp3），例如 cheer-up")
ap.add_argument("seconds", type=float, help="要幾秒（通常等於成片長度）")
ap.add_argument("--start", type=float, default=0.0, help="從原曲第幾秒開始取")
ap.add_argument("--name", help="輸出檔名（不含副檔名），預設 bgm_<track>_<秒>s")
ap.add_argument("--fade-in", type=float, default=0.6)
ap.add_argument("--fade-out", type=float, default=0.0,
                help="預設 0＝不淡出（PUBLISH_GATE 要求結尾戛然而止）")
a = ap.parse_args()

src = SRC / f"{a.track}.mp3"
if not src.is_file():
    print(f"[X] 找不到 {src.name}。庫存：")
    for f in sorted(SRC.glob("*.mp3")):
        print("   ", f.stem)
    sys.exit(1)

out = DST / f"{a.name or f'bgm_{a.track.replace(chr(45), chr(95))}_{a.seconds:g}s'}.wav"

af = [f"afade=t=in:d={a.fade_in}"]
if a.fade_out > 0:
    af.append(f"afade=t=out:st={max(0, a.seconds - a.fade_out):.2f}:d={a.fade_out}")
af.append("aresample=48000")

# 中文路徑坑：先複製到英文暫存再給 ffmpeg
with tempfile.TemporaryDirectory(prefix="bgmclip_") as td:
    tin, tout = Path(td) / "in.mp3", Path(td) / "out.wav"
    tin.write_bytes(src.read_bytes())
    p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(a.start), "-t", str(a.seconds),
                        "-i", str(tin), "-af", ",".join(af), "-ac", "2", str(tout)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0 or not tout.exists():
        print("[X] ffmpeg 失敗：", (p.stderr or "")[-400:])
        sys.exit(1)
    out.write_bytes(tout.read_bytes())

dur = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                      "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
print(f"[ok] {out.name}　{dur}s")
print(f"     配方引用：(\"_prerendered/{out.name}\", 0.0, -5, \"\", False)")
