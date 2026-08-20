"""本機 ComfyUI 生**單段 5 秒** 704x1280 影片。

為什麼不接龍：8/9 三次實測，第二段每次都崩（長人手／增生第二隻狗／換品種）。
單段是本機唯一穩定能交付的長度。要更長就每鏡各生一張場景圖分開跑再剪。

用法：python make_video_local_5s.py <scene.jpg> <prompt.txt> <out.mp4>
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import studio_lock  # noqa: E402

scene, prompt_file, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])

# 產線互斥（8/20 加）：這台只有一張顯卡，兩個視窗同時生片只會排隊互踩。
studio_lock.acquire(f"生影片 {out.name}")

# --seed：2026-08-13 加。原本 seed 寫死成 int(stamp) % 900000，也就是每次跑都不一樣，
# 而且不會印出來 —— 生出好結果重現不了，生出壞結果也分不清是 prompt 問題還是 seed 運氣。
# 不給 --seed 就維持原本的時間戳行為，完全向後相容。
SEED = None
if "--seed" in sys.argv:
    SEED = int(sys.argv[sys.argv.index("--seed") + 1])
# --steps：2026-08-14 加。原本寫死 4（Turbo 蒸餾模型的建議值）。
# 2026-08-15 預設改成 8：單變數實驗（_exp_20260814，六種步數）證明 steps 8 對 steps 4
# 是**全面勝出**，沒有任何一項退步 —— 動作幅度 +38%、速度抖動 −7%、光流解釋率 +38%、
# 連角色細節保留率都更好 +9%，代價只有多 30% 的時間（5.0 → 6.5 分鐘）。
# 再往上（10/16/24）動作還會漲，但角色穩定度開始退步，所以 8 是轉折點不是最高分。
# 詳見 LOCAL-AI-STUDIO/PRODUCTION/MODEL_CAPABILITY.md 第六節。
STEPS = 8
if "--steps" in sys.argv:
    STEPS = int(sys.argv[sys.argv.index("--steps") + 1])
# --shift / --length / --sampler / --scheduler：2026-08-14 晚上加，為了跑單變數實驗。
# 這四個原本都寫死在下面的工作流字典裡，改一次要動一次程式碼，等於沒辦法乾淨地
# 「只改一個變數」。全部拉成參數，不給就是原本的值，向後相容。
# ⚠️ length 必須是 4n+1（Wan 的潛在空間時間軸是 4 倍壓縮），給 80 會直接報錯。
SHIFT = 8.0
if "--shift" in sys.argv:
    SHIFT = float(sys.argv[sys.argv.index("--shift") + 1])
LENGTH = 121
if "--length" in sys.argv:
    LENGTH = int(sys.argv[sys.argv.index("--length") + 1])
    if LENGTH % 4 != 1:
        print(f"FAILED: length 必須是 4n+1，{LENGTH} 不合法")
        sys.exit(1)
SAMPLER = "euler"
if "--sampler" in sys.argv:
    SAMPLER = sys.argv[sys.argv.index("--sampler") + 1]
SCHEDULER = "simple"
if "--scheduler" in sys.argv:
    SCHEDULER = sys.argv[sys.argv.index("--scheduler") + 1]
HERE = Path(r"C:\Users\TUF Gaming\ai-video-local")
COMFY = HERE / "ComfyUI"
API = "http://127.0.0.1:8188"

PROMPT = prompt_file.read_text(encoding="utf-8").split("|||")[0].strip()
NEG = ("blurry, low quality, worst quality, cartoon, anime, 3d render, text, letters, words, "
       "captions, watermark, subtitles, deformed, extra limbs, extra legs, mutated, jpeg artifacts, "
       "static image, overexposed, human, person, hand, arm, fingers, smartphone, phone, "
       "two huskies, three dogs, multiple dogs, duplicate dog, extra dog, cloned animal, "
       "second husky, melting face, morphing face, warping, distorted face, changing breed, "
       # 2026-08-11 加：D4 麵粉片在粉堆裡長出一隻「幻覺幼犬」（有鼻子、眼點、四趾爪子），
       # 佔畫面 1/4、持續 7 秒。原本的 "three dogs / extra dog" 擋不住 ——
       # 因為它不是一隻完整的狗，是「材料堆裡浮現出動物的形狀」，要直接點名這件事。
       "animal shape hidden in the pile, face emerging from powder, puppy in the flour, "
       "creature buried in the mess, pareidolia, hidden face, "
       # 粉塵被生成灰褐色像煙，而且從畫面後方升起（跟前景的袋子對不上）
       "smoke, grey dust, dark haze, fog, steam, dust cloud from behind, airborne dust, floating particles, powder in the air, dust plume, haze, mist, atmospheric fog, smoke rising, cloud of dust")


def api(path, data=None, timeout=30):
    req = (urllib.request.Request(API + path, json.dumps(data).encode(),
                                  {"Content-Type": "application/json"})
           if data is not None else urllib.request.Request(API + path))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def comfy_up():
    try:
        api("/system_stats", timeout=5)
        print("ComfyUI 已在跑")
        return None
    except Exception:
        pass
    proc = subprocess.Popen(
        [str(HERE / "venv/Scripts/python.exe"), "main.py", "--listen", "127.0.0.1",
         "--port", "8188", "--disable-auto-launch"],
        cwd=str(COMFY), stdout=open(HERE / "comfyui.log", "w", encoding="utf-8"),
        stderr=subprocess.STDOUT)
    for _ in range(120):
        try:
            api("/system_stats", timeout=5)
            print("ComfyUI 起來了")
            return proc
        except Exception:
            time.sleep(5)
    print("FAILED: ComfyUI 起不來")
    sys.exit(1)


proc = comfy_up()
stamp = str(int(time.time()))[-6:]
s704 = COMFY / "input" / f"s5_{stamp}.png"
ff("-i", str(scene), "-vf",
   "scale=704:1280:force_original_aspect_ratio=increase,crop=704:1280", str(s704))
print("起始圖已備好")

g = {
    "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "wan22_5b_turbo_Q4_K_M.gguf"}},
    "2": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": SHIFT}},
    "3": {"class_type": "CLIPLoader",
          "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                     "type": "wan", "device": "default"}},
    "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": PROMPT}},
    "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": NEG}},
    "6": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
    "12": {"class_type": "LoadImage", "inputs": {"image": s704.name}},
    "7": {"class_type": "Wan22ImageToVideoLatent",
          "inputs": {"vae": ["6", 0], "width": 704, "height": 1280, "length": LENGTH,
                     "batch_size": 1, "start_image": ["12", 0]}},
    "8": {"class_type": "KSampler",
          "inputs": {"model": ["2", 0], "positive": ["4", 0], "negative": ["5", 0],
                     "latent_image": ["7", 0],
                     "seed": SEED if SEED is not None else int(stamp) % 900000, "steps": STEPS,
                     "cfg": 1.0, "sampler_name": SAMPLER, "scheduler": SCHEDULER, "denoise": 1.0}},
    "9": {"class_type": "VAEDecodeTiled",
          "inputs": {"samples": ["8", 0], "vae": ["6", 0], "tile_size": 256, "overlap": 64,
                     "temporal_size": 64, "temporal_overlap": 8}},
    "10": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24.0}},
    "11": {"class_type": "SaveVideo", "inputs": {"video": ["10", 0],
                                                 "filename_prefix": f"s5_{stamp}",
                                                 "format": "mp4", "codec": "h264"}},
}

# 2026-08-14：生成前先叫 ComfyUI 放掉上一輪的模型與快取。VRAM 只有 8.5G，
# 連續跑多支時第二支開始常常卡在換頁上，速度差一倍以上。
try:
    api("/free", {"unload_models": True, "free_memory": True}, timeout=60)
except Exception as e:
    print(f"  （/free 沒成功，不影響生成：{e}）", flush=True)

t0 = time.time()
pid = api("/prompt", {"prompt": g})["prompt_id"]
print(f"  seed = {SEED if SEED is not None else int(stamp) % 900000}"
      f"{'（指定）' if SEED is not None else '（時間戳隨機）'} / steps = {STEPS}"
      f" / shift = {SHIFT} / length = {LENGTH} / {SAMPLER}+{SCHEDULER}", flush=True)
print("已排入佇列，開始算圖…", flush=True)

src = None
while time.time() - t0 < 2400:
    time.sleep(15)
    try:
        hist = api(f"/history/{pid}", timeout=30)
    except Exception:
        continue
    if pid in hist:
        e = hist[pid]
        if e.get("status", {}).get("completed") or e.get("outputs"):
            for node in e.get("outputs", {}).values():
                for key in ("images", "video", "gifs"):
                    for f in node.get(key, []):
                        src = COMFY / "output" / f.get("subfolder", "") / f["filename"]
            break
        if e.get("status", {}).get("status_str") == "error":
            print("FAILED:", json.dumps(e.get("status"))[:400])
            sys.exit(1)

if not src:
    print("FAILED: 逾時")
    sys.exit(1)
print(f"算完了，花了 {(time.time()-t0)/60:.1f} 分鐘")

# 放大到 1080x1920（Shorts 規格）
ff("-i", str(src), "-vf", "scale=1080:1964:flags=lanczos,crop=1080:1920",
   "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(out))
print("saved", out)
if proc:
    proc.terminate()
