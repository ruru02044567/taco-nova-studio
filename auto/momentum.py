# -*- coding: utf-8 -*-
"""量一支片的「動量曲線」：每 0.25 秒的畫面變化量，以及峰值／基線的比值。

為什麼這個數字重要 —— 用這支工具量的基準值（都是同一套演算法，可以互相比較）：

    d1s1（Veo 生，5.1 萬觀看）  峰值/基線 = 22.8 倍  鋪陳 → 爆發 → 餘韻 → 收乾淨
    d5s1（本機生＋慢速開頭）    峰值/基線 =  3.0 倍
    d4s1（本機生，被否決）      峰值/基線 =  2.5 倍  從頭忙到尾，沒有任何一處突出來

⚠️ 2026-08-11 的三方審片報告寫 d1s1 是「35 倍」，跟這裡的 22.8 不一樣。
不是誰算錯，是**基線的定義不同**：審片取的是曲線的最低點（0.8），
這支工具取的是 10 分位（1.23）—— 取最低點容易被單一格的雜訊放大。
**要互相比較的時候一律用這支工具的數字**，不要拿審片報告的 35 去跟工具跑出來的值比。

「看起來很忙，但什麼都沒發生」是 Shorts 最糟的組合 ——
觀眾感覺得到影片還在動，卻拿不到新資訊，於是在 5 到 6 秒之間滑走。

⚠️ 本機 Wan 2.2 **不吃 prompt 裡的時間節拍指令**（實測：寫「先靜止一拍再動」
會生出從第一格就均勻運動的片，曲線是平的 1.4 倍）。要做出對比只能在剪輯階段：
把開頭 0.7 秒用 `trim` ＋ `setpts=PTS*2.6` 放慢成 1.8 秒，1.4 倍就變 3.2 倍。

用法：
    python momentum.py <影片> [暫存資料夾]

輸出每 0.25 秒的動量長條圖，以及最後一行的統計摘要。
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

src = Path(sys.argv[1])
tmp = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(tempfile.mkdtemp(prefix="momentum_"))
tmp.mkdir(parents=True, exist_ok=True)
for f in tmp.glob("*.png"):
    f.unlink()

# 4fps 降採樣 ＋ 縮到 180 寬：只看構圖層級的變化，不被畫面雜訊干擾
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                "-vf", "fps=4,scale=180:-1", str(tmp / "f%04d.png")], check=True)

frames = sorted(tmp.glob("*.png"))
if len(frames) < 3:
    print("FAILED: 抽不到足夠的影格")
    sys.exit(1)

arrs = [np.asarray(Image.open(f).convert("L"), dtype=np.int16) for f in frames]
print(f"{len(arrs)} 格 @4fps = {len(arrs) / 4:.2f} 秒\n")
print(" 時間    動量")

diffs = []
for i in range(1, len(arrs)):
    d = float(np.abs(arrs[i] - arrs[i - 1]).mean())
    diffs.append(d)
    print(f"{i / 4:5.2f}s  {d:6.2f}  {'#' * int(d * 2)}")

d = np.array(diffs)
base = max(float(np.percentile(d, 10)), 0.01)
# 判讀跟顯示用同一個值。不這樣做的話 2.98 會印成「3.0 倍」卻被判進 <3 那一檔，
# 使用者看到的結論跟看到的數字自相矛盾。
ratio = round(float(d.max()) / base, 1)
print(f"\n平均 {d.mean():.2f}  峰值 {d.max():.2f} @ {(d.argmax() + 1) / 4:.2f}s  "
      f"基線(10分位) {base:.2f}  峰值/基線 {ratio} 倍")

if ratio >= 10:
    print("→ 有明確的爆點，戲劇曲線成立（爆款 d1s1 用同一套演算法量是 22.8 倍）")
elif ratio >= 3:
    print("→ 有對比但不夠強。可考慮把開頭再放慢，或把結尾收乾淨")
else:
    print("→ ⚠️ 曲線是平的：從頭忙到尾，觀眾拿不到「發生了什麼」的訊號")
