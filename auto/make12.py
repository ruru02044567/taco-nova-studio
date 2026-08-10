# -*- coding: utf-8 -*-
"""四鏡 12 秒：4 張同房間場景圖 → 4 支 3 秒單段影片 → 串接 → 配 Sonniss 真實音效。

跟 make15.py 的差別：
1. 每鏡 3 秒（73 格，Wan 要求 4n+1）而不是 5 秒 121 格 → 單鏡約 3 分鐘
2. 場景圖全部用 q1 當母版由 make_scene_ref.py 改圖生成 → 四鏡同一個房間
3. 混音目標 loudnorm I=-11（上一支 15 秒用 -14 實測 mean -17.8dB 太小聲，
   對標 D2S1 巧克力那支的 -10.4dB 聽感）

用法：python make12.py
進度：寫進 make12.status.txt
輸出：..\待審核\d3s1-12秒-淹水.mp4
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent

# 預設跑淹水那支（已驗證過的組合）。要跑別的題材就給三個參數：
#   python make12.py clips12w w d9s1-紅酒-四鏡
# 分別是：素材資料夾、鏡頭檔名前綴（會找 <前綴>1_scene.jpg…）、輸出檔名（不含副檔名）
CLIPS = HERE / (sys.argv[1] if len(sys.argv) > 1 else "clips12")
PREFIX = sys.argv[2] if len(sys.argv) > 2 else "q"
OUT_NAME = sys.argv[3] if len(sys.argv) > 3 else "d3s1-12秒-淹水"

REVIEW = HERE.parent / "待審核"
REVIEW.mkdir(parents=True, exist_ok=True)
STATUS = HERE / f"make12.{PREFIX}.status.txt"

LOCAL = Path(r"C:\Users\TUF Gaming\ai-video-local")
COMFY = LOCAL / "ComfyUI"
API = "http://127.0.0.1:8188"
SFX = HERE.parent / "sfx" / "lib"

SHOTS = [f"{PREFIX}{i}" for i in (1, 2, 3, 4)]
FRAMES = 73                     # 3.04 秒（4n+1）
SHOT_SEC = FRAMES / 24.0
NEG = ("blurry, low quality, worst quality, cartoon, anime, 3d render, text, letters, words, "
       "captions, watermark, subtitles, deformed, extra limbs, extra legs, mutated, jpeg artifacts, "
       "static image, overexposed, human, person, hand, arm, fingers, smartphone, phone, "
       "two huskies, three dogs, multiple dogs, duplicate dog, extra dog, cloned animal, "
       "second husky, melting face, morphing face, warping, distorted face, changing breed")


def note(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(STATUS, "a", encoding="utf-8") as f:
        f.write(line + "\n")


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
        note("ComfyUI 已在跑")
        return None
    except Exception:
        pass
    proc = subprocess.Popen(
        [str(LOCAL / "venv/Scripts/python.exe"), "main.py", "--listen", "127.0.0.1",
         "--port", "8188", "--disable-auto-launch"],
        cwd=str(COMFY), stdout=open(LOCAL / "comfyui.log", "w", encoding="utf-8"),
        stderr=subprocess.STDOUT)
    for _ in range(120):
        try:
            api("/system_stats", timeout=5)
            note("ComfyUI 起來了")
            return proc
        except Exception:
            time.sleep(5)
    note("FATAL: ComfyUI 起不來")
    sys.exit(1)


def render(shot, seed):
    """單段 3 秒 704x1280，不接龍。"""
    scene = CLIPS / f"{shot}_scene.jpg"
    prompt = (CLIPS / f"{shot}_video.txt").read_text(encoding="utf-8").strip()
    start = COMFY / "input" / f"m12_{shot}_{seed}.png"
    ff("-i", str(scene), "-vf",
       "scale=704:1280:force_original_aspect_ratio=increase,crop=704:1280", str(start))

    g = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "wan22_5b_turbo_Q4_K_M.gguf"}},
        "2": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8.0}},
        "3": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                         "type": "wan", "device": "default"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": prompt}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": NEG}},
        "6": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
        "12": {"class_type": "LoadImage", "inputs": {"image": start.name}},
        "7": {"class_type": "Wan22ImageToVideoLatent",
              "inputs": {"vae": ["6", 0], "width": 704, "height": 1280, "length": FRAMES,
                         "batch_size": 1, "start_image": ["12", 0]}},
        "8": {"class_type": "KSampler",
              "inputs": {"model": ["2", 0], "positive": ["4", 0], "negative": ["5", 0],
                         "latent_image": ["7", 0], "seed": seed, "steps": 4, "cfg": 1.0,
                         "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "9": {"class_type": "VAEDecodeTiled",
              "inputs": {"samples": ["8", 0], "vae": ["6", 0], "tile_size": 256, "overlap": 64,
                         "temporal_size": 64, "temporal_overlap": 8}},
        "10": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24.0}},
        "11": {"class_type": "SaveVideo", "inputs": {"video": ["10", 0],
                                                     "filename_prefix": f"m12_{shot}_{seed}",
                                                     "format": "mp4", "codec": "h264"}},
    }
    t0 = time.time()
    pid = api("/prompt", {"prompt": g})["prompt_id"]
    note(f"  {shot} 已排入佇列")
    while time.time() - t0 < 1800:
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
                            p = COMFY / "output" / f.get("subfolder", "") / f["filename"]
                            note(f"  {shot} 完成，{(time.time()-t0)/60:.1f} 分鐘")
                            return p
            if e.get("status", {}).get("status_str") == "error":
                note(f"  {shot} ERROR: {json.dumps(e.get('status'))[:300]}")
                return None
    note(f"  {shot} 逾時")
    return None


def main():
    STATUS.write_text("", encoding="utf-8")
    note("=== 四鏡 12 秒開工 ===")
    proc = comfy_up()

    stamp = int(time.time()) % 900000
    parts = []
    for i, shot in enumerate(SHOTS):
        note(f"[{i+1}/4] 生 {shot}")
        p = render(shot, stamp + i * 17)
        if not p:
            note(f"FATAL: {shot} 生不出來")
            if proc:
                proc.terminate()
            sys.exit(1)
        out = CLIPS / f"{shot}.mp4"
        ff("-i", str(p), "-vf", "scale=1080:1964:flags=lanczos,crop=1080:1920",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-an", str(out))
        parts.append(out)

    note("四段都好了，開始串接")
    lst = CLIPS / "_list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    silent = CLIPS / "_12s_silent.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent))

    note("配音效")
    total = SHOT_SEC * len(SHOTS)          # ≈ 12.17
    room = SFX / "roomtone" / "Roomtone,Hvac,Drone,Hum,Low Mids,Loop.mp3"
    liquid = next((SFX / "liquid").glob("*.mp3"), None) or next((SFX / "liquid").glob("*.wav"), None)
    whimper = SFX / "dog-whimper" / "EFX INT Dog Wimper 06 A.M.wav"

    final = REVIEW / "d3s1-12秒-淹水.mp4"
    inputs, filters, mix = ["-i", str(silent)], [], []
    idx = 1
    inputs += ["-i", str(room)]
    filters.append(f"[{idx}:a]atrim=0:{total + 0.3:.1f},lowpass=f=900,volume=0.3,"
                   f"afade=t=in:st=0:d=0.4,afade=t=out:st={total - 0.6:.1f}:d=0.6[amb]")
    mix.append("[amb]")
    idx += 1
    if liquid and liquid.exists():
        # 第一鏡：水災現場的水聲；第三鏡：哈士奇玩水的潑水聲
        inputs += ["-i", str(liquid)]
        filters.append(f"[{idx}:a]atrim=0:2.5,adelay=200|200,volume=0.8[liq1]")
        mix.append("[liq1]")
        idx += 1
        inputs += ["-i", str(liquid)]
        splash_at = int(SHOT_SEC * 2 * 1000) + 300     # 第三鏡開頭
        filters.append(f"[{idx}:a]atrim=0:2.5,adelay={splash_at}|{splash_at},volume=0.7[liq2]")
        mix.append("[liq2]")
        idx += 1
    if whimper.exists():
        wh_at = int(SHOT_SEC * 3 * 1000) + 200         # 第四鏡開頭：放棄的嗚咽
        inputs += ["-i", str(whimper)]
        filters.append(f"[{idx}:a]atrim=0:1.8,adelay={wh_at}|{wh_at},volume=1.2[wh]")
        mix.append("[wh]")
        idx += 1
    filters.append("".join(mix) + f"amix=inputs={len(mix)}:duration=first:dropout_transition=0,"
                                  "loudnorm=I=-11:TP=-1.2:LRA=11[a]")
    ff(*inputs, "-filter_complex", ";".join(filters),
       "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
       "-shortest", str(final))

    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=noprint_wrappers=1:nokey=1", str(final)],
                         capture_output=True, text=True, check=True).stdout.strip()
    note(f"FINAL: {final} （{float(dur):.1f} 秒）")
    if proc:
        proc.terminate()


if __name__ == "__main__":
    main()
