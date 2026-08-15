# WORKFLOW_PLAN — 工作流程規劃

> 建立日期：2026-08-12｜狀態：**規劃，尚未執行**

## 目前這條線實際長什麼樣

```
劇本(schedule.json) → 場景圖 → i2v 影片 → 音效 → 待審核 → 發布
                        ↑                    ↑
                    🔴 還綁在雲端        ✅ 已全本機
```

| 步驟 | 現況 | 本機化程度 |
|---|---|---|
| 劇本 / Shot List | `auto\schedule.json` 19 支已寫好 | ✅ 100% |
| **場景圖（Keyframe）** | **主力仍是 Gemini 網頁遙控** | 🔴 **本機版 0/4 不合格** |
| 深度圖 | `make_depth.py` + `clean_depth.py` | ✅ 100% |
| Image-to-Video | ComfyUI Wan 2.2 GGUF，兩段接龍 | ✅ 100%（D4S1、D5S1 已驗證） |
| 音效 | Sonniss 音效庫 + ffmpeg，-14 LUFS | ✅ 100% |
| 品質審查 | 人工＋審片報告 | 🟡 半自動 |
| Upscaling | **無能力**（`upscale_models` 空） | ❌ 0% |
| Voice / Subtitle | 無 | ❌ 0% |
| 發布 | `publish_video.py` 遙控 Studio | 🟡 需瀏覽器 |

## 🔴 核心洞察：瓶頸只有一個

**影片生成已經合格（5 通過 / 2 勉強 / 0 失敗），生圖不合格（7 項全過 0/4）。**

兩者的差別在於：**D4S1 的 i2v 起點是 Gemini 生的場景圖，不是本機生圖。**

> 也就是說——**整條產線唯一還綁在雲端的，就是第一張圖。**
> 把那張圖本機化，整條線就 offline-capable 了。

而那張圖生不出來的唯一致命原因是 **Nova 認不出來（`WRONG_ANIMAL` 4/4）**。

## 因此：Phase 順序要改

文件原本的順序是 Phase 1 審查 → 2 Style Bible → 3 Dataset → 4 Character LoRA → …

依現況，**Phase 6/7（生圖與 i2v workflow）已經做完大半**，真正卡住的是 Phase 3–4。

### 建議路線

| # | 工作 | 為什麼是這個順序 |
|---|---|---|
| **1** | 建立 Nova 資料集（抽幀 + 補睜眼素材） | 唯一 0/4 的項目，也是脫離雲端的唯一障礙 |
| **2** | 安裝 LoRA 訓練工具 | 目前一個都沒有，這是唯一必要的新安裝 |
| **3** | 訓練 `Nova_LoRA_V1` | — |
| **4** | 一致性測試（9 種角度／表情／光線） | 低於 85 分不進正式製作 |
| **5** | 若 Nova 過關 → 訓 `Taco_LoRA_V1` 補黑點眉 | 黑點眉 4/4 全失，也只有 LoRA 救得回 |
| **6** | 兩個 LoRA 併入 `gen_scene_local.py` | 這時本機生圖才可能取代 Gemini |
| 7 | Upscaling 能力評估 | 目前完全沒有，需評估後再裝 |
| 8 | Voice / Subtitle | 最後做 |

## 建議的資料夾結構

```
財富密碼\LOCAL-AI-STUDIO\
├── PROJECT_AUDIT.md          ← 本次產出
├── MODEL_REGISTRY.md
├── MASTER_STYLE_BIBLE.md
├── ENTITY_REGISTRY.md
├── DATASET_STATUS.md
├── FAILURE_DATABASE.md
├── WORKFLOW_PLAN.md
├── RESOURCE_STATUS.md
├── DATASET\
│   ├── dog_main\   {GOOD, BAD, REVIEW}
│   └── dog_support\{GOOD, BAD, REVIEW}
└── LORA\
    ├── Nova_LoRA_V1\
    └── Taco_LoRA_V1\
```

> 現有的 `auto\`、`character\`、`clips\` **一律不動**，這個資料夾只放新系統的產物。

## 版本管理規則

- 任何 LoRA 一律 `V1 / V2 / V3` 遞增，**禁止覆蓋**
- 每版必須記錄：改了什麼 / 為什麼改 / 一致性分數提高多少
- Workflow 同理（`gen_scene_local.py` 已在 git 版控中）

## 8GB VRAM 保護規則（每次執行前）

1. 確認可用 RAM ≥ 10 GB
2. 單一 workflow 內模型總和 ≤ 7.0 GB VRAM
3. **DA3 深度圖必須獨立跑**，不可與 SDXL 同時載入
4. Batch Size = 1，先低解析度測通再拉高
5. 若預估超標 → 顯示 VRAM WARNING，不直接執行
