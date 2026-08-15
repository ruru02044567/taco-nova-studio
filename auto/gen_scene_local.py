# -*- coding: utf-8 -*-
"""本機生場景圖（寫實版）：IP-Adapter 鎖 Taco & Nova，不再依賴 Gemini 網頁。

為什麼要有這支：
生圖一直走 Gemini 網頁遙控，等於整條產線綁在一個會當、會跳登入、會被排程器
沖掉對話的瀏覽器上。本機生圖沒有額度、不用開瀏覽器、不會被任何人搶。

跟隔壁卡通農場那套的差別（同一套技術，參數完全不同）：
  卡通 → DreamShaperXL（畫風偏藝術），角色是 chibi 小熊
  寫實 → RealVisXL V5 Lightning，角色是真狗，容錯率低很多

用法：
  # 參數掃描（找出這對狗的最佳權重，只需做一次）
  python gen_scene_local.py --sweep

  # 用固定參數生一張
  python gen_scene_local.py --prompt-file clips/d9s1_scene.txt --out clips/x.png
"""
import argparse
import os
import sys

import comfy_api as C

sys.stdout.reconfigure(encoding="utf-8")

CKPT = "RealVisXL_V5.0_Lightning_fp16.safetensors"
REF_DUO = "duo_full.png"        # 放進 ComfyUI/input 的方形參考圖

# Lightning 模型：步數少、cfg 低。cfg 太高會燒圖，太低則不聽提示詞。
# 官方建議 4~6 步 / cfg 1.0~2.0，這裡取中間值再由 --steps/--cfg 覆寫。
STEPS, CFG = 6, 1.8
SAMPLER, SCHED = "dpmpp_sde", "karras"
W, H = 768, 1152                 # 直式 2:3，之後裁成 9:16

CHAR = (
    "a tiny pure snow-white smooth-coat chihuahua with two small round black dot "
    "markings above its eyes like little eyebrows, oversized pointy ears, wearing a "
    "thin blue collar with a small round silver tag, and a large fluffy grey and white "
    "siberian husky with pale blue eyes sitting nearby"
)

STYLE = (
    "photorealistic home video still, shot on a smartphone at floor level, "
    "eye-level pet photography, bright modern living room, light wood floor, "
    "grey fabric sofa, green potted plants, warm afternoon window light, "
    "shallow depth of field, natural colors, slight lens grain"
)

NEG = (
    "cartoon, anime, illustration, 3d render, painting, cgi, plastic, toy, "
    "three dogs, multiple dogs, extra dog, duplicate dog, second husky, second chihuahua, "
    "extra limbs, extra legs, deformed, mutated, fused animals, "
    "human, person, hand, arm, fingers, smartphone, phone, camera, "
    "text, watermark, signature, logo, blurry, low quality, worst quality"
)


def build(prompt, seed, ip_weight, ip_start, tag, ckpt=CKPT,
          steps=STEPS, cfg=CFG, width=W, height=H, ip_type="linear", ref=REF_DUO,
          donor=None, cn_strength=0.75, cn_end=0.85, depth=None):
    """IP-Adapter 鎖角色 ＋（可選）ControlNet 深度圖鎖構圖。

    2026-08-11 三輪實測的結論，決定了為什麼一定要有 donor 這條路：
      第 1 輪（雙狗參考圖、cfg 1.8）→ 角色穩，但哈士奇完全沒出現、紅酒漬變成一杯酒
      第 2 輪（cfg 拉到 2.5/3.5）→ 第二隻狗出現了，但是小型犬不是哈士奇，
                                    而且吉娃娃的純白被染成棕白
      第 3 輪（只鎖 Taco 的參考圖）→ 哈士奇還是生不出來
    也就是說：**IP-Adapter 管得住「這隻狗長什麼樣」，管不住「畫面該有幾隻狗、誰站哪」。**
    構圖只能用 ControlNet 當成圖像硬塞進去（隔壁卡通農場同一個坑、同一個解法）。

    donor：拿一張構圖正確的圖（例如以前 Gemini 生的場景圖）抽深度圖當模板。
    """
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "5": {"class_type": "LoadImage", "inputs": {"image": ref}},
        "6": {"class_type": "IPAdapterUnifiedLoader",
              "inputs": {"model": ["1", 0], "preset": "PLUS (high strength)"}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": f"{CHAR}. {prompt} {STYLE}", "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["1", 1]}},
        # weight_type 只用 linear —— 隔壁實測 style transfer 系列在低 cfg 下會把整張燒掉
        "7": {"class_type": "IPAdapterAdvanced",
              "inputs": {"model": ["6", 0], "ipadapter": ["6", 1], "image": ["5", 0],
                         "weight": ip_weight, "weight_type": ip_type,
                         "combine_embeds": "concat", "start_at": ip_start, "end_at": 1.0,
                         "embeds_scaling": "V only"}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"images": ["9", 0], "filename_prefix": f"pet/{tag}"}},
    }

    pos, neg = ["2", 0], ["3", 0]

    # depth：吃 make_depth.py 事先抽好的深度圖。
    # 不要在同一個 workflow 裡現抽 —— DA3 ＋ SDXL ＋ IP-Adapter ＋ ControlNet
    # 一起載，這台 16GB 的機器會直接 Fatal Python error 把 ComfyUI 幹掉（8/11 實測）。
    if depth:
        wf["13"] = {"class_type": "LoadImage", "inputs": {"image": depth}}
        wf["16"] = {"class_type": "ControlNetLoader",
                    "inputs": {"control_net_name":
                               "xinsir_controlnet_union_sdxl_promax.safetensors"}}
        wf["17"] = {"class_type": "SetUnionControlNetType",
                    "inputs": {"control_net": ["16", 0], "type": "depth"}}
        wf["20"] = {"class_type": "ControlNetApplyAdvanced",
                    "inputs": {"positive": ["2", 0], "negative": ["3", 0],
                               "control_net": ["17", 0], "image": ["13", 0],
                               "strength": cn_strength, "start_percent": 0.0,
                               "end_percent": cn_end, "vae": ["1", 2]}}
        pos, neg = ["20", 0], ["20", 1]
    elif donor:
        wf["30"] = {"class_type": "LoadImage", "inputs": {"image": donor}}
        wf["31"] = {"class_type": "ImageScale",
                    "inputs": {"image": ["30", 0], "width": width, "height": height,
                               "upscale_method": "lanczos", "crop": "center"}}
        wf["11"] = {"class_type": "LoadDA3Model",
                    "inputs": {"model_name": "depth_anything_3_base.safetensors",
                               "weight_dtype": "fp16"}}
        wf["12"] = {"class_type": "DA3Inference",
                    "inputs": {"da3_model": ["11", 0], "image": ["31", 0],
                               "resolution": 504, "resize_method": "upper_bound_resize",
                               "mode": "mono"}}
        wf["13"] = {"class_type": "DA3Render",
                    "inputs": {"da3_geometry": ["12", 0], "output": "depth",
                               "output.normalization": "v2_style",
                               "output.apply_sky_clip": False}}
        wf["14"] = {"class_type": "SaveImage",
                    "inputs": {"images": ["13", 0], "filename_prefix": f"pet/{tag}_depth"}}
        wf["16"] = {"class_type": "ControlNetLoader",
                    "inputs": {"control_net_name":
                               "xinsir_controlnet_union_sdxl_promax.safetensors"}}
        wf["17"] = {"class_type": "SetUnionControlNetType",
                    "inputs": {"control_net": ["16", 0], "type": "depth"}}
        wf["20"] = {"class_type": "ControlNetApplyAdvanced",
                    "inputs": {"positive": ["2", 0], "negative": ["3", 0],
                               "control_net": ["17", 0], "image": ["13", 0],
                               "strength": cn_strength, "start_percent": 0.0,
                               "end_percent": cn_end, "vae": ["1", 2]}}
        pos, neg = ["20", 0], ["20", 1]

    wf["8"] = {"class_type": "KSampler",
               "inputs": {"model": ["7", 0], "positive": pos, "negative": neg,
                          "latent_image": ["4", 0], "seed": seed, "steps": steps,
                          "cfg": cfg, "sampler_name": SAMPLER, "scheduler": SCHED,
                          "denoise": 1.0}}
    return wf


SWEEP_PROMPT = (
    "The chihuahua stands in the middle of a large burgundy red wine stain soaked into "
    "a snow-white shag rug, a tipped-over wine glass beside it, its front paws stained "
    "dark red, looking at the camera with a guilty caught-in-the-act expression. "
    "The husky sits a few feet away watching with a flat unimpressed stare."
)


def sweep(args):
    """固定 seed，掃 IP-Adapter 權重 × start_at。同一顆 seed 才比得出參數的影響。"""
    combos = [(w, s) for w in (0.55, 0.70, 0.85) for s in (0.0, 0.20)]
    print(f"共 {len(combos)} 組，固定 seed={args.seed}")
    made = []
    for i, (w, s) in enumerate(combos, 1):
        tag = f"sweep_w{int(w * 100):03d}_s{int(s * 100):02d}"
        print(f"[{i}/{len(combos)}] weight={w} start_at={s}", flush=True)
        wf = build(SWEEP_PROMPT, args.seed, w, s, tag,
                   ckpt=args.ckpt, steps=args.steps, cfg=args.cfg)
        imgs = C.run(wf, tag=tag)
        if imgs:
            made.append((f"w={w} start={s}", imgs[0]))
            print(f"      -> {os.path.basename(imgs[0])}")
        else:
            print("      -> 失敗")
    print(f"\n完成 {len(made)}/{len(combos)} 張")
    for label, p in made:
        print(f"  {label:<22} {p}")
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true", help="跑參數掃描")
    ap.add_argument("--prompt-file", help="場景描述檔")
    ap.add_argument("--prompt", help="直接給場景描述")
    ap.add_argument("--out", help="輸出檔路徑（複製一份過去）")
    ap.add_argument("--seed", type=int, default=777001)
    ap.add_argument("--ip-weight", type=float, default=0.70)
    ap.add_argument("--ip-start", type=float, default=0.0)
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--cfg", type=float, default=CFG)
    ap.add_argument("--tag", default="scene")
    ap.add_argument("--donor", help="構圖模板圖（放在 ComfyUI/input），現場抽深度圖給 ControlNet。記憶體吃緊時改用 --depth")
    ap.add_argument("--depth", help="make_depth.py 事先抽好的深度圖檔名（省下 DA3 的記憶體）")
    ap.add_argument("--cn-strength", type=float, default=0.75)
    ap.add_argument("--cn-end", type=float, default=0.85,
                    help="ControlNet 管到第幾成步數就放手。深度圖是灰白的，管太久連顏色都會被帶成灰白（實測紅酒漬變白泡沫），調低讓後半段自由上色")
    ap.add_argument("--ref", default=REF_DUO,
                    help="IP-Adapter 參考圖。雙狗圖會讓模型把兩隻的特徵混成一團"
                         "（實測：哈士奇會變成小型犬、吉娃娃會被染成棕白），"
                         "要生兩隻狗的畫面就改用 taco_face.png 只鎖吉娃娃")
    ap.add_argument("--ckpt", default=CKPT,
                    help="換底模型。RealVisXL 還在下載時，可以先用現有的 checkpoint "
                         "把整條管線測通（畫風會不對，那是預期的，只驗流程）")
    args = ap.parse_args()

    C.require_server()

    ckpt_path = os.path.join(C.COMFY_ROOT, "models", "checkpoints", args.ckpt)
    if not C.is_complete_safetensors(ckpt_path):
        print(f"[X] checkpoint 還沒下載完或壞了：{args.ckpt}")
        sys.exit(2)

    if args.sweep:
        sweep(args)
        return

    text = args.prompt
    if args.prompt_file:
        text = open(args.prompt_file, encoding="utf-8").read().split("|||")[0].strip()
    if not text:
        print("[X] 要給 --prompt 或 --prompt-file")
        sys.exit(1)

    wf = build(text, args.seed, args.ip_weight, args.ip_start, args.tag,
               ckpt=args.ckpt, steps=args.steps, cfg=args.cfg, ref=args.ref,
               donor=args.donor, cn_strength=args.cn_strength,
               cn_end=args.cn_end, depth=args.depth)
    imgs = C.run(wf, tag=args.tag)
    if not imgs:
        print("[X] 生成失敗")
        sys.exit(3)
    print("saved", imgs[0])
    if args.out:
        import shutil
        shutil.copy(imgs[0], args.out)
        print("copied ->", args.out)


if __name__ == "__main__":
    main()
