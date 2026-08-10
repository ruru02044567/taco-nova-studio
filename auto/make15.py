# -*- coding: utf-8 -*-
"""三鏡 15 秒：3 張場景圖 → 3 支 5 秒單段影片 → 串接 → 配 Sonniss 真實音效。

為什麼要這樣做：本機 Wan 2.2 的訓練長度是 121 格（5 秒），接龍第二段三次實測全崩
（長人手／增生第二隻狗／換品種）。所以 15 秒不能用接龍，只能「每鏡各生一張場景圖、
各自單獨生成、再剪在一起」——這也是專業短片的分鏡做法，而且每鏡都是「第一段」不會漂移。

用法：python make15.py
進度：寫進 make15.status.txt（對話斷了也查得到）
輸出：..\待審核\d3s1-15秒-淹水.mp4
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
CLIPS = HERE / "clips15"
REVIEW = HERE.parent / "待審核"
REVIEW.mkdir(parents=True, exist_ok=True)
STATUS = HERE / "make15.status.txt"

LOCAL = Path(r"C:\Users\TUF Gaming\ai-video-local")
COMFY = LOCAL / "ComfyUI"
API = "http://127.0.0.1:8188"
SFX = HERE.parent / "sfx" / "lib"

SHOTS = ["s1", "s2", "s3"]
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
    """單段 5 秒 704x1280，不接龍。"""
    scene = CLIPS / f"{shot}_scene.jpg"
    prompt = (CLIPS / f"{shot}_video.txt").read_text(encoding="utf-8").strip()
    start = COMFY / "input" / f"m15_{shot}_{seed}.png"
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
              "inputs": {"vae": ["6", 0], "width": 704, "height": 1280, "length": 121,
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
                                                     "filename_prefix": f"m15_{shot}_{seed}",
                                                     "format": "mp4", "codec": "h264"}},
    }
    t0 = time.time()
    pid = api("/prompt", {"prompt": g})["prompt_id"]
    note(f"  {shot} 已排入佇列")
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
    note("=== 三鏡 15 秒開工 ===")
    proc = comfy_up()

    stamp = int(time.time()) % 900000
    parts = []
    for i, shot in enumerate(SHOTS):
        note(f"[{i+1}/3] 生 {shot}")
        p = render(shot, stamp + i * 17)
        if not p:
            note(f"FATAL: {shot} 生不出來")
            if proc:
                proc.terminate()
            sys.exit(1)
        # 放大到 Shorts 規格
        out = CLIPS / f"{shot}.mp4"
        ff("-i", str(p), "-vf", "scale=1080:1964:flags=lanczos,crop=1080:1920",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-an", str(out))
        parts.append(out)

    note("三段都好了，開始串接")
    lst = CLIPS / "_list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    silent = CLIPS / "_15s_silent.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent))

    note("配音效")
    room = SFX / "roomtone" / "Roomtone,Hvac,Drone,Hum,Low Mids,Loop.mp3"
    liquid = next((SFX / "liquid").glob("*.mp3"), None) or next((SFX / "liquid").glob("*.wav"), None)
    whimper = SFX / "dog-whimper" / "EFX INT Dog Wimper 06 A.M.wav"

    final = REVIEW / "d3s1-15秒-淹水.mp4"
    inputs, filters, mix = ["-i", str(silent)], [], []
    idx = 1
    inputs += ["-i", str(room)]
    filters.append(f"[{idx}:a]atrim=0:15.2,lowpass=f=900,volume=0.12,"
                   f"afade=t=in:st=0:d=0.4,afade=t=out:st=14.6:d=0.6[amb]")
    mix.append("[amb]")
    idx += 1
    if liquid and liquid.exists():
        inputs += ["-i", str(liquid)]
        filters.append(f"[{idx}:a]atrim=0:3,adelay=200|200,volume=0.5[liq]")
        mix.append("[liq]")
        idx += 1
    if whimper.exists():
        inputs += ["-i", str(whimper)]
        filters.append(f"[{idx}:a]atrim=0:1.8,adelay=11200|11200,volume=0.9[wh]")
        mix.append("[wh]")
        idx += 1
    filters.append("".join(mix) + f"amix=inputs={len(mix)}:duration=first:dropout_transition=0,"
                                  "loudnorm=I=-14:TP=-1.5:LRA=11[a]")
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
