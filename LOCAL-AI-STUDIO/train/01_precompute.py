# -*- coding: utf-8 -*-
"""第一階段：把 VAE 潛在向量與文字嵌入預先算好存到硬碟。

為什麼要拆兩階段（8 GB VRAM 的關鍵）：
SDXL 的 UNet(5GB) + VAE(0.3GB) + 兩個文字編碼器(1.7GB) 同時放進 8 GB
再加上訓練用的梯度與 activation，一定 OOM。
但 VAE 與文字編碼器在訓練過程中「輸出永遠一樣」——同一張圖、同一句 caption
每一步算出來的東西完全相同，本來就沒有理由每步重算。
先算一次存檔，訓練時整個卸掉，UNet 就能獨佔顯存。

用法：python 01_precompute.py
"""
import gc
import json
import sys
from pathlib import Path

import torch
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
STUDIO = HERE.parent
# 2026-08-12：原本要用 sd_xl_base_1.0.safetensors，實測該檔**已損毀**
# （SafetensorError: incomplete metadata, file not fully covered），改用實際生圖用的底座。
# 訓練與推論同一個底座，LoRA 的貼合度反而更好。
BASE = r"C:\Users\TUF Gaming\ai-video-local\ComfyUI\models\checkpoints\RealVisXL_V5.0_Lightning_fp16.safetensors"
DATA = None   # 由 WHO 決定，見下
CACHE = None
import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--who", default="nova", choices=["nova", "taco"])
WHO = _ap.parse_args().who
TRIGGER = {"nova": "nov4dog", "taco": "t4codog"}[WHO]

# 每張圖的 caption。角度寫進去，讓 LoRA 學到「這隻狗在不同角度長什麼樣」，
# 而不是把某個固定姿勢跟角色綁在一起。
ALL_CAPTIONS = {
 "nova": {
    "nova_01_closeup.png":
        f"{TRIGGER}, siberian husky, close-up head portrait, grey and white fur, "
        f"black facial mask, inverted V forehead marking, clear light blue eyes, "
        f"upright triangular ears, indoor living room, natural window light",
    "nova_02_front_fullbody.png":
        f"{TRIGGER}, siberian husky, full body, sitting, front view, grey and white fur, "
        f"black facial mask, clear light blue eyes, large dog, wooden floor, living room",
    "nova_03_front_fullbody.png":
        f"{TRIGGER}, siberian husky, full body, sitting, front view, grey and white fur, "
        f"black facial mask, clear light blue eyes, large dog, indoor, natural light",
    "nova_04_34standing_SIZEREF.png":
        f"{TRIGGER}, siberian husky, full body, standing, three quarter view, "
        f"grey and white fur, black facial mask, clear light blue eyes, large dog, wooden floor",
    "nova_05_34lying.png":
        f"{TRIGGER}, siberian husky, lying down on a rug, three quarter view, "
        f"grey and white fur, black facial mask, clear light blue eyes, large dog, resting",
 },
 "taco": {
    "taco_01_closeup.png":
        f"{TRIGGER}, chihuahua, close-up head portrait, pure white short fur, "
        f"two black eyebrow spots on forehead, huge pointed ears, dark grey muzzle shading, "
        f"blue collar, plain silver tag, chin up proud expression, indoor living room",
    "taco_02_front_squint.jpg":
        f"{TRIGGER}, chihuahua, full body, sitting, front view, pure white short fur, "
        f"two black eyebrow spots, huge pointed ears, blue collar, plain silver tag, "
        f"squinting smug smile, wooden floor",
    "taco_03_34side_openmouth.jpg":
        f"{TRIGGER}, chihuahua, full body, sitting, three quarter side view, pure white short fur, "
        f"two black eyebrow spots, huge pointed ears, blue collar, plain silver tag, "
        f"open mouth grin, living room",
    "taco_04_front_fullbody.png":
        f"{TRIGGER}, chihuahua, full body, sitting, front view, pure white short fur, "
        f"two black eyebrow spots, huge pointed ears, blue collar, plain silver tag, wooden floor",
    "taco_05_front_fullbody.png":
        f"{TRIGGER}, chihuahua, full body, sitting, front view, pure white short fur, "
        f"two black eyebrow spots, huge pointed ears, blue collar, plain silver tag, indoor",
 },
}
CAPTIONS = ALL_CAPTIONS[WHO]
DATA = STUDIO / "DATASET" / ("dog_support" if WHO == "nova" else "dog_main") / "TRAIN"
CACHE = HERE / f"cache_{WHO}"
CACHE.mkdir(exist_ok=True, parents=True)


def bucket_size(w, h, target_px=768 * 768, mult=64):
    """把原圖比例縮到總像素接近 768²，長寬各自對齊 64 的倍數。

    不用正方形置中裁切，因為全身站姿的圖裁成正方形會把狗的頭或腳切掉——
    對角色 LoRA 來說那是致命的資訊損失。
    """
    ar = w / h
    nh = (target_px / ar) ** 0.5
    nw = nh * ar
    nw = max(mult, int(round(nw / mult)) * mult)
    nh = max(mult, int(round(nh / mult)) * mult)
    return nw, nh


def main():
    from diffusers import AutoencoderKL, StableDiffusionXLPipeline

    files = sorted(DATA.glob("*.png")) + sorted(DATA.glob("*.jpg"))
    files = [f for f in files if f.name in CAPTIONS]
    if not files:
        print("找不到訓練圖，請確認", DATA)
        return 1
    print(f"找到 {len(files)} 張訓練圖\n")

    print("載入 SDXL base（只為了取 VAE 與文字編碼器）…")
    pipe = StableDiffusionXLPipeline.from_single_file(
        BASE, torch_dtype=torch.float16, add_watermarker=False,
    )
    dev = "cuda"

    # ── 文字嵌入 ──────────────────────────────────────────────
    print("計算文字嵌入…")
    pipe.text_encoder.to(dev)
    pipe.text_encoder_2.to(dev)
    embeds = {}
    with torch.no_grad():
        for f in files:
            pe, _, ppe, _ = pipe.encode_prompt(
                prompt=CAPTIONS[f.name], prompt_2=CAPTIONS[f.name],
                device=dev, num_images_per_prompt=1, do_classifier_free_guidance=False,
            )
            embeds[f.name] = (pe[0].cpu().clone(), ppe[0].cpu().clone())
            print(f"   {f.name:<34} {tuple(pe[0].shape)}  pooled {tuple(ppe[0].shape)}")
    pipe.text_encoder.to("cpu"); pipe.text_encoder_2.to("cpu")
    del pipe.text_encoder, pipe.text_encoder_2
    gc.collect(); torch.cuda.empty_cache()

    # ── VAE 潛在向量 ──────────────────────────────────────────
    # SDXL 原版 VAE 在 fp16 會產生 NaN，這裡一律用 fp32 跑。
    # 只跑 5 張、一次性，慢一點無所謂。
    print("\n計算 VAE 潛在向量（fp32 避免 NaN）…")
    vae = AutoencoderKL.from_single_file(BASE, torch_dtype=torch.float32).to(dev)
    vae.eval()
    records = []
    with torch.no_grad():
        for f in files:
            im = Image.open(f).convert("RGB")
            w, h = bucket_size(*im.size)
            im = im.resize((w, h), Image.LANCZOS)
            x = torch.from_numpy(
                (torch.frombuffer(im.tobytes(), dtype=torch.uint8)
                 .reshape(h, w, 3).numpy() / 127.5 - 1.0)
            ).permute(2, 0, 1).unsqueeze(0).float().to(dev)
            lat = vae.encode(x).latent_dist.sample() * vae.config.scaling_factor
            pe, ppe = embeds[f.name]
            rec = {
                "name": f.name,
                "latent": lat[0].cpu().clone(),
                "prompt_embeds": pe,
                "pooled": ppe,
                "orig_size": (h, w),
                "target_size": (h, w),
                "crop_top_left": (0, 0),
                "caption": CAPTIONS[f.name],
            }
            records.append(rec)
            print(f"   {f.name:<34} {w}x{h}  →  latent {tuple(lat[0].shape)}")

    vae.to("cpu"); del vae
    gc.collect(); torch.cuda.empty_cache()

    torch.save(records, CACHE / "cache.pt")
    (CACHE / "captions.json").write_text(
        json.dumps(CAPTIONS, ensure_ascii=False, indent=2), encoding="utf-8")
    mb = (CACHE / "cache.pt").stat().st_size / 1024 / 1024
    print(f"\n✅ 快取完成：{CACHE / 'cache.pt'}  ({mb:.1f} MB)")
    print(f"   觸發詞：{TRIGGER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
