# -*- coding: utf-8 -*-
r"""NAG A/B — 驗證掛上 NAGuidance 之後負面提示詞是不是真的被計算了。

## 為什麼要跑這個

`ComfyUI\comfy\samplers.py:610`：cfg 接近 1.0 時 `uncond_ = None`，
整條負面分支被跳過。而 `make_video_local_5s.py` 的 KSampler 正是 `cfg: 1.0`。
所以產線那一長串 `two huskies / extra limbs / extra dog` 從來沒生效過。

`comfy_extras\nodes_nag.py` 的 `NAGuidance` 第 85 行呼叫
`disable_model_cfg1_optimization()`，把那條分支強制算回來。

## 實驗設計

同一張起始圖、同一顆 seed、其餘參數完全相同，只換負面詞。
兩組負面詞的意思完全相反，所以「有沒有差」就等於「負面詞有沒有被計算」。

    對照組（不掛 NAG）：預期兩版逐像素完全相同（最大差 0）
    實驗組（掛 NAG）  ：若有差，代表 NAG 確實把負面分支算回來了

為了省時間用短片段（LENGTH=25，約 1 秒）。驗的是「有沒有被計算」，
不是畫面品質，短片段足夠而且每次只要 1 分多鐘。

用法：python _nag_ab.py [起始圖.png]
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "http://127.0.0.1:8188"
HERE = Path(__file__).resolve().parent
COMFY = Path(r"C:\Users\TUF Gaming\ai-video-local\ComfyUI")

SEED = 909090
# --cfg：對照用。cfg=1.0 走 samplers.py:610 的捷徑（負面分支被跳過），
# 提高到 >1 就不會走捷徑。用來驗證「沒差異」是真的沒生效，不是實驗設計寫錯。
CFG = 1.0
if "--cfg" in sys.argv:
    CFG = float(sys.argv[sys.argv.index("--cfg") + 1])
STEPS = 8
SHIFT = 8.0
LENGTH = 25          # 約 1 秒（正式產線是 121）
if "--length" in sys.argv:
    LENGTH = int(sys.argv[sys.argv.index("--length") + 1])
SKIP_NAG = "--skip-nag" in sys.argv   # 只跑對照組，省一半時間
WIDTH, HEIGHT = 704, 1280
SAMPLER, SCHEDULER = "euler", "simple"
FPS = 24

PROMPT = ("A tiny snow-white chihuahua with two small black round dots above his eyes stands "
          "in a bright living room, a big husky asleep on the floor behind him. "
          "The chihuahua turns his head and blinks.")

# 兩組意思完全相反的負面詞
NEG_BAD = ("deformed, extra limbs, extra legs, two huskies, three dogs, duplicate dog, "
           "blurry, low quality, worst quality, mutated, distorted face")
NEG_GOOD = ("beautiful, masterpiece, perfect anatomy, sharp focus, high quality, "
            "award winning, flawless, cinematic lighting, detailed fur")


def api(path, data=None, timeout=30):
    req = (urllib.request.Request(API + path, json.dumps(data).encode(),
                                  {"Content-Type": "application/json"})
           if data is not None else urllib.request.Request(API + path))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def build(image_name, neg, use_nag, tag):
    """組 workflow。use_nag=True 就在 ModelSampling 和 KSampler 之間插 NAGuidance。"""
    wf = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "wan22_5b_turbo_Q4_K_M.gguf"}},
        "2": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": SHIFT}},
        "3": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": PROMPT}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": neg}},
        "6": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
        "12": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "7": {"class_type": "Wan22ImageToVideoLatent",
              "inputs": {"vae": ["6", 0], "start_image": ["12", 0],
                         "width": WIDTH, "height": HEIGHT, "length": LENGTH, "batch_size": 1}},
        "8": {"class_type": "KSampler",
              "inputs": {"model": ["2", 0], "positive": ["4", 0], "negative": ["5", 0],
                         "latent_image": ["7", 0], "seed": SEED, "steps": STEPS,
                         "cfg": CFG, "sampler_name": SAMPLER, "scheduler": SCHEDULER,
                         "denoise": 1.0}},
        "9": {"class_type": "VAEDecodeTiled",
              "inputs": {"samples": ["8", 0], "vae": ["6", 0],
                         "tile_size": 256, "overlap": 64, "temporal_size": 12, "temporal_overlap": 4}},
        "10": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": float(FPS)}},
        "11": {"class_type": "SaveVideo",
               "inputs": {"video": ["10", 0], "filename_prefix": f"nagab_{tag}_cfg{CFG:g}_L{LENGTH}",
                          "format": "mp4", "codec": "h264"}},
    }
    if use_nag:
        wf["20"] = {"class_type": "NAGuidance",
                    "inputs": {"model": ["2", 0], "nag_scale": 5.0,
                               "nag_alpha": 0.5, "nag_tau": 1.5}}
        wf["8"]["inputs"]["model"] = ["20", 0]
    return wf


def run(wf, tag):
    t0 = time.time()
    pid = api("/prompt", {"prompt": wf})["prompt_id"]
    print(f"  [{tag}] 送出 {pid[:8]}…", flush=True)
    while True:
        time.sleep(4)
        h = api(f"/history/{pid}", timeout=20)
        if pid in h:
            break
        if time.time() - t0 > 900:
            print(f"  [{tag}] 超過 15 分鐘沒回，放棄")
            return None
    outs = h[pid].get("outputs", {})
    for node in outs.values():
        for key in ("video", "videos", "images", "gifs"):
            for item in node.get(key, []) or []:
                p = COMFY / item.get("type", "output") / (item.get("subfolder") or "") / item["filename"]
                if p.is_file():
                    print(f"  [{tag}] 完成，{time.time()-t0:.0f} 秒 → {p.name}")
                    return p
    print(f"  [{tag}] 跑完但抓不到輸出檔：{json.dumps(outs)[:200]}")
    return None


def diff(a, b, label):
    """用 ffmpeg 逐幀比對兩支影片，回傳最大與平均差。"""
    if not a or not b:
        print(f"{label}：缺檔，無法比對")
        return
    cmd = ["ffmpeg", "-v", "error", "-i", str(a), "-i", str(b),
           "-filter_complex", "[0:v][1:v]blend=all_mode=difference,signalstats,"
                              "metadata=print:key=lavfi.signalstats.YMAX",
           "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    vals = []
    for line in (r.stderr + r.stdout).splitlines():
        if "YMAX" in line:
            try:
                vals.append(float(line.split("=")[-1].strip()))
            except ValueError:
                pass
    if not vals:
        print(f"{label}：ffmpeg 沒吐出比對值")
        print("  stderr:", (r.stderr or "")[:200])
        return
    mx, avg = max(vals), sum(vals) / len(vals)
    verdict = "完全相同 → 負面詞沒被計算" if mx == 0 else "有差異 → 負面詞有被計算"
    print(f"{label}：最大差 {mx:.1f}　平均 {avg:.2f}　（{len(vals)} 幀）　{verdict}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    img = args[0] if args else "d13s1_scene.jpg"
    print(f"起始圖：{img}　seed={SEED}　length={LENGTH}　cfg=1.0\n")

    print("【對照組】不掛 NAG（預期：兩版完全相同）")
    a1 = run(build(img, NEG_BAD, False, "off_bad"), "off_bad")
    a2 = run(build(img, NEG_GOOD, False, "off_good"), "off_good")
    b1 = b2 = None
    if not SKIP_NAG:
        print()
        print("【實驗組】掛 NAG（若有差＝負面分支被算回來了）")
        b1 = run(build(img, NEG_BAD, True, "on_bad"), "on_bad")
        b2 = run(build(img, NEG_GOOD, True, "on_good"), "on_good")

    print("\n" + "=" * 60)
    diff(a1, a2, "不掛 NAG")
    diff(b1, b2, "掛 NAG  ")
