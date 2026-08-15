# RESOURCE_STATUS — 硬體與環境現況

> 盤點日期：2026-08-12｜全部數字為**當場實測**，非規格書抄錄

## 硬體

| 項目 | 實測值 | 對本專案的意義 |
|---|---|---|
| GPU | NVIDIA RTX 5050 Laptop GPU | Blackwell 架構 |
| VRAM | **8151 MiB（約 7.96 GB）** | SDXL 生圖沒問題；SDXL LoRA 訓練會很緊 |
| 算力 | **sm_120 (12, 0)** | 需要較新的 PyTorch，見下 |
| 驅動 | 610.88 | — |
| RAM | 15.3 GB 總 / **當下只剩 3.6 GB 可用** | 🔴 這是目前最被低估的瓶頸 |
| CPU | AMD Ryzen 7 260 w/ Radeon 780M | 內顯可分擔桌面輸出，讓獨顯專心跑模型 |
| 硬碟 | C: 447 GB 總 / **剩 144 GB** | 夠裝訓練工具與資料集 |

## 軟體環境

| 項目 | 實測值 |
|---|---|
| ComfyUI venv | `C:\Users\TUF Gaming\ai-video-local\venv` |
| Python | 3.13.14 |
| PyTorch | **2.11.0+cu128** |
| CUDA build | 12.8 |
| `torch.cuda.is_available()` | **True** |
| custom_nodes | ComfyUI-GGUF、ComfyUI_IPAdapter_plus |

### ⚠️ 一條舊結論已經過時，必須更正

先前記錄「RTX 5050 是 Blackwell sm_120，穩定版 PyTorch 不支援，只能走 nightly」。

**實測結果：torch 2.11.0+cu128 已經正式支援 sm_120，`cuda.is_available()` 回傳 True，算力正確讀出 (12, 0)。**
這條限制已經解除，之後不要再把它當作阻礙。

## 資源紅線

| 資源 | 安全上限 | 理由 |
|---|---|---|
| VRAM | 峰值 **≤ 7.0 GB** | 留 1 GB 給系統與顯示輸出 |
| RAM | 訓練／生成前需釋出到 **≥ 10 GB 可用** | 曾實測：DA3 + SDXL + IP-Adapter + ControlNet 同時載入 → `Fatal Python error: Aborted`，ComfyUI 整個進程崩潰，佇列卡在 `running=1` 二十分鐘零產出，**表面看像「很慢」其實是死了** |
| 硬碟 | 保留 **≥ 40 GB** 空白 | 訓練 checkpoint 與資料集會長很快 |

## 已驗證的實際速度

| 工作 | 實測速度 | 條件 |
|---|---|---|
| SDXL 生圖（RealVisXL Lightning） | **18～34 秒／張** | 768×1152、steps 8、IP-Adapter + ControlNet，無 OOM |
| 深度圖抽取（DA3） | **4 秒／張** | 必須獨立跑，不可與 SDXL 同 workflow |
| Wan 2.2 i2v 影片 | 未計時，兩段接龍約 10 秒成品 | GGUF Q4_K_M 量化版 |

## RAM 管理程序（每次重工作前執行）

1. 關掉多餘的 Claude Code 視窗（每個約佔 150～350 MB）
2. 關掉 Edge 遙控瀏覽器（若不需要雲端生圖）
3. 確認可用 RAM ≥ 10 GB 再啟動 ComfyUI
4. **絕不**在同一個 workflow 裡同時載入 DA3 + SDXL + IP-Adapter + ControlNet
