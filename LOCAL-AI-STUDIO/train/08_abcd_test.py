# -*- coding: utf-8 -*-
"""A/B/C/D 對照：LoRA 到底該取代 IP-Adapter，還是疊在它上面？

背景：
2026-08-12 的實測證明兩件事各管一半——
  LoRA       管得住「這隻狗長什麼樣」（黑點眉、藍眼、灰白毛都回來了）
  ControlNet 管得住「畫面該有幾隻狗、誰站哪裡」
而 IP-Adapter 原本是拿來做前者的，但它做不好（配角外觀 4/4 全失）。

所以真正要問的不是「LoRA 要不要疊上去」，是 **「LoRA 能不能把 IP-Adapter 換掉」**。
四組只改控制方式，深度圖／seed／prompt／取樣參數全部固定。

  A  只有 ControlNet                    → 純構圖基線，看空間控制本身有多強
  B  ControlNet ＋ LoRA                 → 提議的新組合（IP-Adapter 下架）
  C  ControlNet ＋ IP-Adapter           → 目前的正式產線
  D  ControlNet ＋ IP-Adapter ＋ LoRA   → 全部疊起來

用法：python 08_abcd_test.py
"""
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼\auto")
sys.stdout.reconfigure(encoding="utf-8")

import comfy_api as C  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "abcd"; OUT.mkdir(exist_ok=True)

CKPT = "RealVisXL_V5.0_Lightning_fp16.safetensors"
DEPTH = "d9s1_depth_clean.png"      # clean_depth.py 磨過地板的版本
REF = "duo_full.png"
LORA_NOVA, LORA_TACO = "nova_V1_use035.safetensors", "taco_V1_use035.safetensors"
LORA_W = 0.35

STEPS, CFG = 6, 1.8
SAMPLER, SCHED = "dpmpp_sde", "karras"
W, H = 768, 1152
SEED = 424242
CN_STRENGTH, CN_END = 0.70, 0.50    # 8/11 找到的最佳值（紅酒漬那輪）

# 有掛 LoRA 時才加觸發詞。其餘描述兩組完全一樣，才是公平對照。
CHAR_PLAIN = (
    "a tiny pure snow-white smooth-coat chihuahua with two small round black dot "
    "markings above its eyes like little eyebrows, oversized pointy ears, wearing a "
    "thin blue collar with a small round silver tag, and a large fluffy grey and white "
    "siberian husky with pale blue eyes sitting nearby"
)
CHAR_LORA = "t4codog and nov4dog, " + CHAR_PLAIN
SCENE = (
    "The chihuahua stands in the middle of a large burgundy red wine stain soaked into "
    "a snow-white shag rug, a tipped-over wine glass beside it, its front paws stained "
    "dark red, guilty caught-in-the-act expression. The husky sits a few feet away watching."
)
STYLE = ("photorealistic home video still, floor level, bright modern living room, "
         "light wood floor, grey fabric sofa, warm afternoon window light")
NEG = ("cartoon, anime, 3d render, three dogs, multiple dogs, extra dog, duplicate dog, "
       "second husky, extra limbs, deformed, human, person, hand, "
       "text on tag, engraved name, text, watermark, blurry, low quality")


def build(tag, use_lora, use_ipa):
    """回傳 ComfyUI API 格式的 workflow。四組的差別只在 model/clip 的接線。"""
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": W, "height": H, "batch_size": 1}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"images": ["9", 0], "filename_prefix": f"abcd/{tag}"}},
    }
    model_src, clip_src = ["1", 0], ["1", 1]

    # ── LoRA 鏈：兩顆串接，掛在 checkpoint 後面 ──
    if use_lora:
        wf["40"] = {"class_type": "LoraLoader",
                    "inputs": {"lora_name": LORA_NOVA,
                               "strength_model": LORA_W, "strength_clip": LORA_W,
                               "model": model_src, "clip": clip_src}}
        wf["41"] = {"class_type": "LoraLoader",
                    "inputs": {"lora_name": LORA_TACO,
                               "strength_model": LORA_W, "strength_clip": LORA_W,
                               "model": ["40", 0], "clip": ["40", 1]}}
        model_src, clip_src = ["41", 0], ["41", 1]

    char = CHAR_LORA if use_lora else CHAR_PLAIN
    wf["2"] = {"class_type": "CLIPTextEncode",
               "inputs": {"text": f"{char}. {SCENE} {STYLE}", "clip": clip_src}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": clip_src}}

    # ── IP-Adapter：接在 LoRA 之後（如果有的話）──
    if use_ipa:
        wf["5"] = {"class_type": "LoadImage", "inputs": {"image": REF}}
        wf["6"] = {"class_type": "IPAdapterUnifiedLoader",
                   "inputs": {"model": model_src, "preset": "PLUS (high strength)"}}
        wf["7"] = {"class_type": "IPAdapterAdvanced",
                   "inputs": {"model": ["6", 0], "ipadapter": ["6", 1], "image": ["5", 0],
                              "weight": 0.65, "weight_type": "linear",
                              "combine_embeds": "concat", "start_at": 0.25, "end_at": 1.0,
                              "embeds_scaling": "V only"}}
        model_src = ["7", 0]

    # ── ControlNet 深度圖：四組都有，這是唯一的構圖來源 ──
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
               "inputs": {"model": model_src, "positive": ["20", 0], "negative": ["20", 1],
                          "latent_image": ["4", 0], "seed": SEED, "steps": STEPS,
                          "cfg": CFG, "sampler_name": SAMPLER, "scheduler": SCHED,
                          "denoise": 1.0}}
    return wf


CASES = [
    ("A_只有ControlNet",              False, False),
    ("B_ControlNet＋LoRA",            True,  False),
    ("C_ControlNet＋IPAdapter",       False, True),
    ("D_ControlNet＋IPA＋LoRA",       True,  True),
]


def main():
    C.require_server()
    results = []
    for tag, lora, ipa in CASES:
        print(f"\n▶ {tag}   (LoRA={lora}, IP-Adapter={ipa})")
        t0 = time.time()
        try:
            imgs = C.run(build(tag, lora, ipa), tag=tag, timeout=900)
            dt = time.time() - t0
            if imgs:
                dst = OUT / f"{tag}.png"
                shutil.copy2(imgs[0], dst)
                results.append((tag, dst, dt))
                print(f"   ✅ {dt:.0f} 秒 → {dst.name}")
            else:
                print("   ⚠️ 沒有產出圖片")
        except Exception as e:
            print(f"   ❌ {type(e).__name__}: {str(e)[:160]}")

    if not results:
        return 1
    from PIL import Image, ImageDraw
    ims = [(t, Image.open(p).convert("RGB")) for t, p, _ in results]
    TH = 700
    ims = [(t, i.resize((int(i.width * TH / i.height), TH))) for t, i in ims]
    Wd = sum(i.width for _, i in ims) + 10 * (len(ims) + 1)
    sh = Image.new("RGB", (Wd, TH + 28), (24, 24, 24))
    dr = ImageDraw.Draw(sh); x = 10
    for t, i in ims:
        sh.paste(i, (x, 24)); dr.text((x + 3, 6), t, fill=(255, 220, 120)); x += i.width + 10
    sh.save(OUT / "_ABCD.jpg", quality=92)
    print(f"\n✅ {OUT / '_ABCD.jpg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
