# -*- coding: utf-8 -*-
"""多鏡剪接引擎：N 張同房間場景圖 → N 支短單段影片 → 硬切串接 → 量剪接點跳動。

**這支是 _舊版備份/make12.py 的復活版**，不是新發明。
make12.py 在 2026-08-10 生出 `d3s1`（四鏡 12 秒淹水），那支是九支已發布影片裡
唯一有「狀態推進」的本機片。這支把它參數化、補上三個當時沒有的東西：

1. `--steps 8`（make12 寫死 4）。8/14 單變數實驗證明 steps 8 對 4 全面勝出。
2. **每鏡之間呼叫 /free 卸模型**。make12 沒有這段，8/17 實測這台 RAM 只剩 2.8 GB，
   連跑三支不卸模型第二支開始會卡在換頁上。make_video_local_5s.py 早就有這段了。
3. **生完自動量剪接點的 scene_score**。多鏡最大的風險就是「刀口跳很兇」，
   不能靠感覺judge。8/17 實測基準：
       73 幀鏡（3.04 秒）→ 三刀 0.183 / 0.345 / 0.279
      121 幀鏡（5.04 秒）→ 兩刀 0.341 / 0.443
   **鏡越長，刀口跳越大**（推論：Wan 在 5 秒裡把角色漂移得更遠，末幀離自己的
   場景圖更遠，而下一鏡的首幀就是它自己的場景圖）。所以預設 73 幀不是 121。
   > 判讀：< 0.30 順、0.30–0.40 看得出剪但可接受、> 0.45 要重做那一鏡。

用法：
    python make_shots.py clips3 d8_ 3
    python make_shots.py clips3 d8_ 3 --frames 73 --steps 8 --seed 424260

檔案約定（放在 <素材資料夾> 裡）：
    <前綴>1_scene.jpg   <前綴>1_video.txt
    <前綴>2_scene.jpg   <前綴>2_video.txt
    ...
輸出：<素材資料夾>/_silent.mp4（無聲，1080x1920）。配音效是下一步，另外跑 mix。
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
LOCAL = Path(r"C:\Users\TUF Gaming\ai-video-local")
COMFY = LOCAL / "ComfyUI"
API = "http://127.0.0.1:8188"

if len(sys.argv) < 4:
    print(__doc__)
    sys.exit(1)

CLIPS = HERE / sys.argv[1]
PREFIX = sys.argv[2]
NSHOT = int(sys.argv[3])


def opt(name, default, cast=int):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


# 73 幀＝3.04 秒。必須是 4n+1（Wan 的潛在空間時間軸 4 倍壓縮），73 = 4*18+1。
FRAMES = opt("--frames", 73)
if FRAMES % 4 != 1:
    print(f"FAILED: frames 必須是 4n+1，{FRAMES} 不合法")
    sys.exit(1)
STEPS = opt("--steps", 8)
SEED0 = opt("--seed", int(time.time()) % 900000)
# 每鏡末尾丟掉幾幀。Wan 的退化集中在最後，丟掉尾巴能讓刀口更乾淨。
# 預設 0（先不要偷偷改變畫面長度），要用再開。
TRIM_TAIL = opt("--trim-tail", 0)

SHOT_SEC = FRAMES / 24.0
STATUS = CLIPS / f"_make_shots.{PREFIX}status.txt"

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


def probe(path, entries):
    return subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries,
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()


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
    """單鏡 i2v，不接龍。每鏡都從自己的場景圖起跳 —— 這是整套方法的核心。

    接龍（拿上一鏡的末幀當下一鏡的起始圖）8/9 三次實測零例外全崩，不要再試。
    """
    scene = CLIPS / f"{shot}_scene.jpg"
    ptxt = CLIPS / f"{shot}_video.txt"
    if not scene.exists() or not ptxt.exists():
        note(f"FATAL: 缺檔 {scene.name} 或 {ptxt.name}")
        sys.exit(1)
    # 跟 make_video_local_5s.py 一致：也吃 ||| 分隔，只取第一段
    prompt = ptxt.read_text(encoding="utf-8").split("|||")[0].strip()
    start = COMFY / "input" / f"ms_{shot}_{seed}.png"
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
                         "latent_image": ["7", 0], "seed": seed, "steps": STEPS, "cfg": 1.0,
                         "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "9": {"class_type": "VAEDecodeTiled",
              "inputs": {"samples": ["8", 0], "vae": ["6", 0], "tile_size": 256, "overlap": 64,
                         "temporal_size": 64, "temporal_overlap": 8}},
        "10": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24.0}},
        "11": {"class_type": "SaveVideo", "inputs": {"video": ["10", 0],
                                                     "filename_prefix": f"ms_{shot}_{seed}",
                                                     "format": "mp4", "codec": "h264"}},
    }
    # RAM 只剩 2-3 GB，連跑多鏡一定要先叫它放掉上一輪的模型
    try:
        api("/free", {"unload_models": True, "free_memory": True}, timeout=60)
    except Exception as e:
        note(f"  （/free 沒成功，不影響生成：{e}）")

    t0 = time.time()
    pid = api("/prompt", {"prompt": g})["prompt_id"]
    note(f"  {shot} 已排入佇列（seed {seed} / steps {STEPS} / {FRAMES} 幀）")
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
    note(f"=== {NSHOT} 鏡 × {SHOT_SEC:.2f} 秒 = {SHOT_SEC*NSHOT:.1f} 秒　開工 ===")
    proc = comfy_up()
    t_all = time.time()

    parts = []
    for i in range(1, NSHOT + 1):
        shot = f"{PREFIX}{i}"
        note(f"[{i}/{NSHOT}] 生 {shot}")
        raw = render(shot, SEED0 + i * 17)
        if not raw:
            note(f"FATAL: {shot} 生不出來。只要重跑這一鏡，前面幾鏡不用重生。")
            if proc:
                proc.terminate()
            sys.exit(1)
        out = CLIPS / f"{shot}.mp4"
        # 放大到 Shorts 規格。-an 一定要留：concat -c copy 要求所有片段格式一致。
        vf = "scale=1080:1964:flags=lanczos,crop=1080:1920"
        args = ["-i", str(raw)]
        if TRIM_TAIL:
            args += ["-frames:v", str(FRAMES - TRIM_TAIL)]
        ff(*args, "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-an", str(out))
        parts.append(out)

    note("全部鏡頭都好了，硬切串接")
    lst = CLIPS / "_list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    silent = CLIPS / "_silent.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent))

    dur = float(probe(silent, "format=duration"))
    note(f"OUT: {silent} （{dur:.2f} 秒，無聲）")

    # ── 量剪接點跳動 ─────────────────────────────────────────
    note("量剪接點跳動（scene_score）")
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(silent),
         "-vf", "select='gt(scene,0.06)',metadata=print:file=-", "-f", "null", "-"],
        capture_output=True, text=True)
    times, scores = [], []
    for ln in (r.stdout + r.stderr).splitlines():
        if "pts_time:" in ln:
            times.append(float(ln.split("pts_time:")[1].split()[0]))
        if "scene_score=" in ln:
            scores.append(float(ln.split("scene_score=")[1].strip()))
    cuts = [round(SHOT_SEC * k, 2) for k in range(1, NSHOT)]
    note(f"  預期刀口在 {cuts}")
    worst = 0.0
    for t, s in zip(times, scores):
        near = any(abs(t - c) < 0.15 for c in cuts)
        tag = "← 刀口" if near else "（鏡內變化）"
        if near:
            worst = max(worst, s)
        note(f"  {t:6.2f}s  {s:.3f}  {tag}")
    if not scores:
        note("  ⚠️ 全片沒有任何 >0.06 的畫面變化 —— 這就是「沒有劇情」的數字長相，"
             "三鏡等於白拍，回去檢查場景圖之間到底有沒有變。")
    else:
        note(f"  最大刀口跳動 = {worst:.3f}　"
             f"（<0.30 順 / 0.30-0.40 可接受 / >0.45 那一鏡重做）")

    note(f"=== 總耗時 {(time.time()-t_all)/60:.1f} 分鐘 ===")
    note(f"下一步：配音效，然後跑 PUBLISH_GATE 十條。")
    if proc:
        proc.terminate()


if __name__ == "__main__":
    main()
