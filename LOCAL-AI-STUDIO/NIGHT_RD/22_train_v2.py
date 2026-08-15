# -*- coding: utf-8 -*-
"""EXP-02 階段二：訓練 Nova LoRA V2。

跟 V1 的差別（**只改這三項，其餘全部固定**）：
  訓練資料  5 張（全乾淨客廳） → 12 張（乾淨5 / 淹水3 / 麵粉2 / 岩漿2）
  LR        1e-4 → 5e-5      （V1 可用權重區間只有 0.25–0.45 太窄）
  步數      1000 → 1500      （lr 減半要補回來）

另外修掉 V1 的存檔 bug：
V1 用 `convert_state_dict_to_kohya()` 產出的 key 少了 `lora_unet_` 前綴，
測試階段才發現載不進去。這版在源頭就補上，而且**第一個 checkpoint 存完立刻驗證**，
不等 1500 步跑完才發現。

用法：python 22_train_v2.py
"""
import json
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
BASE = r"C:\Users\TUF Gaming\ai-video-local\ComfyUI\models\checkpoints\RealVisXL_V5.0_Lightning_fp16.safetensors"
CACHE = HERE / "cache_nova_v2" / "cache.pt"
OUT = HERE / "out_nova_v2"; OUT.mkdir(exist_ok=True, parents=True)

RANK, ALPHA = 16, 8
LR = 5e-5                 # V1 是 1e-4
MAX_STEPS = 1500          # V1 是 1000
WARMUP, SAVE_EVERY, SEED = 50, 250, 42
TARGETS = ["to_k", "to_q", "to_v", "to_out.0"]
PREFIX = "lora_unet_"


def vram(tag=""):
    a = torch.cuda.memory_allocated() / 1024 ** 3
    r = torch.cuda.max_memory_allocated() / 1024 ** 3
    return f"[VRAM {a:.2f}/峰值 {r:.2f} GB] {tag}"


def save_lora(unet, path):
    """存成 kohya 格式。key 一定要有 lora_unet_ 前綴，ComfyUI 和 diffusers 都靠它辨識。"""
    from diffusers.utils.state_dict_utils import convert_state_dict_to_kohya
    from peft import get_peft_model_state_dict
    from safetensors.torch import save_file
    sd = convert_state_dict_to_kohya(get_peft_model_state_dict(unet))
    fixed = {}
    for k, v in sd.items():
        base, _, suf = k.partition(".")
        key = k if k.startswith(PREFIX) else PREFIX + base + "." + suf
        fixed[key] = v.to(torch.float16)
    save_file(fixed, str(path))
    return len(fixed)


def verify(path):
    """立刻驗證：能不能被讀回、key 是不是 ComfyUI 認得的格式。"""
    from safetensors.torch import load_file
    sd = load_file(str(path))
    n = len(sd)
    bad = [k for k in sd if not k.startswith(PREFIX)]
    nonzero = all(v.abs().sum().item() > 0 for v in sd.values())
    params = sum(v.numel() for v in sd.values())
    ok = (n > 0 and not bad and nonzero)
    print(f"   🔍 驗證：{n} 個張量 / {params:,} 參數 / 全非零={nonzero} / "
          f"前綴錯誤={len(bad)} → {'✅ 通過' if ok else '❌ 失敗'}")
    return ok


def main():
    from diffusers import DDPMScheduler, UNet2DConditionModel
    from peft import LoraConfig

    torch.manual_seed(SEED); random.seed(SEED)
    dev = "cuda"

    recs = torch.load(CACHE, weights_only=False)
    scenes = {}
    for r in recs:
        s = r["name"].split("_")[1]
        scenes[s] = scenes.get(s, 0) + 1
    print(f"訓練樣本 {len(recs)} 筆，場景分布 {scenes}\n")

    print("載入 UNet（fp16，凍結）…")
    unet = UNet2DConditionModel.from_single_file(BASE, subfolder="unet",
                                                 torch_dtype=torch.float16)
    unet.requires_grad_(False)
    unet.to(dev)
    unet.enable_gradient_checkpointing()
    unet.add_adapter(LoraConfig(r=RANK, lora_alpha=ALPHA,
                                init_lora_weights="gaussian", target_modules=TARGETS))
    params = [p for p in unet.parameters() if p.requires_grad]
    for p in params:
        p.data = p.data.float()
    print(f"   可訓練參數 {sum(p.numel() for p in params):,}（rank {RANK} / alpha {ALPHA}）")
    print("  ", vram("就緒"))

    sched = DDPMScheduler.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0", subfolder="scheduler")
    opt = torch.optim.AdamW(params, lr=LR, weight_decay=1e-2)

    print(f"\nLR {LR} / {MAX_STEPS} 步 / 每 {SAVE_EVERY} 步存檔\n" + "─" * 64)
    t0, losses, log, first_verified = time.time(), [], [], False

    for step in range(1, MAX_STEPS + 1):
        for g in opt.param_groups:
            g["lr"] = LR * step / WARMUP if step < WARMUP else LR
        rec = random.choice(recs)

        lat = rec["latent"].unsqueeze(0).to(dev, torch.float16)
        pe = rec["prompt_embeds"].unsqueeze(0).to(dev, torch.float16)
        ppe = rec["pooled"].unsqueeze(0).to(dev, torch.float16)
        h, w = rec["orig_size"]
        add_time = torch.tensor([[h, w, 0, 0, h, w]], device=dev, dtype=torch.float16)

        noise = torch.randn_like(lat)
        t = torch.randint(0, sched.config.num_train_timesteps, (1,), device=dev).long()
        with torch.autocast("cuda", dtype=torch.bfloat16):
            pred = unet(sched.add_noise(lat, noise, t), t, encoder_hidden_states=pe,
                        added_cond_kwargs={"text_embeds": ppe, "time_ids": add_time}).sample
            loss = F.mse_loss(pred.float(), noise.float())
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step(); opt.zero_grad(set_to_none=True)
        losses.append(loss.item())

        if step % 50 == 0 or step == MAX_STEPS:
            avg = sum(losses[-50:]) / len(losses[-50:])
            el = time.time() - t0
            print(f"step {step:>5}/{MAX_STEPS}  avg50 {avg:.4f}  "
                  f"{el/step:.2f}s/步  剩 {(MAX_STEPS-step)*el/step/60:.1f} 分  {vram()}")
            log.append({"step": step, "avg50": avg})

        if step % SAVE_EVERY == 0 or step == MAX_STEPS:
            p = OUT / f"nova_lora_V2_step{step}.safetensors"
            n = save_lora(unet, p)
            print(f"   💾 {p.name}  {n} 張量  {p.stat().st_size/1024/1024:.1f} MB")
            # STEP 6：第一個 checkpoint 存完立刻驗證，不等跑完
            if not first_verified:
                first_verified = True
                if not verify(p):
                    print("   ❌ 第一個 checkpoint 驗證失敗，中止訓練")
                    return 2

    dur = time.time() - t0
    print("─" * 64)
    print(f"✅ {MAX_STEPS} 步完成，{dur/60:.1f} 分（{dur/MAX_STEPS:.2f} 秒/步）")
    (OUT / "train_log.json").write_text(json.dumps({
        "version": "V2", "base": BASE, "rank": RANK, "alpha": ALPHA, "lr": LR,
        "steps": MAX_STEPS, "seed": SEED, "targets": TARGETS,
        "samples": len(recs), "scenes": scenes,
        "minutes": round(dur / 60, 1), "loss_log": log,
        "vs_v1": {"lr": "1e-4 → 5e-5", "steps": "1000 → 1500",
                  "samples": "5 (all clean) → 12 (4 scenes)"},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
