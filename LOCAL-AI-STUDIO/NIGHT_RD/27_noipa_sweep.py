# -*- coding: utf-8 -*-
"""EXP-07：無 IP-Adapter 的權重掃描 —— 把 EXP-06 的變數污染拆開

EXP-06（26_ab_ipadapter.py）同時動了兩個變數：
    A = LoRA 0.45 + 無 IPA
    B = LoRA 0.35 + 有 IPA
所以「A 的紅酒漬幾乎消失」無法歸因 —— 可能是拿掉 IPA，也可能只是 0.45 太高
（EXP-03 已證實 V2 在 0.45 本來就會把酒漬抹成細線）。

本實驗把 IP-Adapter 當成唯一新變數：
    其餘條件與 23_sweep_v2.py **一字不差**（同底模、同深度圖、同 seed、
    同 sampler/steps/cfg、同 ControlNet、同 positive、同 negative、同權重階梯），
    只把 IPAdapter 節點整組拿掉。

跑完可與 sweep_V2/ 逐權重並排 → 同一格的差異就只剩 IP-Adapter。

用法：python 27_noipa_sweep.py
"""
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\TUF Gaming\Desktop\我的專案\財富密碼\auto")
sys.stdout.reconfigure(encoding="utf-8")
import comfy_api as C  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "noipa_sweep"; OUT.mkdir(exist_ok=True)
REF_SWEEP = HERE / "sweep_V2"          # 有 IPA 的對照組（EXP-03 產出）

# ── 以下常數與 23_sweep_v2.py 完全相同 ─────────────────────────
CKPT = "RealVisXL_V5.0_Lightning_fp16.safetensors"
DEPTH = "d9s1_depth_clean.png"
LORA = "nova_lora_V2_step1500.safetensors"
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


def build(weight):
    """與 23_sweep_v2.build() 相同，唯獨不建立 IPAdapter 節點（5/6/7）。"""
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": W, "height": H, "batch_size": 1}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"images": ["9", 0], "filename_prefix": "noipa/x"}},
    }
    model_src, clip_src = ["1", 0], ["1", 1]
    if weight > 0:
        wf["40"] = {"class_type": "LoraLoader",
                    "inputs": {"lora_name": LORA, "strength_model": weight,
                               "strength_clip": weight, "model": model_src, "clip": clip_src}}
        model_src, clip_src = ["40", 0], ["40", 1]

    wf["2"] = {"class_type": "CLIPTextEncode",
               "inputs": {"text": f"{CHAR}. {SCENE} {STYLE}", "clip": clip_src}}
    wf["3"] = {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": clip_src}}

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
                          "latent_image": ["4", 0], "seed": SEED, "steps": STEPS, "cfg": CFG,
                          "sampler_name": "dpmpp_sde", "scheduler": "karras", "denoise": 1.0}}
    return wf


def row(pairs, label_prefix, thumb_h, box=None):
    """把 (標籤, PIL.Image) 排成一列，可選裁切區。回傳 PIL.Image。"""
    from PIL import Image, ImageDraw
    cells = []
    for lbl, im in pairs:
        c = im
        if box:
            Wd, Hh = im.size
            c = im.crop((int(box[0] * Wd), int(box[1] * Hh),
                         int(box[2] * Wd), int(box[3] * Hh)))
        cells.append((lbl, c.resize((int(c.width * thumb_h / c.height), thumb_h))))
    tot = sum(i.width for _, i in cells) + 8 * (len(cells) + 1)
    sh = Image.new("RGB", (tot, thumb_h + 22), (24, 24, 24))
    dr = ImageDraw.Draw(sh); x = 8
    for lbl, i in cells:
        sh.paste(i, (x, 18))
        dr.text((x + 3, 3), f"{label_prefix}{lbl}", fill=(255, 220, 120))
        x += i.width + 8
    return sh


def stack(rows, gap=6):
    from PIL import Image
    Wd = max(r.width for r in rows)
    Hh = sum(r.height for r in rows) + gap * (len(rows) - 1)
    sh = Image.new("RGB", (Wd, Hh), (24, 24, 24))
    y = 0
    for r in rows:
        sh.paste(r, (0, y)); y += r.height + gap
    return sh


def main():
    C.require_server()
    made, times = [], {}
    for w in WEIGHTS:
        tag = f"noipa_w{w:.2f}"
        print(f"\n▶ LoRA {w:.2f}  IP-Adapter=OFF")
        t0 = time.time()
        try:
            imgs = C.run(build(w), tag=tag, timeout=600)
            if imgs:
                p = OUT / f"w{w:.2f}.png"
                shutil.copy2(imgs[0], p)
                made.append((w, p)); times[w] = time.time() - t0
                print(f"   ✅ {times[w]:.0f}s → {p.name}")
        except Exception as e:
            print(f"   ❌ {type(e).__name__}: {str(e)[:140]}")

    if not made:
        print("一張都沒生出來")
        return 1

    from PIL import Image
    noipa = [(f"{w:.2f}", Image.open(p).convert("RGB")) for w, p in made]
    withipa = []
    for w, _ in made:
        q = REF_SWEEP / f"w{w:.2f}.png"
        if q.exists():
            withipa.append((f"{w:.2f}", Image.open(q).convert("RGB")))

    # 三組對照圖：全圖 / Nova 臉 / 酒漬區。上排有 IPA、下排無 IPA。
    views = [("FULL", None, 560), ("NOVA", (0.50, 0.00, 1.00, 0.32), 420),
             ("STAIN", (0.00, 0.45, 1.00, 1.00), 420)]
    for name, box, th in views:
        rows = []
        if len(withipa) == len(noipa):
            rows.append(row(withipa, "有IPA w", th, box))
        rows.append(row(noipa, "無IPA w", th, box))
        stack(rows).save(OUT / f"_CMP_{name}.jpg", quality=94)

    (OUT / "params.txt").write_text(
        f"""EXP-07 無 IP-Adapter 權重掃描（拆開 EXP-06 的變數污染）

唯一變數：IP-Adapter 有 / 無
對照組：sweep_V2/（同權重、有 IPA 0.65、EXP-03 產出）

固定條件
  底模型        {CKPT}
  LoRA          {LORA}（權重 {WEIGHTS}）
  ControlNet    xinsir union promax（depth）強度 {CN_STRENGTH} end {CN_END}
  深度圖         {DEPTH}
  seed          {SEED}（固定，非時間戳）
  解析度         {W}x{H}
  sampler       dpmpp_sde / karras   steps {STEPS}  cfg {CFG}
  positive / negative  與 23_sweep_v2.py 完全相同

耗時：{', '.join(f'{w:.2f}={t:.0f}s' for w, t in times.items())}
""", encoding="utf-8")
    print(f"\n✅ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
