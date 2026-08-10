# -*- coding: utf-8 -*-
"""把幾支影片的音訊畫成波形圖疊在一起比較密度"""
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼")
TMP = Path(r"C:\Users\TUFGAM~1\AppData\Local\Temp\claude\C--Users-TUF-Gaming\2a58efa0-384a-45d4-b03d-36802970a640\scratchpad")

ROWS = [
    ("v2 壓縮版（尖峰被壓平）", BASE / "待審核/d1s1-有聲v2.mp4", "#7aa2c8"),
    ("v3 動態版（保留尖峰）", BASE / "待審核/d1s1-有聲v3.mp4", "#f7c948"),
    ("對標 Tim and Jeffy", TMP / "ref.mp4", "#7ec87e"),
]

W, H, BAR, PAD = 1100, 150, 44, 10
canvas = Image.new("RGB", (W + PAD * 2, (H + BAR) * len(ROWS) + PAD * 2), "#11161d")
d = ImageDraw.Draw(canvas)
font = ImageFont.truetype(r"C:\Windows\Fonts\msjh.ttc", 26)

for i, (label, src, color) in enumerate(ROWS):
    png = TMP / f"wave{i}.png"
    subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-i", str(src),
                    "-filter_complex", f"showwavespic=s={W}x{H}:colors={color}",
                    "-frames:v", "1", str(png)], check=False)
    if not png.exists():
        print("失敗:", src)
        continue
    y = PAD + i * (H + BAR)
    d.text((PAD + 2, y + 6), label, font=font, fill="#f7c948" if i == 1 else "#c9d6e4")
    canvas.paste(Image.open(png).convert("RGB"), (PAD, y + BAR))

out = BASE / "channel-art/preview/音效波形比較.png"
canvas.save(out)
print(out, canvas.size)
