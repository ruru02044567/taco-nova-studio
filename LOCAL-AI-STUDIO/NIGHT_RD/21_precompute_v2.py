# -*- coding: utf-8 -*-
"""EXP-02 階段一：Nova V2 的潛在向量與文字嵌入預算。

caption 設計是 V2 的核心：

  固定不變（要燒進觸發詞的）：nov4dog + 品種 + 毛色 + 藍眼 + 臉罩 + 體型
  逐張變動（要能被剝離的）  ：場景狀態 + 光線

V1 的失敗不是「沒寫場景」——V1 有寫 `indoor living room, natural window light`。
失敗在**5 張圖的場景全都一樣**，模型沒有對照組可以學會把角色跟場景分開。
V2 用 4 種場景 × 2 種光線提供對照。

用法：python 21_precompute_v2.py
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
BASE = r"C:\Users\TUF Gaming\ai-video-local\ComfyUI\models\checkpoints\RealVisXL_V5.0_Lightning_fp16.safetensors"
DATA = STUDIO / "DATASET" / "dog_support_v2" / "TRAIN"
CACHE = HERE / "cache_nova_v2"
CACHE.mkdir(exist_ok=True, parents=True)

TRIGGER = "nov4dog"

# ── 固定：角色身份（每張都一樣，這是要被學進觸發詞的部分）──
IDENTITY = (f"{TRIGGER}, siberian husky, grey and white fur, black facial mask, "
            f"inverted V forehead marking, clear light blue eyes, large dog, "
            f"upright triangular ears")

# ── 變動：場景狀態 ＋ 光線（每張不同，這是要能被剝離的部分）──
SCENES = {
    "clean": "clean tidy living room, bare wooden floor, soft warm afternoon window light",
    "flood": "standing in a flooded living room, water covering the wooden floor, "
             "wet reflective surfaces, water ripples, bright indoor daylight",
    "flour": "lying asleep on a floor covered in spilled white flour, flour dust "
             "scattered everywhere, a torn paper bag nearby, warm window light",
    "lava":  "lying on a grey sofa above a floor of glowing molten lava, "
             "dramatic orange underlighting, strong warm rim light from below",
}

POSE = {
    "nova_clean_nova_01_closeup.png": "close-up head portrait",
    "nova_clean_nova_02_front_fullbody.png": "full body, sitting, front view",
    "nova_clean_nova_03_front_fullbody.png": "full body, sitting, front view",
    "nova_clean_nova_04_34standing_SIZEREF.png": "full body, standing, three quarter view",
    "nova_clean_nova_05_34lying.png": "lying down on a rug, three quarter view",
    "nova_flood_f002.png": "full body, standing, front view",
    "nova_flood_f005.png": "full body, sitting, front view",
    "nova_flood_f007.png": "full body, sitting, front view",
    "nova_flour_f001.png": "head and shoulders, lying down asleep, eyes closed",
    "nova_flour_f003.png": "head close-up, lying down asleep, eyes closed",
    "nova_lava_f002.png": "full body, lying stretched out on a sofa",
    "nova_lava_f004.png": "full body, lying on a sofa, head resting over the edge",
}


def caption_for(fn):
    scene = fn.split("_")[1] if fn.startswith("nova_") else "clean"
    if scene not in SCENES:
        scene = "clean"
    pose = POSE.get(fn, "full body")
    return f"{IDENTITY}, {pose}, {SCENES[scene]}"


def bucket_size(w, h, target_px=768 * 768, mult=64):
    ar = w / h
    nh = (target_px / ar) ** 0.5
    nw = nh * ar
    return (max(mult, int(round(nw / mult)) * mult),
            max(mult, int(round(nh / mult)) * mult))


def main():
    from diffusers import AutoencoderKL, StableDiffusionXLPipeline

    files = sorted(DATA.glob("*.png"))
    if not files:
        print("找不到訓練圖")
        return 1
    print(f"{len(files)} 張訓練圖\n")

    caps = {f.name: caption_for(f.name) for f in files}
    for f in files:
        sc = f.name.split("_")[1]
        print(f"   {f.name:<42} scene={sc}")

    print("\n載入底模型…")
    pipe = StableDiffusionXLPipeline.from_single_file(
        BASE, torch_dtype=torch.float16, add_watermarker=False)
    dev = "cuda"

    print("計算文字嵌入…")
    pipe.text_encoder.to(dev); pipe.text_encoder_2.to(dev)
    embeds = {}
    with torch.no_grad():
        for f in files:
            pe, _, ppe, _ = pipe.encode_prompt(
                prompt=caps[f.name], prompt_2=caps[f.name], device=dev,
                num_images_per_prompt=1, do_classifier_free_guidance=False)
            embeds[f.name] = (pe[0].cpu().clone(), ppe[0].cpu().clone())
    pipe.text_encoder.to("cpu"); pipe.text_encoder_2.to("cpu")
    del pipe.text_encoder, pipe.text_encoder_2
    gc.collect(); torch.cuda.empty_cache()

    print("計算 VAE 潛在向量（fp32 避免 NaN）…")
    vae = AutoencoderKL.from_single_file(BASE, torch_dtype=torch.float32).to(dev).eval()
    recs = []
    with torch.no_grad():
        for f in files:
            im = Image.open(f).convert("RGB")
            w, h = bucket_size(*im.size)
            im = im.resize((w, h), Image.LANCZOS)
            arr = torch.frombuffer(bytearray(im.tobytes()), dtype=torch.uint8)
            x = (arr.reshape(h, w, 3).float() / 127.5 - 1.0).permute(2, 0, 1)[None].to(dev)
            lat = vae.encode(x).latent_dist.sample() * vae.config.scaling_factor
            pe, ppe = embeds[f.name]
            recs.append({"name": f.name, "latent": lat[0].cpu().clone(),
                         "prompt_embeds": pe, "pooled": ppe,
                         "orig_size": (h, w), "caption": caps[f.name]})
            print(f"   {f.name:<42} {w}x{h}")
            del x, lat
            gc.collect(); torch.cuda.empty_cache()

    vae.to("cpu"); del vae, pipe
    gc.collect(); torch.cuda.empty_cache()

    torch.save(recs, CACHE / "cache.pt")
    (CACHE / "captions.json").write_text(
        json.dumps(caps, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ {CACHE/'cache.pt'}  ({(CACHE/'cache.pt').stat().st_size/1024/1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
