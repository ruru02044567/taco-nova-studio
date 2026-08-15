# -*- coding: utf-8 -*-
"""第三階段：拿訓練好的 LoRA 生測試圖，做角度／表情的一致性驗證。

對每個 checkpoint 跑同一組 prompt、同一組 seed，這樣不同 step 之間才比得出差別
（唯一變數只有訓練步數）。

用法：python 03_test_lora.py --who nova
"""
import argparse
import gc
import sys
import time
from pathlib import Path

import torch

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
BASE = r"C:\Users\TUF Gaming\ai-video-local\ComfyUI\models\checkpoints\RealVisXL_V5.0_Lightning_fp16.safetensors"

# 這組 prompt 刻意涵蓋訓練資料「沒有」的角度與情境，
# 才測得出 LoRA 是真的學會這隻狗，還是只背下那 5 張圖。
TESTS = {
    "nova": [
        ("01_front_sit", "nov4dog, siberian husky, full body, sitting, front view, clear light blue eyes, living room, wooden floor"),
        ("02_side_stand", "nov4dog, siberian husky, full body, standing, pure side view profile, clear light blue eyes, living room"),
        ("03_closeup", "nov4dog, siberian husky, extreme close-up of face, clear light blue eyes, black facial mask, sharp detail"),
        ("04_running", "nov4dog, siberian husky, running through a park, outdoor, daylight, clear light blue eyes, full body"),
        ("05_night", "nov4dog, siberian husky, sitting in a dark room at night, dramatic low light, clear light blue eyes"),
        ("06_duo", "nov4dog, a large siberian husky standing next to a tiny white chihuahua, living room, size difference"),
    ],
    "taco": [
        ("01_front_sit", "t4codog, chihuahua, pure white short fur, two black eyebrow spots, blue collar, plain silver tag, sitting, front view, living room"),
        ("02_side_stand", "t4codog, chihuahua, pure white short fur, two black eyebrow spots, full body, pure side view profile, living room"),
        ("03_closeup", "t4codog, chihuahua, extreme close-up of face, two black eyebrow spots on forehead, huge pointed ears, sharp detail"),
        ("04_running", "t4codog, chihuahua, running through a park, outdoor daylight, full body, blue collar"),
        ("05_night", "t4codog, chihuahua, sitting in a dark room at night, dramatic low light, blue collar"),
        ("06_mess", "t4codog, chihuahua, standing in a pile of white flour on the floor, guilty expression, living room"),
    ],
}
NEG = ("blurry, low quality, deformed, extra limbs, text, watermark, "
       "pomeranian, fox-like dog, cream fur, brown eyes, "
       "text on tag, engraved name, lettering on pendant")
SEEDS = [424242, 888999]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--who", required=True, choices=["nova", "taco"])
    ap.add_argument("--scale", type=float, default=0.8)
    args = ap.parse_args()

    from diffusers import EulerAncestralDiscreteScheduler, StableDiffusionXLPipeline

    out_root = HERE / f"test_{args.who}"
    out_root.mkdir(exist_ok=True, parents=True)
    ckpts = sorted((HERE / f"out_{args.who}").glob("*.safetensors"))
    if not ckpts:
        print("找不到 checkpoint")
        return 1
    print(f"找到 {len(ckpts)} 個 checkpoint：{[c.stem.split('_')[-1] for c in ckpts]}")

    print("載入底模型…")
    pipe = StableDiffusionXLPipeline.from_single_file(
        BASE, torch_dtype=torch.float16, add_watermarker=False)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
    pipe.to("cuda")
    pipe.set_progress_bar_config(disable=True)

    tests = TESTS[args.who]
    t0 = time.time()
    total = len(ckpts) * len(tests) * len(SEEDS)
    done = 0

    # 先生一組「沒有 LoRA」的對照組，不然無從判斷 LoRA 到底有沒有作用
    print("\n── 對照組（無 LoRA）──")
    base_dir = out_root / "step000_noLoRA"; base_dir.mkdir(exist_ok=True)
    for name, prompt in tests:
        for sd in SEEDS[:1]:
            img = pipe(prompt=prompt, negative_prompt=NEG, num_inference_steps=8,
                       guidance_scale=2.0, width=768, height=1024,
                       generator=torch.Generator("cuda").manual_seed(sd)).images[0]
            img.save(base_dir / f"{name}_seed{sd}.png")
            print(f"   {name}_seed{sd}")

    for ck in ckpts:
        step = ck.stem.split("step")[-1]
        d = out_root / f"step{step.zfill(4)}"; d.mkdir(exist_ok=True)
        print(f"\n── {ck.name}（scale {args.scale}）──")
        pipe.load_lora_weights(str(ck), adapter_name="c")
        pipe.set_adapters(["c"], adapter_weights=[args.scale])
        for name, prompt in tests:
            for sd in SEEDS:
                img = pipe(prompt=prompt, negative_prompt=NEG, num_inference_steps=8,
                           guidance_scale=2.0, width=768, height=1024,
                           generator=torch.Generator("cuda").manual_seed(sd)).images[0]
                img.save(d / f"{name}_seed{sd}.png")
                done += 1
                el = time.time() - t0
                print(f"   {name}_seed{sd}   ({done}/{total}, {el/60:.1f} 分)")
        pipe.unload_lora_weights()
        gc.collect(); torch.cuda.empty_cache()

    print(f"\n✅ 測試圖生成完畢，耗時 {(time.time()-t0)/60:.1f} 分 → {out_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
