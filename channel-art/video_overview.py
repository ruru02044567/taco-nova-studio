# -*- coding: utf-8 -*-
"""把專案裡所有成品影片各抽一幀，拼成一張總覽圖，方便在對話框裡一眼看完"""
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

P = Path(r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼")
TMP = Path(__file__).parent / "preview" / "_frames"
TMP.mkdir(parents=True, exist_ok=True)
OUT = Path(__file__).parent / "preview" / "成品總覽.jpg"

# (檔案, 標籤)　順序＝新到舊
VIDEOS = [
    (P / "auto/clips/d1s2.mp4",            "D1S2 小床  本機 → 已發布"),
    (P / "auto/clips/d1s1.mp4",            "D1S1 水碗  本機 → 已發布"),
    (P / "D1S1-驗收-大狗睡小床.mp4",         "D1S1 驗收版"),
    (P / "ab-test/A-原版prompt.mp4",        "AB 測試 A 原版 prompt"),
    (P / "ab-test/B-電影感prompt.mp4",      "AB 測試 B 電影感 prompt"),
    (P / "hand-test/hand-test-10s.mp4",     "手部測試"),
    (P / "taco-bed-10s-veo.mp4",            "搶狗床  Veo"),
    (P / "taco-bed-10s-local.mp4",          "搶狗床  本機"),
    (P / "taco-troll-10s-veo-v2.mp4",       "遙控器 v2  Veo（已發布）"),
    (P / "taco-troll-10s-veo.mp4",          "遙控器 v1  Veo"),
    (P / "taco-troll-10s-local.mp4",        "遙控器  本機"),
    (P / "taco-plant-draft.mp4",            "打翻盆栽  草稿"),
]

CW, CH = 300, 534          # 每格畫面（9:16）
PAD, BAR = 14, 34          # 間距、標題列高
COLS = 6

font = ImageFont.truetype(r"C:\Windows\Fonts\msjh.ttc", 17)


def grab(v, out):
    """抽影片中間附近的一幀"""
    subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-ss", "3", "-i", str(v),
                    "-frames:v", "1", "-vf", f"scale={CW}:{CH}:force_original_aspect_ratio=increase,crop={CW}:{CH}",
                    str(out)], timeout=90, check=False)
    return out.exists()


cells = []
for v, label in VIDEOS:
    if not v.exists():
        continue
    f = TMP / (v.stem + ".jpg")
    if grab(v, f):
        cells.append((f, label))

rows = (len(cells) + COLS - 1) // COLS
W = COLS * CW + (COLS + 1) * PAD
H = rows * (CH + BAR) + (rows + 1) * PAD
sheet = Image.new("RGB", (W, H), "#11161d")
d = ImageDraw.Draw(sheet)

for i, (f, label) in enumerate(cells):
    r, c = divmod(i, COLS)
    x = PAD + c * (CW + PAD)
    y = PAD + r * (CH + BAR + PAD)
    sheet.paste(Image.open(f), (x, y))
    color = "#f7c948" if "已發布" in label else "#c9d6e4"
    d.text((x + 2, y + CH + 8), label, font=font, fill=color)

sheet.save(OUT, quality=90)
print(OUT, sheet.size, f"{len(cells)} 支")
