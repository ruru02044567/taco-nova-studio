"""本機 ComfyUI 生 704x1280 影片。起點有兩種：

  A. 單張場景圖（原本的做法，行為完全沒變）
       python make_video_local_5s.py <scene.jpg> <prompt.txt> <out.mp4>

  B. 前一段的末 N 格＝「多幀接龍」（2026-08-20 加）
       python make_video_local_5s.py - <prompt.txt> <out.mp4> --continue <前一段.mp4>
       （加 --join <長鏡.mp4> 就順便把前一段和這一段接成一個連續長鏡）

## 為什麼要多幀接龍 —— 8/9 那次「接龍失敗」的結論下錯了地方

8/9 三次實測是拿「前一段的最後一張畫面」當起始圖去生第二段，每次都崩
（長人手／增生第二隻狗／換品種），當時寫死結論「本機不能接龍」。
8/20 讀 ComfyUI 0.30.0 `comfy_extras/nodes_wan.py` 的 Wan22ImageToVideoLatent 才發現：

    start_image = start_image[:length]              # 想餵幾格就餵幾格，不是只能一張
    latent_temp = vae.encode(start_image)
    latent[:, :, :latent_temp.shape[-3]] = latent_temp
    mask[:, :, :latent_temp.shape[-3]] *= 0.0       # ← 餵幾格就鎖幾格，KSampler 完全不動

單張圖 ＝ 零運動資訊、零身分錨。模型只知道「這一瞬間長這樣」，不知道牠正往哪動、
動多快、側面長怎樣，要它接著演就只能重新想像一次 —— 那才是長人手與增生第二隻狗的根因。
餵 17 格（0.7 秒）等於同時給了動量與多視角的身分參考，而且這 17 格的 latent 被 mask
鎖死不參與去噪，接縫在數學上就是同一段畫面，不是「接得像」。

⚠️ 這是待驗假說不是結論。5B TI2V 訓練時的條件是單幀，餵多幀等於當 latent inpainting
用，模型有可能不吃這套。這支檔案是拿來驗這件事的。

## 幀數規矩

length 與 anchor 都必須是 4n+1（Wan 的潛在空間時間軸 4 倍壓縮）。anchor 可選 13/17/21/25。
接龍段輸出的是完整 length 格，其中前 anchor 格是前一段尾巴的還原版（見下一節）。
新畫面 ＝ length − anchor 格（預設 121 − 17 ＝ 104 格 ＝ 4.33 秒）。
想讓新畫面滿 5 秒就加 `--length 137`（多 13% 算圖時間與 VRAM，8GB 邊緣，自己斟酌）。

## ⚠️ 接法：砍前一段的尾巴，不要砍新這段的頭（2026-08-20 量出來的）

新這段的前 anchor 格 ＝ 餵進去那 anchor 格被 VAE 還原回來的版本，跟原檔差一個來回誤差
（實測 RGB 平均位移約 −1.1、逐像素平均絕對差 2.31）。所以接縫要挑在同一次解碼的內部：

    ✅ 前段[0 : 總格數−anchor] ＋ 新段整段        接縫幀差 2.68
    ❌ 前段整段 ＋ 新段[anchor:]                   接縫幀差 8.58
    （對照：舊做法兩段各自生再硬接 24.56；同一段內相鄰幀的正常跳動是 1.58）

用 ✅ 那種接法，接縫只有正常跳動的 1.7 倍，肉眼看不出來；用 ❌ 會在接縫看到一下
輕微的「洗掉再回來」。`--join` 會直接照 ✅ 接好，不用自己算格數。

## 每次都會多產一個 .raw704.mp4

那是 ComfyUI 的原生 704x1280 輸出。下一段要接龍時餵它，不要餵 1080x1920 的成品
—— 成品經過 lanczos 放大再裁掉 44px，餵回去等於接一張被縮放過又換過構圖的圖。
給 `--continue` 一個成品路徑時，本程式會自動改用旁邊的 .raw704.mp4。
"""
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import studio_lock  # noqa: E402

scene, prompt_file, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])

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
# ⛔ 2026-08-20：爬網研究建議「降到 4 省一半時間」，依據只有模型卡一句通論，
#    而本機 13 份實驗 log 是反的（而且成本也講反了，4→8 是多 30% 不是多一倍）。維持 8。
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
# --continue / --anchor：2026-08-20 加的多幀接龍，見檔頭。
PREV = None
if "--continue" in sys.argv:
    PREV = Path(sys.argv[sys.argv.index("--continue") + 1])
ANCHOR = 17
if "--anchor" in sys.argv:
    ANCHOR = int(sys.argv[sys.argv.index("--anchor") + 1])
# --join：順便把前一段與這一段接成一個連續長鏡（接法見檔頭）。
JOIN = None
if "--join" in sys.argv:
    JOIN = Path(sys.argv[sys.argv.index("--join") + 1])
# --dry-run：只組工作流與抽錨點，不排隊、不吃顯卡。用來確認接線對不對。
DRY = "--dry-run" in sys.argv
FPS = 24

if JOIN is not None and PREV is None:
    print("FAILED: --join 要配 --continue 用（沒有前一段就沒東西可以接）")
    sys.exit(1)

if PREV is not None:
    if ANCHOR % 4 != 1:
        print(f"FAILED: anchor 必須是 4n+1（13/17/21/25…），{ANCHOR} 不合法")
        sys.exit(1)
    if ANCHOR >= LENGTH:
        print(f"FAILED: anchor {ANCHOR} 不能 >= length {LENGTH}，那樣一格新內容都不會生")
        sys.exit(1)
    # 給成品路徑時自動改用旁邊的原生 704 檔（見檔頭）
    raw_of_prev = PREV.with_name(PREV.stem + ".raw704.mp4")
    if raw_of_prev.exists():
        print(f"  接龍來源自動換成原生檔：{raw_of_prev.name}")
        PREV = raw_of_prev
    if not PREV.exists():
        print(f"FAILED: 接龍來源不存在：{PREV}")
        sys.exit(1)
elif not scene.exists():
    print(f"FAILED: 起始圖不存在：{scene}（沒有 --continue 就一定要有場景圖）")
    sys.exit(1)

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

FIT704 = "scale=704:1280:force_original_aspect_ratio=increase,crop=704:1280"


def api(path, data=None, timeout=30):
    req = (urllib.request.Request(API + path, json.dumps(data).encode(),
                                  {"Content-Type": "application/json"})
           if data is not None else urllib.request.Request(API + path))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def nframes(p):
    """數實際幀數。-count_frames 慢，但我們的片都只有 121 格，眨眼就數完。"""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True).stdout.strip()
    if not r.isdigit():
        print(f"FAILED: 數不出 {p.name} 的幀數（ffprobe 回「{r}」）")
        sys.exit(1)
    return int(r)


def frames_rgb(p, start, n):
    """抓 [start, start+n) 這幾格，回 (n*H*W, 3) 的 float 陣列。只給診斷用。"""
    import numpy as np
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(p),
         "-vf", f"trim=start_frame={start}:end_frame={start + n},setpts=N/{FPS}/TB,{FIT704}",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.uint8).reshape(-1, 3).astype("float64")


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


# 產線互斥（8/20 加）：這台只有一張顯卡，兩個視窗同時生片只會排隊互踩。
# --dry-run 不碰顯卡，不用搶鎖（不然驗接線也要排隊等別人跑完）。
if not DRY:
    studio_lock.acquire(f"生影片 {out.name}")

proc = None if DRY else comfy_up()
stamp = str(int(time.time()))[-6:]

if PREV is None:
    s704 = COMFY / "input" / f"s5_{stamp}.png"
    ff("-i", str(scene), "-vf", FIT704, str(s704))
    print("起始圖已備好")
    anchor_mp4 = None
    start_nodes = {"12": {"class_type": "LoadImage", "inputs": {"image": s704.name}}}
    start_ref = ["12", 0]
else:
    # 把前一段的末 ANCHOR 格切成一支小影片丟進 ComfyUI/input。
    # 為什麼不直接 LoadVideo 整支前段再 ImageFromBatch(-17)：那會把 121 格全解到記憶體
    # （float32 約 1.3 GB），這台 RAM 本來就在邊緣。先用 ffmpeg 砍成 17 格再丟進去。
    # crf 0 ＝ 數學無損：那 17 格是要直接進 VAE 的，不能帶壓縮痕。
    total_prev = nframes(PREV)
    if total_prev < ANCHOR:
        print(f"FAILED: 前一段只有 {total_prev} 格，抽不出 {ANCHOR} 格錨點")
        sys.exit(1)
    anchor_mp4 = COMFY / "input" / f"s5_{stamp}_anchor.mp4"
    ff("-i", str(PREV), "-vf",
       f"trim=start_frame={total_prev - ANCHOR},setpts=N/{FPS}/TB,{FIT704}",
       "-an", "-r", str(FPS), "-c:v", "libx264", "-crf", "0", "-pix_fmt", "yuv420p",
       str(anchor_mp4))
    got = nframes(anchor_mp4)
    if got != ANCHOR:
        print(f"FAILED: 錨點應該是 {ANCHOR} 格，切出來卻是 {got} 格")
        sys.exit(1)
    print(f"錨點已備好：{PREV.name} 的第 {total_prev - ANCHOR}–{total_prev - 1} 格"
          f"（{ANCHOR} 格 = {ANCHOR / FPS:.2f} 秒）")
    start_nodes = {
        "12": {"class_type": "LoadVideo", "inputs": {"file": anchor_mp4.name}},
        "13": {"class_type": "GetVideoComponents", "inputs": {"video": ["12", 0]}},
        # 負的 batch_index 在 ImageFromBatch 裡會 += batch 長度（0.30.0 原始碼確認過），
        # 所以 -ANCHOR 就是「最後 ANCHOR 格」。這裡其實已經只有 ANCHOR 格，
        # 留著是保險：萬一解碼多吐一格，格數與順序還是被鎖死的。
        "14": {"class_type": "ImageFromBatch",
               "inputs": {"image": ["13", 0], "batch_index": -ANCHOR, "length": ANCHOR}},
    }
    start_ref = ["14", 0]

g = {
    "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "wan22_5b_turbo_Q4_K_M.gguf"}},
    "2": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": SHIFT}},
    "3": {"class_type": "CLIPLoader",
          "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                     "type": "wan", "device": "default"}},
    "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": PROMPT}},
    "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": NEG}},
    "6": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
    **start_nodes,
    "7": {"class_type": "Wan22ImageToVideoLatent",
          "inputs": {"vae": ["6", 0], "width": 704, "height": 1280, "length": LENGTH,
                     "batch_size": 1, "start_image": start_ref}},
    "8": {"class_type": "KSampler",
          "inputs": {"model": ["2", 0], "positive": ["4", 0], "negative": ["5", 0],
                     "latent_image": ["7", 0],
                     "seed": SEED if SEED is not None else int(stamp) % 900000, "steps": STEPS,
                     "cfg": 1.0, "sampler_name": SAMPLER, "scheduler": SCHEDULER, "denoise": 1.0}},
    "9": {"class_type": "VAEDecodeTiled",
          "inputs": {"samples": ["8", 0], "vae": ["6", 0], "tile_size": 256, "overlap": 64,
                     "temporal_size": 64, "temporal_overlap": 8}},
    "10": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": float(FPS)}},
    "11": {"class_type": "SaveVideo", "inputs": {"video": ["10", 0],
                                                 "filename_prefix": f"s5_{stamp}",
                                                 "format": "mp4", "codec": "h264"}},
}

if DRY:
    print("--dry-run：工作流組好了，沒有排隊。")
    print(json.dumps(g, ensure_ascii=False, indent=2)[:4000])
    print(f"\nstart_image ← {start_ref}"
          f"{'（多幀接龍 %d 格）' % ANCHOR if PREV else '（單張場景圖）'}")
    if PREV:
        print(f"生 {LENGTH} 格，前 {ANCHOR} 格被 mask 鎖死不去噪，"
              f"新內容 {LENGTH - ANCHOR} 格 = {(LENGTH - ANCHOR) / FPS:.2f} 秒")
    sys.exit(0)

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
      f" / shift = {SHIFT} / length = {LENGTH} / {SAMPLER}+{SCHEDULER}"
      f"{' / 接龍錨點 %d 格' % ANCHOR if PREV else ''}", flush=True)
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

# 接龍模式的接縫診斷：生出來的前 ANCHOR 格應該就是餵進去那 ANCHOR 格
# （latent 被 mask 鎖死沒去噪），只差一次 VAE 來回。所以這個差值量的是
# 「接縫到底有沒有真的對齊」。順便量同一段內部的亮度漂移（WanVideoWrapper
# issue #1541 那個色偏 bug 會讓亮度飽和度單調上升）。量了才知道要不要段間調色。
if PREV is not None:
    try:
        import numpy as np
        a = frames_rgb(anchor_mp4, 0, ANCHOR)
        b = frames_rgb(src, 0, ANCHOR)
        n = min(len(a), len(b))
        nf = n // (704 * 1280)
        dmean = b[:n].mean(0) - a[:n].mean(0)
        dabs = float(np.abs(b[:n] - a[:n]).mean())
        tot = nframes(src)
        k = 9
        head = frames_rgb(src, ANCHOR, k).mean()
        tail = frames_rgb(src, tot - k, k).mean()
        verdict = ("✅ 接縫對齊，段間不用調色" if abs(dmean).max() < 2.0
                   else "⚠️ 接縫有色偏，成片前要做段間統一調色")
        print(f"  接縫診斷：錨點 vs 生成的前 {nf} 格，"
              f"RGB 平均位移 {dmean[0]:+.2f}/{dmean[1]:+.2f}/{dmean[2]:+.2f}、"
              f"逐像素平均絕對差 {dabs:.2f}　{verdict}")
        print(f"  段內漂移：新內容頭 {k} 格亮度 {head:.2f} → 尾 {k} 格 {tail:.2f}"
              f"（{tail - head:+.2f}）")
    except Exception as e:
        print(f"  （接縫診斷跳過：{e}）")

# 原生 704x1280 存一份放在成品旁邊，下一段接龍餵這個（見檔頭）。
# 接龍段**不切頭** —— 前 ANCHOR 格要留著當接縫的另一半，理由與實測數字見檔頭「接法」。
raw704 = out.with_name(out.stem + ".raw704.mp4")
shutil.copy2(src, raw704)

# 放大到 1080x1920（Shorts 規格）
UP = "scale=1080:1964:flags=lanczos,crop=1080:1920"
ff("-i", str(src), "-vf", UP,
   "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(out))
print(f"saved {out}（{nframes(out)} 格 = {nframes(out) / FPS:.2f} 秒"
      + (f"，前 {ANCHOR} 格是前段尾巴的還原版）" if PREV is not None else "）"))
print(f"      接龍用原生檔：{raw704.name}")

if PREV is not None:
    keep = nframes(PREV) - ANCHOR
    if JOIN is None:
        print(f"      ⚠️ 組裝時前一段只取前 {keep} 格再接這段，兩段都整段接會重播"
              f" {ANCHOR / FPS:.2f} 秒。懶得算就加 --join。")
    else:
        # 先在 704 原生把長鏡接好，再一次放大 —— 避免放大兩次糊掉。
        join_raw = JOIN.with_name(JOIN.stem + ".raw704.mp4")
        ff("-i", str(PREV), "-i", str(raw704), "-filter_complex",
           f"[0:v]trim=end_frame={keep},setpts=N/{FPS}/TB[a];[a][1:v]concat=n=2:v=1:a=0[v]",
           "-map", "[v]", "-an", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium",
           "-crf", "12", "-pix_fmt", "yuv420p", str(join_raw))
        ff("-i", str(join_raw), "-vf", UP, "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-pix_fmt", "yuv420p", str(JOIN))
        print(f"joined {JOIN}（{nframes(JOIN)} 格 = {nframes(JOIN) / FPS:.2f} 秒，單一連續鏡）")
        print(f"       再接下一段就餵 {join_raw.name}")
if proc:
    proc.terminate()
