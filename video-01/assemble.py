"""把 clips/ 裡的 shot1.mp4...shotN.mp4 依序組裝成可上傳的 Shorts 成品（幾段都行）。

用法：python assemble.py
輸出：output/final.mp4（1080x1920、30fps、AAC）＋ output/thumbnail.jpg
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
CLIPS = HERE / "clips"
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

shots = sorted(
    CLIPS.glob("shot*.mp4"),
    key=lambda p: int(re.search(r"\d+", p.stem).group()),
)
if len(shots) < 2:
    sys.exit(f"clips/ 裡只找到 {len(shots)} 段（要 shot1.mp4、shot2.mp4...），放齊再跑")
print("串接順序：", ", ".join(s.name for s in shots))

norm = []
for i, s in enumerate(shots, 1):
    n = OUT / f"_n{i}.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", str(s),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
               "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
        str(n),
    ], check=True)
    norm.append(n)

concat_list = OUT / "_list.txt"
concat_list.write_text("".join(f"file '{n.name}'\n" for n in norm), encoding="utf-8")

final = OUT / "final.mp4"
subprocess.run([
    "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
    "-i", str(concat_list), "-c", "copy", str(final),
], check=True, cwd=OUT)

subprocess.run([
    "ffmpeg", "-y", "-v", "error", "-ss", "6", "-i", str(final),
    "-frames:v", "1", "-q:v", "2", str(OUT / "thumbnail.jpg"),
], check=True)

for n in norm + [concat_list]:
    n.unlink()

probe = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "default=noprint_wrappers=1:nokey=1", str(final)],
    capture_output=True, text=True, check=True)
print(f"完成：{final}（{float(probe.stdout):.1f} 秒）")
