"""本機 ComfyUI 生 10 秒片（704x1280 兩段接龍）當雲端的備援。
用法：python make_video_local.py <scene.jpg> <prompt.txt> <out.mp4>
prompt.txt 用 "|||" 分成兩段（前 5 秒／後 5 秒）；沒有分隔就整段當第一段、第二段自動延續。
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

scene, prompt_file, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
HERE = Path(r"C:\Users\TUF Gaming\ai-video-local")
COMFY = HERE / "ComfyUI"
API = "http://127.0.0.1:8188"

raw = prompt_file.read_text(encoding="utf-8").strip()
parts = [p.strip() for p in raw.split("|||") if p.strip()]
SEG_A = parts[0]
SEG_B = parts[1] if len(parts) > 1 else parts[0] + " The scene continues calmly to its final pose."

TAIL = (" Photorealistic home video, locked-off tripod camera at floor level, no camera operator, "
        "minimal camera movement, slow calm motion, both dogs stay fully in frame.")
NEG = ("blurry, low quality, worst quality, cartoon, anime, 3d render, text, letters, words, captions, "
       "watermark, subtitles, deformed, extra limbs, extra legs, mutated, jpeg artifacts, static image, "
       "overexposed, human, person, hand, arm, fingers, smartphone, phone, holding phone, "
       # 實測崩潰主因：接龍第二段會自己增生第二隻狗、臉部熔化
       "two huskies, three dogs, multiple dogs, duplicate dog, extra dog, cloned animal, "
       "second husky, crowd of animals, melting face, morphing face, warping, distorted face, "
       "changing breed, dog turning into another animal")


def api(path, data=None, timeout=30):
    url = API + path
    req = (urllib.request.Request(url, json.dumps(data).encode(), {"Content-Type": "application/json"})
           if data is not None else urllib.request.Request(url))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def comfy_up():
    try:
        api("/system_stats", timeout=5)
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
            return proc
        except Exception:
            time.sleep(5)
    print("FAILED: ComfyUI 起不來")
    sys.exit(1)


def graph(prompt, seed, prefix, start_image):
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "wan22_5b_turbo_Q4_K_M.gguf"}},
        "2": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8.0}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                                                     "type": "wan", "device": "default"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": prompt + TAIL}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": NEG}},
        "6": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
        "12": {"class_type": "LoadImage", "inputs": {"image": start_image}},
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
        "11": {"class_type": "SaveVideo", "inputs": {"video": ["10", 0], "filename_prefix": prefix,
                                                     "format": "mp4", "codec": "h264"}},
    }


def run_graph(g, label):
    pid = api("/prompt", {"prompt": g})["prompt_id"]
    t0 = time.time()
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
                            print(f"{label} done in {(time.time()-t0)/60:.1f} min")
                            return p
            if e.get("status", {}).get("status_str") == "error":
                return None
    return None


proc = comfy_up()
stamp = str(int(time.time()))[-6:]
s704 = COMFY / "input" / f"auto_{stamp}.png"
ff("-i", str(scene), "-vf", "scale=704:1280:force_original_aspect_ratio=increase,crop=704:1280", str(s704))

a = run_graph(graph(SEG_A, int(stamp) % 900000, f"auto_{stamp}_A", s704.name), "segA")
if not a:
    print("FAILED: segA"); sys.exit(1)

bridge = COMFY / "input" / f"auto_{stamp}_br.png"
ff("-sseof", "-0.1", "-i", str(a), "-frames:v", "1", "-update", "1", str(bridge))
bseg = run_graph(graph(SEG_B, int(stamp) % 900000 + 7, f"auto_{stamp}_B", bridge.name), "segB")
if not bseg:
    print("FAILED: segB"); sys.exit(1)

lst = COMFY / "output" / f"auto_{stamp}_list.txt"
lst.write_text(f"file '{a.as_posix()}'\nfile '{bseg.as_posix()}'\n", encoding="utf-8")
silent = COMFY / "output" / f"auto_{stamp}_v.mp4"
ff("-f", "concat", "-safe", "0", "-i", str(lst),
   "-vf", "scale=1080:1964:flags=lanczos,crop=1080:1920",
   "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(silent))
ff("-i", str(silent), "-f", "lavfi", "-i", "anoisesrc=colour=brown:amplitude=0.03:seed=7",
   "-filter_complex", "[1:a]lowpass=f=400,volume=0.5[a]", "-map", "0:v", "-map", "[a]", "-shortest",
   "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", str(out))
print("saved", out)
if proc:
    proc.terminate()
