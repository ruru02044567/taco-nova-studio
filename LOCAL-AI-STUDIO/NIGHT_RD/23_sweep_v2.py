# -*- coding: utf-8 -*-
"""EXP-03：Nova V2 權重掃描（控制變因實驗）

要回答的唯一問題：
**「Nova 品種正確」與「紅酒漬完整」能不能同時成立？**

V1 的實測是不能——權重越高 Nova 越對，紅酒漬被抹得越乾淨，是一條乾淨的權衡曲線。
V2 的訓練集加入了髒亂場景，如果假設成立，這條曲線應該**右移**：
更高的權重仍然保得住酒漬。

固定：深度圖、seed、ControlNet 強度、IP-Adapter 設定、步數、CFG、解析度
唯一變數：LoRA 權重（0.00 / 0.15 / 0.25 / 0.35 / 0.45）

用法：python 23_sweep_v2.py [--version V2|V1] [--ckpt step1500]
"""
import argparse
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼\auto")
sys.stdout.reconfigure(encoding="utf-8")
import comfy_api as C  # noqa: E402

HERE = Path(__file__).parent
CKPT = "RealVisXL_V5.0_Lightning_fp16.safetensors"
DEPTH = "d9s1_depth_clean.png"          # 8/11 用 clean_depth.py 磨過地板的版本
REF = "duo_full.png"
STEPS, CFG = 6, 1.8
W, H = 768, 1152
SEED = 424242
CN_STRENGTH, CN_END = 0.70, 0.50
WEIGHTS = [0.00, 0.15, 0.25, 0.35, 0.45]

CHAR = ("t4codog and nov4dog, a tiny pure snow-white smooth-coat chihuahua with two "
        "small round black dot markings above its eyes, oversized pointy ears, thin blue "
        "collar with a small round silver tag, and a large fluffy grey and white siberian "
        "husky with pale blue eyes sitting nearby")
SCENE = ("The chihuahua stands in the middle of a large burgundy red wine stain soaked into "
         "a snow-white shag rug, a tipped-over wine glass beside it, its front paws stained "
         "dark red. The husky sits a few feet away watching.")
STYLE = ("photorealistic home video still, floor level, bright modern living room, "
         "light wood floor, grey fabric sofa, warm afternoon window light")
NEG = ("cartoon, anime, 3d render, three dogs, multiple dogs, extra dog, duplicate dog, "
       "second husky, extra limbs, deformed, human, person, hand, "
       "pomeranian, fox-like dog, klee kai, brown eyes, cream fur, "
       "text on tag, engraved name, text, watermark, blurry, low quality")


def build(lora_name, weight):
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": W, "height": H, "batch_size": 1}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"images": ["9", 0], "filename_prefix": "sweepv2/x"}},
    }
    model_src, clip_src = ["1", 0], ["1", 1]
    if weight > 0:
        wf["40"] = {"class_type": "LoraLoader",
                    "inputs": {"lora_name": lora_name, "strength_model": weight,
                               "strength_clip": weight, "model": model_src, "clip": clip_src}}
        model_src, clip_src = ["40", 0], ["40", 1]

    wf["2"] = {"class_type": "CLIPTextEncode",
               "inputs": {"text": f"{CHAR}. {SCENE} {STYLE}", "clip": clip_src}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": clip_src}}
    # IP-Adapter 固定開著，跟正式產線一致
    wf["5"] = {"class_type": "LoadImage", "inputs": {"image": REF}}
    wf["6"] = {"class_type": "IPAdapterUnifiedLoader",
               "inputs": {"model": model_src, "preset": "PLUS (high strength)"}}
    wf["7"] = {"class_type": "IPAdapterAdvanced",
               "inputs": {"model": ["6", 0], "ipadapter": ["6", 1], "image": ["5", 0],
                          "weight": 0.65, "weight_type": "linear", "combine_embeds": "concat",
                          "start_at": 0.25, "end_at": 1.0, "embeds_scaling": "V only"}}
    wf["13"] = {"class_type": "LoadImage", "inputs": {"image": DEPTH}}
    wf["16"] = {"class_type": "ControlNetLoader",
                "inputs": {"control_net_name": "xinsir_controlnet_union_sdxl_promax.safetensors"}}
    wf["17"] = {"class_type": "SetUnionControlNetType",
                "inputs": {"control_net": ["16", 0], "type": "depth"}}
    wf["20"] = {"class_type": "ControlNetApplyAdvanced",
                "inputs": {"positive": ["2", 0], "negative": ["3", 0],
                           "control_net": ["17", 0], "image": ["13", 0],
                           "strength": CN_STRENGTH, "start_percent": 0.0,
                           "end_percent": CN_END, "vae": ["1", 2]}}
    wf["8"] = {"class_type": "KSampler",
               "inputs": {"model": ["7", 0], "positive": ["20", 0], "negative": ["20", 1],
                          "latent_image": ["4", 0], "seed": SEED, "steps": STEPS, "cfg": CFG,
                          "sampler_name": "dpmpp_sde", "scheduler": "karras", "denoise": 1.0}}
    return wf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="V2")
    ap.add_argument("--ckpt", default="step1500")
    args = ap.parse_args()

    lora_file = f"nova_lora_{args.version}_{args.ckpt}.safetensors"
    comfy_loras = Path(r"C:\Users\TUF Gaming\ai-video-local\ComfyUI\models\loras")
    src = HERE / f"out_nova_{args.version.lower()}" / lora_file
    if not src.exists():
        print(f"找不到 {src}")
        return 1
    shutil.copy2(src, comfy_loras / lora_file)
    print(f"已放進 ComfyUI: {lora_file}")

    out = HERE / f"sweep_{args.version}"; out.mkdir(exist_ok=True)
    C.require_server()
    made = []
    for w in WEIGHTS:
        tag = f"{args.version}_w{w:.2f}"
        print(f"\n▶ LoRA 權重 {w:.2f}")
        t0 = time.time()
        try:
            imgs = C.run(build(lora_file, w), tag=tag, timeout=600)
            if imgs:
                p = out / f"w{w:.2f}.png"
                shutil.copy2(imgs[0], p); made.append((w, p))
                print(f"   ✅ {time.time()-t0:.0f}s → {p.name}")
        except Exception as e:
            print(f"   ❌ {type(e).__name__}: {str(e)[:140]}")

    if not made:
        return 1
    from PIL import Image, ImageDraw
    TH = 720
    ims = [(f"weight {w:.2f}", Image.open(p).convert("RGB")) for w, p in made]
    ims = [(l, i.resize((int(i.width * TH / i.height), TH))) for l, i in ims]
    Wd = sum(i.width for _, i in ims) + 10 * (len(ims) + 1)
    sh = Image.new("RGB", (Wd, TH + 26), (24, 24, 24))
    dr = ImageDraw.Draw(sh); x = 10
    for l, i in ims:
        sh.paste(i, (x, 22)); dr.text((x + 3, 5), l, fill=(255, 220, 120)); x += i.width + 10
    p = out / f"_SWEEP_{args.version}.jpg"
    sh.save(p, quality=93)
    print(f"\n✅ {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
