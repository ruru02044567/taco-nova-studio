# -*- coding: utf-8 -*-
"""下一輪實驗：做一張「Taco 毛上厚厚附著麵粉」的新起始圖。

為什麼用 img2img 低 denoise，不重新生一張：
指示要求「必須維持原本構圖、原本角色比例、原本角色身份」。
重生整張圖一定會動到這三樣（本機生 Nova 目前 4/4 錯犬種）。
img2img 把原圖編碼成 latent 再只加一點噪聲重跑，構圖與角色是被「保護」下來的，
改的只有表面材質 —— 正好就是這次要改的唯一變數。

denoise 掃 0.30 / 0.40 / 0.50 三檔，挑「麵粉明顯附著、但 Nova 與構圖沒動」的那張。

用法：python 10_make_flour_start.py
"""
import json
import shutil
import sys
import time
import urllib.request
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼\auto")
import comfy_api as C  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "flour_start"; OUT.mkdir(exist_ok=True, parents=True)
CKPT = "RealVisXL_V5.0_Lightning_fp16.safetensors"
SRC = "d4s1_scene_orig.jpg"

# 重點寫在「麵粉附著在毛上」，而且明確點出部位（背、肩、頸、耳、體側、尾）。
# 不寫嘴、不寫鼻 —— 那是規則 10 的紅線。
POS = (
    "a tiny pure snow-white chihuahua thickly caked in white flour, dry powdered flour "
    "clinging in uneven clumps and patches all over his coat, heavy flour dust settled on "
    "his back, on his shoulders, around his neck and collar, on the base of his ears, "
    "along both flanks and around his tail, the powder sitting visibly on top of the fur "
    "with clumpy uneven texture, floury paw prints on the wood floor, a torn paper flour "
    "bag beside him, a large grey and white siberian husky asleep behind him, "
    "bright modern living room, warm afternoon window light, photorealistic"
)
NEG = (
    "flour on the muzzle, powder around the nose, powder coming from the mouth, "
    "clean fur, wet fur, snow, cartoon, illustration, 3d render, "
    "extra dog, duplicate dog, deformed, blurry, low quality, text, watermark"
)


def build(denoise, seed):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "LoadImage", "inputs": {"image": SRC}},
        "3": {"class_type": "VAEEncode", "inputs": {"pixels": ["2", 0], "vae": ["1", 2]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": POS, "clip": ["1", 1]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["1", 1]}},
        # Lightning 模型步數少，但 img2img 的有效步數 = steps × denoise，
        # denoise 0.3 配 6 步等於只跑 1.8 步，材質長不出來 → 步數拉到 12。
        "6": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
                         "latent_image": ["3", 0], "seed": seed, "steps": 12, "cfg": 2.0,
                         "sampler_name": "dpmpp_sde", "scheduler": "karras",
                         "denoise": denoise}},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage",
              "inputs": {"images": ["7", 0], "filename_prefix": f"flourstart/d{denoise:.2f}"}},
    }


def main():
    C.require_server()
    made = []
    for dn in [0.30, 0.40, 0.50]:
        tag = f"denoise{dn:.2f}"
        print(f"\n▶ {tag}")
        try:
            imgs = C.run(build(dn, 424243), tag=tag, timeout=600)
            if imgs:
                p = OUT / f"start_{tag}.png"
                shutil.copy2(imgs[0], p)
                made.append((dn, p))
                print(f"   ✅ {p.name}")
        except Exception as e:
            print(f"   ❌ {type(e).__name__}: {str(e)[:140]}")

    if not made:
        return 1
    # 跟原圖並排，方便判斷「麵粉有沒有附著上去、Nova 有沒有被動到」
    from PIL import Image, ImageDraw
    items = [("原圖 d4s1_scene", Path(r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼\auto\clips\d4s1_scene.jpg"))]
    items += [(f"denoise {dn:.2f}", p) for dn, p in made]
    TH = 700
    ims = [(lab, Image.open(p).convert("RGB")) for lab, p in items]
    ims = [(lab, im.resize((int(im.width * TH / im.height), TH))) for lab, im in ims]
    W = sum(im.width for _, im in ims) + 10 * (len(ims) + 1)
    sh = Image.new("RGB", (W, TH + 26), (24, 24, 24))
    dr = ImageDraw.Draw(sh); x = 10
    for lab, im in ims:
        sh.paste(im, (x, 22)); dr.text((x + 3, 5), lab, fill=(255, 220, 120)); x += im.width + 10
    sh.save(OUT / "_COMPARE_起始圖.jpg", quality=93)
    print(f"\n✅ {OUT / '_COMPARE_起始圖.jpg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
