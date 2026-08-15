# -*- coding: utf-8 -*-
"""用兩個角色 LoRA 生一張正式場景圖，並計時。

這是驗證「本機能不能取代 Gemini 生第一張圖」的實測。
D9S1（紅酒片）是刻意挑的：兩隻狗同框、體型差、黑點眉、地上的液體——
每一項都是先前本機做不到的。

用法：python 07_make_scene.py
"""
import sys
import time
from pathlib import Path

import torch

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
BASE = r"C:\Users\TUF Gaming\ai-video-local\ComfyUI\models\checkpoints\RealVisXL_V5.0_Lightning_fp16.safetensors"
NOVA = HERE / "out_nova" / "nova_lora_V1_step1000.safetensors"
TACO = HERE / "out_taco" / "taco_lora_V1_step1000.safetensors"
OUT = HERE / "scene_d9s1"; OUT.mkdir(exist_ok=True)

PROMPT = (
    "t4codog, a tiny pure white chihuahua with two black eyebrow spots, blue collar, "
    "plain silver tag, standing in the middle of a huge dark red wine stain on a "
    "snow-white long-pile rug, its front paws stained wine-red, guilty squinting face, "
    "an overturned empty wine glass beside it, "
    "nov4dog, a large siberian husky with clear light blue eyes sitting at the edge of "
    "the frame watching, the husky is about three times the size of the chihuahua, "
    "bright modern living room, light wood floor, grey fabric sofa, warm afternoon "
    "window light, photorealistic, 9:16 vertical, floor level camera angle"
)
NEG = (
    "blurry, low quality, deformed, extra limbs, text, watermark, "
    "pomeranian, fox-like dog, cream fur, brown eyes, "
    "text on tag, engraved name, lettering on pendant, "
    "two huskies, three dogs, duplicate dog, human, person, hand"
)
SEEDS = [424242, 888999, 100001, 555777]


def main():
    from diffusers import EulerAncestralDiscreteScheduler, StableDiffusionXLPipeline

    t_load = time.time()
    print("載入底模型…")
    pipe = StableDiffusionXLPipeline.from_single_file(
        BASE, torch_dtype=torch.float16, add_watermarker=False)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
    pipe.to("cuda"); pipe.set_progress_bar_config(disable=True)

    pipe.load_lora_weights(str(NOVA), adapter_name="nova")
    pipe.load_lora_weights(str(TACO), adapter_name="taco")
    pipe.set_adapters(["nova", "taco"], adapter_weights=[0.35, 0.35])
    load_s = time.time() - t_load
    print(f"   載入完成 {load_s:.1f} 秒（兩個 LoRA 同時掛，各 0.35）\n")

    times = []
    for sd in SEEDS:
        t0 = time.time()
        img = pipe(prompt=PROMPT, negative_prompt=NEG, num_inference_steps=8,
                   guidance_scale=2.0, width=768, height=1344,
                   generator=torch.Generator("cuda").manual_seed(sd)).images[0]
        dt = time.time() - t0
        times.append(dt)
        p = OUT / f"d9s1_scene_seed{sd}.png"
        img.save(p)
        print(f"   seed {sd}  {dt:.1f} 秒  → {p.name}")

    print(f"\n模型載入 {load_s:.1f} 秒 ＋ 每張 {sum(times)/len(times):.1f} 秒")

    # 四張排一起方便挑
    from PIL import Image, ImageDraw
    ims = [Image.open(OUT / f"d9s1_scene_seed{s}.png").convert("RGB") for s in SEEDS]
    TH = 620
    ims = [i.resize((int(i.width * TH / i.height), TH)) for i in ims]
    W = sum(i.width for i in ims) + 10 * (len(ims) + 1)
    sh = Image.new("RGB", (W, TH + 28), (24, 24, 24))
    dr = ImageDraw.Draw(sh); x = 10
    for s, i in zip(SEEDS, ims):
        sh.paste(i, (x, 24)); dr.text((x + 3, 6), f"seed {s}", fill=(255, 220, 120))
        x += i.width + 10
    sh.save(OUT / "_PICK.jpg", quality=92)
    print(f"✅ {OUT / '_PICK.jpg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
