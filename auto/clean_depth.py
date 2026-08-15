# -*- coding: utf-8 -*-
"""把深度圖裡「地板／地毯」那一塊的假細節抹平，只留下角色的輪廓。

為什麼需要（2026-08-11 實測）：
DA3 會把攤平在地毯上的紅酒漬誤判成有高低起伏的物體，深度圖上留下一堆輪廓線。
ControlNet 忠實照做，於是無論強弱都生不出液體：
  strength 0.85 → 酒漬變成塗鴉般的深色線條
  strength 0.60 → 變成一團白色布狀物
  strength 0.45 → 酒漬整個消失
問題不在強度，在深度圖本身餵了錯的資訊。

做法：地板區域套大半徑中值濾波把細節磨掉，保留大結構（狗的剪影）。
上半部（狗的頭與身體）完全不動。

用法：python clean_depth.py <深度圖> <輸出檔名> [地板起始比例，預設 0.55]
"""
import sys

from PIL import Image, ImageFilter

import comfy_api as C

sys.stdout.reconfigure(encoding="utf-8")

src = sys.argv[1]
out_name = sys.argv[2]
floor_from = float(sys.argv[3]) if len(sys.argv) > 3 else 0.55

path = C.COMFY_INPUT + "\\" + src
img = Image.open(path).convert("L")
w, h = img.size
split = int(h * floor_from)

top = img.crop((0, 0, w, split))
floor = img.crop((0, split, w, h))

# 中值濾波磨掉紋理細節，再高斯柔化接縫。半徑要夠大才吃得掉酒漬的假輪廓。
floor = floor.filter(ImageFilter.MedianFilter(size=9)).filter(ImageFilter.GaussianBlur(radius=6))

out = Image.new("L", (w, h))
out.paste(top, (0, 0))
out.paste(floor, (0, split))
# 接縫處再柔化一次，避免留下一條水平硬邊被 ControlNet 當成邊緣
band = out.crop((0, max(0, split - 12), w, min(h, split + 12)))
out.paste(band.filter(ImageFilter.GaussianBlur(radius=4)), (0, max(0, split - 12)))

dest = C.COMFY_INPUT + "\\" + out_name
out.convert("RGB").save(dest)
print(f"原圖 {w}x{h}，地板從 y={split} 起抹平")
print("已存：", dest)
