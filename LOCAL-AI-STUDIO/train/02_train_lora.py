# -*- coding: utf-8 -*-
"""第二階段：只載入 UNet，用快取好的潛在向量訓練 LoRA。

用法：
  python 02_train_lora.py                # 正式訓練
  python 02_train_lora.py --smoke        # 只跑 5 步，驗證管線不會炸

輸出：`out_nova/nova_lora_V1_step{N}.safetensors`（kohya 格式，ComfyUI 可直接載入）
"""
import argparse
import gc
import json
import math
import random
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
BASE = r"C:\Users\TUF Gaming\ai-video-local\ComfyUI\models\checkpoints\RealVisXL_V5.0_Lightning_fp16.safetensors"
import argparse as _a
_p = _a.ArgumentParser(add_help=False)
_p.add_argument("--who", default="nova", choices=["nova", "taco"])
WHO = _p.parse_known_args()[0].who
CACHE = HERE / f"cache_{WHO}" / "cache.pt"
OUT = HERE / f"out_{WHO}"
OUT.mkdir(exist_ok=True, parents=True)

RANK = 16
ALPHA = 8
LR = 1e-4
MAX_STEPS = 1000
WARMUP = 50
SAVE_EVERY = 250
SEED = 42
# 只掛在注意力層的四個投影上。這是角色 LoRA 的標準做法——
# 角色「長什麼樣」是被注意力層記住的，掛整個 UNet 只會讓檔案變大、更容易過擬合。
TARGETS = ["to_k", "to_q", "to_v", "to_out.0"]


def vram(tag=""):
    if torch.cuda.is_available():
        a = torch.cuda.memory_allocated() / 1024 ** 3
        r = torch.cuda.max_memory_allocated() / 1024 ** 3
        return f"[VRAM {a:.2f}/峰值 {r:.2f} GB] {tag}"
    return tag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="只跑 5 步驗證管線")
    ap.add_argument("--who", default="nova")
    args = ap.parse_args()

    from diffusers import DDPMScheduler, UNet2DConditionModel
    from diffusers.loaders.peft import _SET_ADAPTER_SCALE_FN_MAPPING  # noqa: F401
    from diffusers.utils.state_dict_utils import convert_state_dict_to_kohya
    from peft import LoraConfig, get_peft_model_state_dict

    steps_total = 5 if args.smoke else MAX_STEPS
    torch.manual_seed(SEED); random.seed(SEED)
    dev = "cuda"

    print(f"載入快取 {CACHE}")
    recs = torch.load(CACHE, weights_only=False)
    print(f"   {len(recs)} 筆訓練樣本\n")

    print("載入 UNet（fp16，凍結）…")
    unet = UNet2DConditionModel.from_single_file(
        BASE, subfolder="unet", torch_dtype=torch.float16,
    )
    unet.requires_grad_(False)
    unet.to(dev)
    unet.enable_gradient_checkpointing()
    print("  ", vram("UNet 就緒"))

    unet.add_adapter(LoraConfig(
        r=RANK, lora_alpha=ALPHA, init_lora_weights="gaussian", target_modules=TARGETS,
    ))
    params = [p for p in unet.parameters() if p.requires_grad]
    for p in params:
        p.data = p.data.float()
    n = sum(p.numel() for p in params)
    print(f"   LoRA 可訓練參數 {n:,}（rank {RANK} / alpha {ALPHA}）")
    print("  ", vram("LoRA 掛載後"))

    sched = DDPMScheduler.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0", subfolder="scheduler")
    opt = torch.optim.AdamW(params, lr=LR, weight_decay=1e-2)

    def lr_at(s):
        if s < WARMUP:
            return LR * s / max(1, WARMUP)
        return LR

    print(f"\n開始訓練：{steps_total} 步，每 {SAVE_EVERY} 步存一次\n" + "─" * 62)
    t0 = time.time()
    losses = []
    log = []

    for step in range(1, steps_total + 1):
        for g in opt.param_groups:
            g["lr"] = lr_at(step)
        rec = recs[(step - 1) % len(recs)] if args.smoke else random.choice(recs)

        lat = rec["latent"].unsqueeze(0).to(dev, torch.float16)
        pe = rec["prompt_embeds"].unsqueeze(0).to(dev, torch.float16)
        ppe = rec["pooled"].unsqueeze(0).to(dev, torch.float16)
        h, w = rec["orig_size"]
        add_time = torch.tensor([[h, w, 0, 0, h, w]], device=dev, dtype=torch.float16)

        noise = torch.randn_like(lat)
        t = torch.randint(0, sched.config.num_train_timesteps, (1,), device=dev).long()
        noisy = sched.add_noise(lat, noise, t)

        with torch.autocast("cuda", dtype=torch.bfloat16):
            pred = unet(
                noisy, t, encoder_hidden_states=pe,
                added_cond_kwargs={"text_embeds": ppe, "time_ids": add_time},
            ).sample
            loss = F.mse_loss(pred.float(), noise.float())

        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
        opt.zero_grad(set_to_none=True)

        losses.append(loss.item())
        if step % 25 == 0 or step <= 5 or step == steps_total:
            avg = sum(losses[-25:]) / len(losses[-25:])
            el = time.time() - t0
            sps = el / step
            eta = (steps_total - step) * sps
            print(f"step {step:>5}/{steps_total}  loss {loss.item():.4f}  "
                  f"avg25 {avg:.4f}  {sps:.2f}s/步  剩 {eta/60:.1f} 分  "
                  f"{vram()}")
            log.append({"step": step, "loss": loss.item(), "avg25": avg})

        if not args.smoke and (step % SAVE_EVERY == 0 or step == steps_total):
            sd = convert_state_dict_to_kohya(get_peft_model_state_dict(unet))
            from safetensors.torch import save_file
            p = OUT / f"{WHO}_lora_V1_step{step}.safetensors"
            save_file({k: v.to(torch.float16) for k, v in sd.items()}, str(p))
            print(f"   💾 存檔 {p.name}  ({p.stat().st_size/1024/1024:.1f} MB)")

    dur = time.time() - t0
    print("─" * 62)
    print(f"✅ 完成 {steps_total} 步，耗時 {dur/60:.1f} 分（{dur/steps_total:.2f} 秒/步）")
    print("  ", vram("結束"))
    if not args.smoke:
        (OUT / "train_log.json").write_text(json.dumps({
            "base": BASE, "rank": RANK, "alpha": ALPHA, "lr": LR,
            "steps": steps_total, "seed": SEED, "targets": TARGETS,
            "samples": len(recs), "trainable_params": n,
            "minutes": round(dur / 60, 1), "loss_log": log,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
