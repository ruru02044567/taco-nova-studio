# LOCAL VIDEO ENGINE — 現況盤點（AUDIT）

> 建立：2026-08-16｜基準硬體：**原版 TUF Gaming A16，未升級**
> 這份只寫「現在真的有什麼」，不寫規劃。規劃在 `LOCAL_VIDEO_ENGINE_ROADMAP.md`。

---

## 一、實機硬體（2026-08-16 實測，非目標規格）

| 項目 | 實測值 | 備註 |
|---|---|---|
| 機型 | ASUS TUF Gaming A16 **FA608UHI** | |
| CPU | AMD Ryzen 7 260（含 Radeon 780M 內顯） | |
| GPU | RTX 5050 Laptop，**8151 MiB** | 驅動 610.88 |
| RAM | **15.3 GB 可用 / 16 GB 標稱** | ⚠️ 見下方 |
| SSD | C: 447 GB，**剩 123.5 GB** | |

### ⚠️ 兩個盤點時才發現的事

**1. RAM 是「單條 16GB + 一個空插槽」，目前跑在單通道。**

```
DIMM 0: 16 GB  5600 MHz  A-DATA
插槽總數: 2      ← 還有一槽是空的
```

這代表兩件事：① 升級不用丟掉現有記憶體，加一條就好；
② **目前是單通道**，而 Wan 這種要把權重在 RAM/VRAM 之間搬的工作，
記憶體頻寬是真的會影響速度的。補一條同規格上雙通道，理論上除了容量還會有頻寬收益。
（**頻寬收益是推的，沒實測**——這台從來沒在雙通道狀態下跑過。）

**2. 磁碟只剩 123.5 GB，而模型已經佔了 55 GB。**
這支持「先盤點現有的，不要先下載一堆大模型」這個方向。

---

## 二、現有模型清單（55 GB）

### 影片側 —— 只有一套，沒有替代品

| 檔案 | 大小 | 角色 |
|---|---:|---|
| `wan22_5b_turbo_Q4_K_M.gguf` | 3.20 GB | **唯一的影片生成模型**（4 步蒸餾版） |
| `wan2.2_vae.safetensors` | 1.31 GB | Wan 專用 VAE |
| `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | 6.27 GB | Wan 的 text encoder |

### 生圖側 —— 反而很完整

| 檔案 | 大小 | 角色 |
|---|---:|---|
| `sd_xl_base_1.0` / `sd_xl_turbo` / `DreamShaperXL_Turbo_v2_1` / `RealVisXL_V5.0_Lightning` | 各 ~6.5 GB | 四個 SDXL checkpoint |
| `xinsir_controlnet_union_sdxl_promax` | 2.34 GB | **ControlNet（姿勢/深度/邊緣控制）** |
| `ip-adapter-plus_sdxl_vit-h` + `ip-adapter_sdxl_vit-h` | 0.79 + 0.65 GB | **IP-Adapter（參考圖）** |
| `CLIP-ViT-H-14-laion2B` | 2.35 GB | IP-Adapter 的視覺編碼器 |
| `depth_anything_3_base` | 0.50 GB | 深度圖估計 |
| `flux1-schnell-Q4_K_S.gguf` + `t5xxl` + `clip_l` + `ae` | 11.42 GB | FLUX 生圖（商用授權） |

### LoRA —— **全部是 SDXL 的，沒有一個能用在 Wan 上**

實際讀 safetensors header 驗證過，5 個 LoRA 的 key 全是 `lora_unet_down_blocks_*`
（SDXL 的 UNet 命名），不是 Wan 的 DiT 結構。

| 檔案 | 架構 | 張量數 |
|---|---|---:|
| `taco_V1_use035` | SDXL | 1680 |
| `nova_V1_use035` / `nova_lora_V1_step1000` / `nova_lora_V2_step1500` | SDXL | 1680 |
| `nubobear_10_steps` | SDXL | 3268 |

**這是整個盤點最重要的發現之一** → 見第四節。

---

## 三、ComfyUI 擴充節點：只有兩個

```
ComfyUI-GGUF              跑 GGUF 量化模型（Wan / FLUX 都靠它）
ComfyUI_IPAdapter_plus    IP-Adapter
```

**沒裝**：`comfyui_controlnet_aux`（OpenPose/Canny 等 preprocessor）、
任何 video/temporal 相關節點、任何 upscale 節點包。

ControlNet 本體 ComfyUI 內建支援，所以 `xinsir controlnet union` 能載入；
但要從照片抽姿勢骨架，目前只能靠自己寫的 `make_depth.py` + `depth_anything_3`
（只有深度，沒有骨架）。

---

## 四、⚠️ 最關鍵的三個發現

### 4.1 「1080×1920」是拉上去的，不是生出來的

`make_video_local_5s.py` 的實際流程：

```
Wan 生成 704×1280
   ↓ ffmpeg scale=1080:1964:flags=lanczos
   ↓ crop=1080:1920
輸出「1080×1920」
```

**真實資訊量只有 704×1280 = 90 萬像素，1080×1920 是 207 萬像素。**
等於只有目標的 **43%**，其餘是 lanczos 內插補出來的。

`upscale_models/` 目錄裡只有一個佔位檔 `put_esrgan_and_other_upscale_models_here`，
**一個 AI 放大模型都沒有**。

→ 這是「本機片畫質看起來就是比較糊」的一個具體、可量化的原因，
且它跟模型的動作能力**無關**，是獨立的一條可改善路徑。

### 4.2 所有進階控制能力都在生圖側，影片側是光禿禿的

| 能力 | 生圖（SDXL） | 影片（Wan） |
|---|---|---|
| 參考圖鎖角色 | ✅ IP-Adapter | ❌ 無 |
| 姿勢／構圖控制 | ✅ ControlNet Union | ❌ 無 |
| 角色 LoRA | ✅ taco/nova/bear | ❌ 無（現有 LoRA 架構不相容） |
| 深度圖 | ✅ depth_anything_3 | ❌ 無 |

這解釋了為什麼現行產線的最佳實踐是
「**能搬到生圖階段的事就不要留給影片模型**」——那不是偏好，是因為
影片那一側**現在什麼控制手段都沒有**，只有一個 prompt 輸入口。

### 4.3 Wan 那條線只有「一個模型、一種設定、一條 workflow」

沒有 workflow json（Wan 的工作流是寫死在 `make_video_local_5s.py` 的字典裡），
沒有第二個影片模型可以對照，沒有非蒸餾版可以比較。
`workflows/` 資料夾裡只有 `flux_schnell_api.json` 一個檔。

---

## 五、現有腳本資產

### `ai-video-local\`（12 支 gen_*.py，多為一次性實驗）
`gen_flux.py`（8/15，還在用）、`gen_shot1_local.py`（單段模板）、
`gen_10s.py`（接龍，已棄用）、其餘 8/6–8/9 的一次性腳本。

### `財富密碼\auto\`（產線用，這些是資產）

| 腳本 | 用途 | 對 benchmark 的價值 |
|---|---|---|
| `make_video_local_5s.py` | Wan 單段生成 | **主受測對象**，已參數化（steps/shift/length/sampler/scheduler/seed） |
| `flow.py` | 光流解釋率 | **量流暢度的唯一工具**，比「動量」準 |
| `charstab.py` | 角色穩定度代理指標 | 量角色漂移 |
| `make_depth.py` / `clean_depth.py` | 深度圖 | ControlNet 路線的既有基礎 |
| `gen_scene_local.py` | 本機生圖 | SDXL 側入口 |
| `plan_model.py` | 能力判斷 | 見下方警告 |

**已經有量測工具這件事很重要**：`flow.py` 和 `charstab.py` 讓 benchmark
可以出數字而不是只有「看起來比較好」。

---

## 六、⚠️ 產線現存缺陷（盤點時發現，尚未修）

**`plan_model` 的關鍵字比對目前形同虛設。**

- 能力表 100 個關鍵字裡 **87 個是中文**
- `schedule.json` 的 `videoPrompt` **19 支全部是英文**
- 實測：同一支片用 `videoPrompt` 判 vs 用 `title` 判，**19 支裡有 14 支結果不同**

原因是 `plan_model.py` 原本設計成賢賢手動輸入中文劇本
（文件裡的範例全是「Taco 把拖鞋叼起來丟進傳送門」這種），
8/16 接進 pipeline 時餵給它的卻是英文的 `videoPrompt`。

→ **目前的 BLOCKED 判斷只靠那 13 個英文關鍵字在運作，中文的 87 個全是死的。**
→ 在修好之前，不要把 plan_model 的判斷當成可信的守門結果。
→ 修法有兩條路（雙語關鍵字 vs 改用中文欄位），**等賢賢決定，這輪不動 production**。
