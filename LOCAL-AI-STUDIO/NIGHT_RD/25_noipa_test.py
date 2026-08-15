# -*- coding: utf-8 -*-
"""EXP-05：拿掉 IP-Adapter，測 LoRA 單獨的作用力。

為什麼要做這個：
EXP-03 的權重掃描顯示，Nova 的臉在 0.00 到 0.45 之間**幾乎沒有變化**，
V1 與 V2 也長得一樣 —— 眼睛全部是深棕色。

這代表在「ControlNet ＋ IP-Adapter ＋ LoRA」的組合裡，
**Nova 的臉是被 IP-Adapter 釘住的，LoRA 根本擠不進去。**

所以要判斷「V2 有沒有把藍眼學起來」，必須先把 IP-Adapter 拿掉。
這是改變數種類，不是加 seed。

用法：python 25_noipa_test.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼\auto")
sys.stdout.reconfigure(encoding="utf-8")
import comfy_api as C  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "noipa"; OUT.mkdir(exist_ok=True)
CKPT = "RealVisXL_V5.0_Lightning_fp16.safetensors"
DEPTH = "d9s1_depth_clean.png"
SEED, STEPS, CFG = 424242, 6, 1.8
W, H = 768, 1152
CN_STRENGTH, CN_END = 0.70, 0.50

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

CASES = [
    ("A_無LoRA",     None,                                  0.00),
    ("B_V1_0.45",    "nova_lora_V1_step1000.safetensors",   0.45),
    ("C_V2_0.45",    "nova_lora_V2_step1500.safetensors",   0.45),
    ("D_V2_0.70",    "nova_lora_V2_step1500.safetensors",   0.70),
]


def build(lora, w):
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": W, "height": H, "batch_size": 1}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"images": ["9", 0], "filename_prefix": "noipa/x"}},
    }
    m, c = ["1", 0], ["1", 1]
    if lora and w > 0:
        wf["40"] = {"class_type": "LoraLoader",
                    "inputs": {"lora_name": lora, "strength_model": w,
                               "strength_clip": w, "model": m, "clip": c}}
        m, c = ["40", 0], ["40", 1]
    wf["2"] = {"class_type": "CLIPTextEncode",
               "inputs": {"text": f"{CHAR}. {SCENE} {STYLE}", "clip": c}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": c}}
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
               "inputs": {"model": m, "positive": ["20", 0], "negative": ["20", 1],
                          "latent_image": ["4", 0], "seed": SEED, "steps": STEPS, "cfg": CFG,
                          "sampler_name": "dpmpp_sde", "scheduler": "karras", "denoise": 1.0}}
    return wf


def main():
    C.require_server()
    made = []
    for tag, lora, w in CASES:
        print(f"▶ {tag}（無 IP-Adapter）")
        try:
            imgs = C.run(build(lora, w), tag=tag, timeout=600)
            if imgs:
                p = OUT / f"{tag}.png"
                shutil.copy2(imgs[0], p); made.append((tag, p)); print("   ✅")
        except Exception as e:
            print(f"   ❌ {type(e).__name__}: {str(e)[:120]}")
    if not made:
        return 1

    from PIL import Image, ImageDraw
    # 全圖
    TH = 620
    ims = [(t, Image.open(p).convert("RGB")) for t, p in made]
    r = [(t, i.resize((int(i.width * TH / i.height), TH))) for t, i in ims]
    tot = sum(i.width for _, i in r) + 8 * (len(r) + 1)
    s = Image.new("RGB", (tot, TH + 24), (24, 24, 24))
    d = ImageDraw.Draw(s); x = 8
    for t, i in r:
        s.paste(i, (x, 20)); d.text((x + 3, 4), t, fill=(255, 220, 120)); x += i.width + 8
    s.save(OUT / "_NOIPA_FULL.jpg", quality=93)

    # Nova 臉部放大
    TH = 430
    cr = []
    for t, im in ims:
        Wd, Hh = im.size
        c = im.crop((int(0.52 * Wd), int(0.02 * Hh), Wd, int(0.30 * Hh)))
        cr.append((t, c.resize((int(c.width * TH / c.height), TH))))
    tot = sum(i.width for _, i in cr) + 6 * (len(cr) + 1)
    s = Image.new("RGB", (tot, TH + 20), (24, 24, 24))
    d = ImageDraw.Draw(s); x = 6
    for t, i in cr:
        s.paste(i, (x, 16)); d.text((x + 2, 3), t, fill=(255, 220, 120)); x += i.width + 6
    s.save(OUT / "_NOIPA_ZOOM.jpg", quality=95)
    print(f"\n✅ {OUT / '_NOIPA_ZOOM.jpg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
