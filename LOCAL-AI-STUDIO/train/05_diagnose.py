# -*- coding: utf-8 -*-
"""診斷：LoRA 是不是把 Lightning 的蒸餾特性打壞了？

假設：RealVisXL V5 **Lightning** 是蒸餾模型，被訓練成用 8 步大跨距取樣。
我用標準 DDPM 1000 步排程訓 LoRA，等於教 LoRA 把模型「修正回」非蒸餾的行為，
結果就是取樣步數不夠 → 糊、低對比。

若假設成立，**同一個 LoRA 用更多步數 + 正常 CFG 取樣，畫質應該會回來。**

用法：python 05_diagnose.py
"""
import sys
from pathlib import Path

import torch

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
BASE = r"C:\Users\TUF Gaming\ai-video-local\ComfyUI\models\checkpoints\RealVisXL_V5.0_Lightning_fp16.safetensors"
LORA = HERE / "out_nova" / "nova_lora_V1_step1000.safetensors"

PROMPT = ("nov4dog, siberian husky, full body, sitting, front view, "
          "clear light blue eyes, living room, wooden floor")
NEG = "blurry, low quality, deformed, pomeranian, fox-like dog, cream fur, brown eyes"
SEED = 424242

# (標籤, LoRA 權重, 步數, CFG)
CASES = [
    ("A_原設定_8步_cfg2_scale0.8", 0.8, 8, 2.0),
    ("B_多步_25步_cfg6_scale0.8", 0.8, 25, 6.0),
    ("C_多步_25步_cfg6_scale1.0", 1.0, 25, 6.0),
    ("D_弱化_8步_cfg2_scale0.3", 0.3, 8, 2.0),
    ("E_中間_16步_cfg4_scale0.6", 0.6, 16, 4.0),
]


def main():
    from diffusers import EulerAncestralDiscreteScheduler, StableDiffusionXLPipeline

    out = HERE / "diagnose"; out.mkdir(exist_ok=True)
    print("載入底模型…")
    pipe = StableDiffusionXLPipeline.from_single_file(
        BASE, torch_dtype=torch.float16, add_watermarker=False)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
    pipe.to("cuda"); pipe.set_progress_bar_config(disable=True)

    # 基準：完全不掛 LoRA，8 步（模型原本的最佳設定）
    img = pipe(prompt=PROMPT.replace("nov4dog, ", ""), negative_prompt=NEG,
               num_inference_steps=8, guidance_scale=2.0, width=768, height=1024,
               generator=torch.Generator("cuda").manual_seed(SEED)).images[0]
    img.save(out / "BASE_noLoRA_8步.png"); print("   BASE_noLoRA_8步")

    pipe.load_lora_weights(str(LORA), adapter_name="c")
    for tag, scale, steps, cfg in CASES:
        pipe.set_adapters(["c"], adapter_weights=[scale])
        img = pipe(prompt=PROMPT, negative_prompt=NEG,
                   num_inference_steps=steps, guidance_scale=cfg,
                   width=768, height=1024,
                   generator=torch.Generator("cuda").manual_seed(SEED)).images[0]
        img.save(out / f"{tag}.png"); print(f"   {tag}")

    # 排成一張對照表
    from PIL import Image, ImageDraw
    fs = sorted(out.glob("*.png"))
    ims = [Image.open(f).convert("RGB") for f in fs]
    TH = 460
    ims = [i.resize((int(i.width * TH / i.height), TH)) for i in ims]
    W = sum(i.width for i in ims) + 10 * (len(ims) + 1)
    sheet = Image.new("RGB", (W, TH + 34), (24, 24, 24))
    dr = ImageDraw.Draw(sheet); x = 10
    for f, i in zip(fs, ims):
        sheet.paste(i, (x, 28)); dr.text((x + 3, 8), f.stem, fill=(255, 220, 120))
        x += i.width + 10
    sheet.save(out / "_DIAGNOSE.jpg", quality=90)
    print(f"\n✅ {out / '_DIAGNOSE.jpg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
