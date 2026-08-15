# -*- coding: utf-8 -*-
"""EXP-04：髒污顏色對照實驗（最小控制變因）

要驗證的假設：
「白麵粉附著在純白短毛上，視覺對比接近於零，所以模型畫不出來。」

這句目前只是**合理假設**，不是已證實事實。本實驗把它變成可否證的命題。

四組只改一個變數：**髒污的顏色**。
  A 白粉      ← 目前 D4S1 用的
  B 淺灰粉
  C 淺棕粉
  D 黑色髒污  ← 排程上的 D11S1 黑漆片

其餘全部固定：模型、seed、prompt 結構、構圖描述、步數、CFG、解析度。

三種可能的結論：
  1. 只有 A 失敗，B/C/D 成功 → **對比假設成立**，不要再硬攻白粉
  2. 全部失敗            → 問題不在顏色，在「附著」這個概念本身模型畫不出來
  3. 全部成功            → 問題不在起始圖，在 i2v 的動態生成能力

用法：python 24_contrast_test.py
"""
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼\auto")
sys.stdout.reconfigure(encoding="utf-8")
import comfy_api as C  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "contrast_short"; OUT.mkdir(exist_ok=True)
CKPT = "RealVisXL_V5.0_Lightning_fp16.safetensors"
SEED = 424242
STEPS, CFG = 8, 2.0
W, H = 768, 1152

# prompt 結構完全一樣，只有 {} 裡的顏色詞在變
TEMPLATE = (
    "photo of a pure white chihuahua covered in {powder}, thick {powder} "
    "caked all over his fur and back, photorealistic"
)
NEG = ("clean fur, wet fur, snow, cartoon, illustration, 3d render, deformed, "
       "extra limbs, blurry, low quality, text, watermark, "
       "powder around the nose, powder from the mouth")

CASES = [
    ("A_白粉",   "white flour powder"),
    ("B_淺灰粉", "light grey ash powder"),
    ("C_淺棕粉", "light brown cocoa powder"),
    ("D_黑髒污", "black paint smeared and black soot powder"),
]


def build(powder, tag):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": TEMPLATE.format(powder=powder), "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": W, "height": H, "batch_size": 1}},
        "8": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
                         "latent_image": ["4", 0], "seed": SEED, "steps": STEPS, "cfg": CFG,
                         "sampler_name": "dpmpp_sde", "scheduler": "karras", "denoise": 1.0}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"images": ["9", 0], "filename_prefix": f"contrastS/{tag}"}},
    }


def main():
    C.require_server()
    made = []
    for tag, powder in CASES:
        print(f"\n▶ {tag}  ({powder})")
        t0 = time.time()
        try:
            imgs = C.run(build(powder, tag), tag=tag, timeout=600)
            if imgs:
                p = OUT / f"{tag}.png"
                shutil.copy2(imgs[0], p); made.append((tag, p))
                print(f"   ✅ {time.time()-t0:.0f}s")
        except Exception as e:
            print(f"   ❌ {type(e).__name__}: {str(e)[:140]}")

    if not made:
        return 1
    from PIL import Image, ImageDraw
    TH = 760
    ims = [(t, Image.open(p).convert("RGB")) for t, p in made]
    ims = [(t, i.resize((int(i.width * TH / i.height), TH))) for t, i in ims]
    Wd = sum(i.width for _, i in ims) + 10 * (len(ims) + 1)
    sh = Image.new("RGB", (Wd, TH + 26), (24, 24, 24))
    dr = ImageDraw.Draw(sh); x = 10
    for t, i in ims:
        sh.paste(i, (x, 22)); dr.text((x + 3, 5), t, fill=(255, 220, 120)); x += i.width + 10
    p = OUT / "_CONTRAST.jpg"
    sh.save(p, quality=93)
    print(f"\n✅ {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
