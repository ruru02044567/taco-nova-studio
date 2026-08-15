# MODEL_REGISTRY — 本機模型清冊

> 盤點日期：2026-08-12｜路徑：`C:\Users\TUF Gaming\ai-video-local\ComfyUI\models`
> 合計約 **33 GB**，全部已在本機，**不需要再下載任何東西就能跑完 Phase 1**

## IMAGE_MODEL（底模型）

| 模型 | 大小 | 用途 | VRAM | 本專案狀態 |
|---|---|---|---|---|
| `RealVisXL_V5.0_Lightning_fp16.safetensors` | 6.46 GB | 寫實向 SDXL，**財富密碼主力** | ~6.5 GB | ✅ 使用中 |
| `DreamShaperXL_Turbo_v2_1.safetensors` | 6.46 GB | 卡通風 SDXL | ~6.5 GB | ⏸ 卡通農場專用，本專案不用 |
| `sd_xl_base_1.0.safetensors` | 6.54 GB | SDXL 原版 | — | 🔴 **檔案損毀，無法載入** |
| `sd_xl_turbo_1.0_fp16.safetensors` | 6.46 GB | 快速出圖 | ~6.5 GB | ⏸ 未使用 |

## VIDEO_MODEL

| 模型 | 大小 | 用途 | 狀態 |
|---|---|---|---|
| `unet\wan22_5b_turbo_Q4_K_M.gguf` | 3.2 GB | Wan 2.2 5B Turbo，**Q4 量化版**，i2v 生影片 | ✅ 使用中（D4S1、D5S1 成品） |
| `vae\wan2.2_vae.safetensors` | 1.31 GB | Wan 2.2 專用 VAE | ✅ 搭配上者 |
| `text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors` | 6.27 GB | Wan 2.2 文字編碼器（FP8） | ✅ 搭配上者 |

量化到 Q4_K_M 是為了塞進 8 GB。這是**已驗證可跑**的組合，不要換成未量化版。

## CONTROL_MODEL（控制與參考）

| 模型 | 大小 | 用途 | 狀態 |
|---|---|---|---|
| `controlnet\xinsir_controlnet_union_sdxl_promax.safetensors` | 2.34 GB | 鎖構圖（深度圖模式） | ✅ 關鍵元件 |
| `ipadapter\ip-adapter-plus_sdxl_vit-h.safetensors` | 0.79 GB | 鎖角色外觀 | ✅ 使用中 |
| `ipadapter\ip-adapter_sdxl_vit-h.safetensors` | 0.65 GB | IP-Adapter 標準版 | ⏸ 備用 |
| `clip_vision\CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` | 2.35 GB | IP-Adapter 的視覺編碼器 | ✅ 必要相依 |
| `geometry_estimation\depth_anything_3_base.safetensors` | 0.50 GB | 抽深度圖 | ✅ **必須單獨跑** |

### 🔴 2026-08-12 發現：`sd_xl_base_1.0.safetensors` 已損毀

準備訓練時載入失敗：

```
SafetensorError: Error while deserializing header:
incomplete metadata, file not fully covered
```

四個 checkpoint 逐一驗證的結果：

| 檔案 | 張量數 | 狀態 |
|---|---|---|
| `DreamShaperXL_Turbo_v2_1` | 2516 | ✅ 正常 |
| `RealVisXL_V5.0_Lightning_fp16` | 2526 | ✅ 正常 |
| **`sd_xl_base_1.0`** | — | 🔴 **讀不出來** |
| `sd_xl_turbo_1.0_fp16` | 2515 | ✅ 正常 |

推測是當初下載中斷留下的半成品。**它佔著 6.54 GB 但完全不能用**，
任何寫死用它的 workflow 都會失敗。

**處理建議**：直接刪除回收 6.54 GB。真的需要原版 SDXL 再重新下載。
（未執行——刪檔要賢賢點頭。）

## 訓練工具（2026-08-12 新增）

安裝在 **`LOCAL-AI-STUDIO\_trainlib\`**（獨立目錄，**不是**裝進 ComfyUI 的 venv）。
這樣做是為了不動到現有的生圖環境——不要了直接刪整個資料夾即可，ComfyUI 完全不受影響。

| 套件 | 版本 | 大小 |
|---|---|---|
| `diffusers` | 0.39.0 | 63 MB（三個合計） |
| `peft` | 0.20.0 | |
| `accelerate` | 1.14.0 | |

以 `--no-deps` 安裝，共用 venv 既有的 torch 2.11 / transformers 5.14 / safetensors。
執行時用 `PYTHONPATH` 指向 `_trainlib` 即可。

回滾點：`LOCAL-AI-STUDIO\_pip-freeze-before-training.txt`（安裝前的 87 個套件清單）。

## LORA

| LoRA | 大小 | 對象 | 狀態 |
|---|---|---|---|
| `loras\nubobear_10_steps_00001_.safetensors` | 0.05 GB | 卡通農場的小熊暖寶 | ⏸ 與本專案無關 |

> 🔴 **Taco 和 Nova 目前都沒有任何 LoRA。** 這是本次 audit 最核心的缺口。

## UPSCALE_MODEL / VOICE_MODEL / EMBEDDING

**全部為空。** `upscale_models`、`embeddings`、`latent_upscale_models`、`frame_interpolation` 等資料夾存在但沒有檔案。

超解析（Phase 8）與本機語音目前完全沒有能力，需要時才評估安裝。

## 訓練工具

| 工具 | 狀態 |
|---|---|
| kohya_ss | ❌ 未安裝 |
| sd-scripts | ❌ 未安裝 |
| ai-toolkit | ❌ 未安裝 |
| OneTrainer | ❌ 未安裝 |
| diffusers | ❌ 未安裝 |

> 🔴 **要訓練任何 LoRA，必須先安裝訓練工具。這是 Phase 4 開始前的第一個必要安裝。**
> 依照安裝政策，安裝前會先提出完整的 VRAM / RAM / 硬碟 / 授權 / 相容性分析給賢賢核准。

## 安裝政策（沿用文件第九節）

任何新模型安裝前必須先回答：Purpose / License / VRAM / RAM / Disk / Compatibility / Expected Speed。
非必要不安裝。目前判定**唯一必要**的新安裝是 LoRA 訓練工具。
