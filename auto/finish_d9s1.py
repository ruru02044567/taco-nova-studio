# -*- coding: utf-8 -*-
"""紅酒片收尾：拉到 Shorts 規格 → 依劇本節拍配 Sonniss 音效 → 正規化 → 進待審核。

為什麼要自己配音效：Veo 號稱有原生音效，但 8/09 實測整軌只有 -47dB，
等於無聲。平台會壓抑安靜的影片，所以一律自己補。

音效對照劇本節拍（10 秒版）：
  0.0-2.0  開場災難現場  → roomtone 打底
  2.0-6.0  瘋狂抓地毯    → nails_on_velvet ×2（刷刷聲，抓絨毛地毯最像）
  6.0-8.0  退開看災情    → 布料拖曳一下
  8.0-10.0 裝無辜＋哈士奇嘆氣 → 小狗嗚咽

用法：python finish_d9s1.py <raw.mp4>
"""
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
SFX = HERE.parent / "sfx" / "lib"
REVIEW = HERE.parent / "待審核"
REVIEW.mkdir(parents=True, exist_ok=True)

raw = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "clips" / "d9s1_raw.mp4")
final = REVIEW / "d9s1-紅酒-有聲.mp4"


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def probe(path, entries):
    return subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries,
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()


dur = float(probe(raw, "format=duration"))
wh = probe(raw, "stream=width,height").split()
print(f"原始：{wh[0]}x{wh[1]}，{dur:.1f} 秒")

# 拉到 1080x1920。Veo 出的是 720x1280，等比放大不裁切
silent = HERE / "clips" / "_d9s1_v.mp4"
ff("-i", str(raw), "-vf", "scale=1080:1920:flags=lanczos",
   "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
   "-an", str(silent))

room = SFX / "roomtone" / "Roomtone,Hvac,Drone,Hum,Low Mids,Loop.mp3"
scrub = SFX / "claw-scratch" / "nails_on_velvet_single_002.mp3"
cloth = SFX / "fabric-fine" / "Blanket-Lift_06.mp3"
whine = SFX / "dog-whimper" / "EFX INT Dog Wimper 06 A.M.wav"

inputs, filters, mix = ["-i", str(silent)], [], []
idx = 1

inputs += ["-i", str(room)]
filters.append(f"[{idx}:a]atrim=0:{dur + 0.3:.1f},lowpass=f=900,volume=0.3,"
               f"afade=t=in:st=0:d=0.4,afade=t=out:st={dur - 0.6:.1f}:d=0.6[amb]")
mix.append("[amb]")
idx += 1

# 抓地毯：2.0 秒和 3.8 秒各來一次，做出「瘋狂猛擦」的密集感
if scrub.exists():
    for at in (2000, 3800):
        inputs += ["-i", str(scrub)]
        filters.append(f"[{idx}:a]atrim=0:1.8,adelay={at}|{at},volume=1.0[sc{idx}]")
        mix.append(f"[sc{idx}]")
        idx += 1

# 退開：布料被拖動
if cloth.exists():
    inputs += ["-i", str(cloth)]
    filters.append(f"[{idx}:a]atrim=0:1.2,adelay=6200|6200,volume=0.6[cl]")
    mix.append("[cl]")
    idx += 1

# 結尾裝無辜的嗚咽
if whine.exists():
    at = int(max(dur - 1.8, 0) * 1000)
    inputs += ["-i", str(whine)]
    filters.append(f"[{idx}:a]atrim=0:1.6,adelay={at}|{at},volume=1.2[wh]")
    mix.append("[wh]")
    idx += 1

filters.append("".join(mix) + f"amix=inputs={len(mix)}:duration=first:dropout_transition=0,"
                              "loudnorm=I=-11:TP=-1.2:LRA=11[a]")
ff(*inputs, "-filter_complex", ";".join(filters),
   "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
   "-shortest", str(final))

out_dur = float(probe(final, "format=duration"))
vol = subprocess.run(["ffmpeg", "-i", str(final), "-af", "volumedetect", "-f", "null", "-"],
                     capture_output=True, text=True).stderr
mean = [l.split("mean_volume:")[1].strip() for l in vol.splitlines() if "mean_volume:" in l]
print(f"FINAL: {final}")
print(f"  {out_dur:.1f} 秒，音量 {mean[0] if mean else '?'}")
