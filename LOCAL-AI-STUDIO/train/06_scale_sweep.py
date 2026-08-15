# -*- coding: utf-8 -*-
"""權重掃描：找出這個 LoRA 該用多強。

05_diagnose 的結論是「LoRA 權重才是主導變數」——
scale 0.8 以上畫面直接糊掉，scale 0.3 反而銳利又正確。
這支把 scale 掃一遍，配上多個情境，找出可用區間。

用法：python 06_scale_sweep.py --who nova
"""
import argparse
import sys
from pathlib import Path

import torch
from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
BASE = r"C:\Users\TUF Gaming\ai-video-local\ComfyUI\models\checkpoints\RealVisXL_V5.0_Lightning_fp16.safetensors"

SCALES = [0.0, 0.15, 0.25, 0.35, 0.45, 0.60]
SCENES = {
    "nova": [
        ("front_sit", "nov4dog, siberian husky, full body, sitting, front view, clear light blue eyes, living room, wooden floor"),
        ("closeup", "nov4dog, siberian husky, close-up of face, clear light blue eyes, black facial mask, sharp detail"),
        ("side", "nov4dog, siberian husky, full body, standing, side view profile, clear light blue eyes, living room"),
    ],
    "taco": [
        ("front_sit", "t4codog, chihuahua, pure white short fur, two black eyebrow spots, blue collar, plain silver tag, sitting, front view, living room"),
        ("closeup", "t4codog, chihuahua, close-up of face, two black eyebrow spots on forehead, huge pointed ears, sharp detail"),
        ("side", "t4codog, chihuahua, pure white short fur, full body, standing, side view profile, blue collar, living room"),
    ],
}
NEG = ("blurry, low quality, deformed, extra limbs, text, watermark, "
       "pomeranian, fox-like dog, cream fur, brown eyes, text on tag, engraved name")
SEED = 424242


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", required=True, choices=["nova", "taco"])
    ap.add_argument("--ckpt", default="step1000")
    args = ap.parse_args()

    from diffusers import EulerAncestralDiscreteScheduler, StableDiffusionXLPipeline

    lora = HERE / f"out_{args.who}" / f"{args.who}_lora_V1_{args.ckpt}.safetensors"
    out = HERE / f"sweep_{args.who}"; out.mkdir(exist_ok=True)

    print("載入底模型…")
    pipe = StableDiffusionXLPipeline.from_single_file(
        BASE, torch_dtype=torch.float16, add_watermarker=False)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
    pipe.to("cuda"); pipe.set_progress_bar_config(disable=True)
    pipe.load_lora_weights(str(lora), adapter_name="c")

    grid = {}
    for scene, prompt in SCENES[args.who]:
        for sc in SCALES:
            pipe.set_adapters(["c"], adapter_weights=[sc])
            # scale 0 等於沒掛 LoRA，但觸發詞留著，才是公平對照
            img = pipe(prompt=prompt, negative_prompt=NEG, num_inference_steps=8,
                       guidance_scale=2.0, width=768, height=1024,
                       generator=torch.Generator("cuda").manual_seed(SEED)).images[0]
            p = out / f"{scene}_scale{sc:.2f}.png"
            img.save(p); grid[(scene, sc)] = p
            print(f"   {scene:<10} scale {sc:.2f}")

    # 對照表：每列一個情境，橫向是 scale
    TH, PAD, HDR = 400, 6, 30
    rows = []
    for scene, _ in SCENES[args.who]:
        tiles = []
        for sc in SCALES:
            im = Image.open(grid[(scene, sc)]).convert("RGB")
            tiles.append((f"{sc:.2f}", im.resize((int(im.width * TH / im.height), TH))))
        W = sum(t[1].width for t in tiles) + PAD * (len(tiles) + 1)
        row = Image.new("RGB", (W, TH + HDR + PAD), (24, 24, 24))
        dr = ImageDraw.Draw(row)
        dr.text((PAD, 4), f"{args.who} / {scene}", fill=(255, 220, 120))
        x = PAD
        for lab, im in tiles:
            row.paste(im, (x, HDR)); dr.text((x + 3, 17), f"scale {lab}", fill=(150, 200, 255))
            x += im.width + PAD
        rows.append(row)
    W = max(r.width for r in rows); H = sum(r.height for r in rows)
    big = Image.new("RGB", (W, H), (24, 24, 24)); y = 0
    for r in rows:
        big.paste(r, (0, y)); y += r.height
    p = out / f"_SWEEP_{args.who}.jpg"
    big.save(p, quality=88)
    print(f"\n✅ {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
