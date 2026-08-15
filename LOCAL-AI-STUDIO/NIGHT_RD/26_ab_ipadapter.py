# -*- coding: utf-8 -*-
"""EXP-06：最小化 A/B —— 把 IP-Adapter 拔掉後，Nova 能不能回來？

A：ControlNet ＋ Nova V2 LoRA 0.45，**完全不掛 IP-Adapter**
B：ControlNet ＋ Nova V2 LoRA 0.35 ＋ IP-Adapter 0.65（目前基準）

除了控制方式，其餘全部固定，**兩組共用同一份 prompt 與 negative 字串**：
起始構圖（深度圖）／seed／解析度／sampler／scheduler／步數／cfg／ControlNet 強度。

刻意不為任何一組調整 prompt —— 要測的是控制方式，不是 prompt 優化。

用法：python 26_ab_ipadapter.py
"""
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼\auto")
sys.stdout.reconfigure(encoding="utf-8")
import comfy_api as C  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "ab_ipadapter"; OUT.mkdir(exist_ok=True)

# ── 固定條件 ────────────────────────────────────────────────
CKPT = "RealVisXL_V5.0_Lightning_fp16.safetensors"
DEPTH = "d9s1_depth_clean.png"
IPA_REF = "duo_full.png"
LORA = "nova_lora_V2_step1500.safetensors"
SEED = 424242
STEPS, CFG = 6, 1.8
SAMPLER, SCHED = "dpmpp_sde", "karras"
W, H = 768, 1152
CN_STRENGTH, CN_END = 0.70, 0.50
IPA_WEIGHT, IPA_START = 0.65, 0.25

# ── 兩組共用的 prompt（一字不改）────────────────────────────
CHAR = ("t4codog and nov4dog, a tiny pure snow-white smooth-coat chihuahua with two "
        "small round black dot markings above its eyes, oversized pointy ears, thin blue "
        "collar with a small round silver tag, and a large fluffy grey and white siberian "
        "husky with pale blue eyes sitting nearby")
SCENE = ("The chihuahua stands in the middle of a large burgundy red wine stain soaked into "
         "a snow-white shag rug, a tipped-over wine glass beside it, its front paws stained "
         "dark red. The husky sits a few feet away watching.")
STYLE = ("photorealistic home video still, floor level, bright modern living room, "
         "light wood floor, grey fabric sofa, warm afternoon window light")
POSITIVE = f"{CHAR}. {SCENE} {STYLE}"
NEGATIVE = ("cartoon, anime, 3d render, three dogs, multiple dogs, extra dog, duplicate dog, "
            "second husky, extra limbs, deformed, human, person, hand, "
            "pomeranian, fox-like dog, klee kai, brown eyes, cream fur, "
            "text on tag, engraved name, text, watermark, blurry, low quality")

CASES = [
    ("A_CN+LoRA0.45_無IPA", 0.45, False),
    ("B_CN+LoRA0.35+IPA",   0.35, True),
]


def build(lora_weight, use_ipa):
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": W, "height": H, "batch_size": 1}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"images": ["9", 0], "filename_prefix": "abipa/x"}},
    }
    m, c = ["1", 0], ["1", 1]
    wf["40"] = {"class_type": "LoraLoader",
                "inputs": {"lora_name": LORA, "strength_model": lora_weight,
                           "strength_clip": lora_weight, "model": m, "clip": c}}
    m, c = ["40", 0], ["40", 1]

    wf["2"] = {"class_type": "CLIPTextEncode", "inputs": {"text": POSITIVE, "clip": c}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": c}}

    if use_ipa:
        wf["5"] = {"class_type": "LoadImage", "inputs": {"image": IPA_REF}}
        wf["6"] = {"class_type": "IPAdapterUnifiedLoader",
                   "inputs": {"model": m, "preset": "PLUS (high strength)"}}
        wf["7"] = {"class_type": "IPAdapterAdvanced",
                   "inputs": {"model": ["6", 0], "ipadapter": ["6", 1], "image": ["5", 0],
                              "weight": IPA_WEIGHT, "weight_type": "linear",
                              "combine_embeds": "concat", "start_at": IPA_START,
                              "end_at": 1.0, "embeds_scaling": "V only"}}
        m = ["7", 0]

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
                          "sampler_name": SAMPLER, "scheduler": SCHED, "denoise": 1.0}}
    return wf


def main():
    (OUT / "prompt_positive.txt").write_text(POSITIVE, encoding="utf-8")
    (OUT / "prompt_negative.txt").write_text(NEGATIVE, encoding="utf-8")

    C.require_server()
    made, times = [], {}
    for tag, lw, ipa in CASES:
        print(f"\n▶ {tag}   LoRA={lw}  IP-Adapter={'ON ' + str(IPA_WEIGHT) if ipa else 'OFF'}")
        t0 = time.time()
        imgs = C.run(build(lw, ipa), tag=tag, timeout=900)
        dt = time.time() - t0
        if imgs:
            p = OUT / f"{tag}.png"
            shutil.copy2(imgs[0], p)
            made.append((tag, p)); times[tag] = dt
            print(f"   ✅ {dt:.0f} 秒 → {p.name}")

    if len(made) < 2:
        return 1

    from PIL import Image, ImageDraw
    # 全圖並排
    TH = 900
    ims = [(t, Image.open(p).convert("RGB")) for t, p in made]
    r = [(t, i.resize((int(i.width * TH / i.height), TH))) for t, i in ims]
    tot = sum(i.width for _, i in r) + 10 * (len(r) + 1)
    s = Image.new("RGB", (tot, TH + 26), (24, 24, 24))
    d = ImageDraw.Draw(s); x = 10
    for t, i in r:
        s.paste(i, (x, 22)); d.text((x + 3, 5), t, fill=(255, 220, 120)); x += i.width + 10
    s.save(OUT / "_AB_FULL.jpg", quality=94)

    # Nova 臉部放大
    for label, box in [("NOVA", (0.50, 0.00, 1.00, 0.32)),
                       ("TACO", (0.18, 0.20, 0.72, 0.62)),
                       ("STAIN", (0.00, 0.45, 1.00, 1.00))]:
        TH2 = 520
        cr = []
        for t, im in ims:
            Wd, Hh = im.size
            c = im.crop((int(box[0] * Wd), int(box[1] * Hh), int(box[2] * Wd), int(box[3] * Hh)))
            cr.append((t, c.resize((int(c.width * TH2 / c.height), TH2))))
        tot = sum(i.width for _, i in cr) + 8 * (len(cr) + 1)
        s = Image.new("RGB", (tot, TH2 + 22), (24, 24, 24))
        d = ImageDraw.Draw(s); x = 8
        for t, i in cr:
            s.paste(i, (x, 18)); d.text((x + 3, 3), f"{label} {t}", fill=(255, 220, 120))
            x += i.width + 8
        s.save(OUT / f"_AB_{label}.jpg", quality=95)

    (OUT / "params.txt").write_text(
        f"""EXP-06 最小化 A/B —— IP-Adapter 是不是 Nova 身份的瓶頸

A 組  ControlNet + Nova V2 LoRA 0.45，無 IP-Adapter   耗時 {times.get(CASES[0][0],0):.0f} 秒
B 組  ControlNet + Nova V2 LoRA 0.35 + IP-Adapter 0.65 耗時 {times.get(CASES[1][0],0):.0f} 秒

固定條件（兩組完全相同）
  底模型          {CKPT}
  LoRA 檔          {LORA}
  ControlNet      xinsir_controlnet_union_sdxl_promax（depth）
  ControlNet 強度  {CN_STRENGTH}  end_percent {CN_END}
  深度圖           {DEPTH}
  IP-Adapter 參考  {IPA_REF}（僅 B 組使用）
  IP-Adapter 權重  {IPA_WEIGHT}  start_at {IPA_START}（僅 B 組）
  seed            {SEED}（固定，非時間戳）
  解析度           {W}x{H}
  sampler         {SAMPLER} / {SCHED}
  steps / cfg     {STEPS} / {CFG}
  positive        見 prompt_positive.txt（兩組一字不差）
  negative        見 prompt_negative.txt（兩組一字不差）
""", encoding="utf-8")
    print(f"\n✅ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
