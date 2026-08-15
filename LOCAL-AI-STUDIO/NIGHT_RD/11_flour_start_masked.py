# -*- coding: utf-8 -*-
"""起始圖第二次嘗試：只對 Taco 做 inpaint，用遮罩保護 Nova 與場景。

第一次（10_make_flour_start.py）全圖 img2img 失敗，原因很明確：
denoise 是整張均勻施加的，所以
  - 「clumpy uneven texture」被套到地板 → 麵粉變成塊狀碎片
  - Nova 一起被重繪 → 0.30 就開始變，0.50 完全崩壞
本機模型重繪 Nova 必壞，這跟先前 4/4 配角失敗一致。

所以這次先用 rembg 抓前景，取「重心最低的那一塊」當 Taco
（他在前景貼近鏡頭，Nova 躺在後方），只把那塊餵給 inpaint。

用法（要用系統 Python，rembg 在那裡）：
  "C:/Users/TUF Gaming/AppData/Local/Programs/Python/Python313/python.exe" 11_flour_start_masked.py
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
OUT = HERE / "flour_start"; OUT.mkdir(exist_ok=True, parents=True)
SRC = Path(r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼\auto\clips\d4s1_scene.jpg")
COMFY_IN = Path(r"C:\Users\TUF Gaming\ai-video-local\ComfyUI\input")


def main():
    import cv2
    from rembg import new_session, remove

    img = Image.open(SRC).convert("RGB")
    W, H = img.size
    print(f"原圖 {W}×{H}")

    sess = new_session("u2net")
    alpha = np.asarray(remove(img, session=sess).split()[-1])
    mask = (alpha > 60).astype(np.uint8)

    num, lab, st, cent = cv2.connectedComponentsWithStats(mask, connectivity=8)
    blobs = [(st[i, cv2.CC_STAT_AREA], i, cent[i]) for i in range(1, num)
             if st[i, cv2.CC_STAT_AREA] / mask.size > 0.008]
    if not blobs:
        print("抓不到前景")
        return 1
    print(f"前景區塊 {len(blobs)} 個：")
    for a, i, c in blobs:
        print(f"   面積 {a/mask.size*100:.1f}%  重心 y={c[1]/H:.2f}")

    # Taco 在前景貼近鏡頭 → 重心最低（y 最大）的那一塊
    taco = max(blobs, key=lambda b: b[2][1])
    print(f"→ 判定 Taco：面積 {taco[0]/mask.size*100:.1f}%，重心 y={taco[2][1]/H:.2f}")

    tm = (lab == taco[1]).astype(np.uint8) * 255
    # 稍微膨脹再羽化，讓 inpaint 邊緣不留硬痕
    tm = cv2.dilate(tm, np.ones((9, 9), np.uint8), iterations=2)
    m = Image.fromarray(tm).filter(ImageFilter.GaussianBlur(radius=6))

    m.save(COMFY_IN / "d4s1_taco_mask.png")
    m.save(OUT / "_taco_mask.png")
    # 疊圖檢查遮罩有沒有蓋對
    ov = img.copy()
    red = Image.new("RGB", img.size, (255, 40, 40))
    ov = Image.composite(red, ov, m.point(lambda v: int(v * 0.55)))
    ov.save(OUT / "_mask_check.jpg", quality=92)
    print(f"\n遮罩已存：{COMFY_IN / 'd4s1_taco_mask.png'}")
    print(f"疊圖檢查：{OUT / '_mask_check.jpg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
