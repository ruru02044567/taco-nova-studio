# DATASET_STATUS — 訓練資料盤點

> 盤點日期：2026-08-12｜**12 張參考圖全部逐張目視檢查完畢**
> 修訂紀錄：v2（2026-08-12）撤回 v1 的「Nova 多半閉眼」錯誤結論，補上完整目視盤點

---

## 🔒 角色核心特徵（本專案唯一標準，不得偏離）

### Nova = **Siberian Husky（西伯利亞哈士奇）**
- **Clear blue eyes（清楚的藍眼）** ← 核心辨識物
- 灰白毛、灰黑臉罩、倒 V 額紋
- **Larger body size：站立時約為 Taco 的 3 倍**
- 體型比例最佳參考：**`duo-scene-dogbed.jpg`**

### Taco = **Chihuahua（吉娃娃）**
- **Black eyebrow spots（額頭兩顆黑點眉）** ← 核心辨識物
- **Silver tag / pendant（銀色吊牌）**
- 純白短毛、大尖立耳、灰黑口鼻陰影、藍色項圈

> ⚠️ 兩者犬種不得互換。Nova 是哈士奇，Taco 是吉娃娃。

---

## ❌ 撤回的錯誤結論

本文件 v1 曾寫「Nova 在片中多半閉眼，資料集會學不到藍眼，需要另外取得睜眼素材」。

**這個結論是錯的。** 它是從 D4S1 的審片報告（Nova 在那支影片裡全程睡覺）外推出來的，但參考圖完全不是這樣。

**目視確認：Nova 的 5 張參考圖，全部睜眼，藍眼全部清楚可見。**

---

## A. NOVA DATASET INVENTORY

| 檔案 | 角度分類 | 藍眼 | 犬種正確 | 體型 | 判定 |
|---|---|---|---|---|---|
| `ref-square\nova_face.png` | **Close-up** | ✅ 極清楚 | ✅ 標準哈士奇 | — | **TRAIN** |
| `ref-square\duo_full.png` | **Front full body**（坐） | ✅ 清楚 | ✅ | 約 2.5× | **TRAIN**（需裁切） |
| `duo-新臉-奸詐哈士奇×高傲吉娃娃.jpg` | **Front full body**（坐） | ✅ 清楚 | ✅ | 約 2.5× | **TRAIN**（需裁切） |
| `duo-scene-dogbed.jpg` | **3/4 standing**（全身站姿） | ✅ 可見 | ✅ | **約 3×** ⭐ | **TRAIN**（需裁切）**體型黃金範本** |
| `duo-scene-remote.jpg` | **3/4 lying**（側躺） | ✅ 清楚 | ✅ | — | **TRAIN**（需裁切） |

**Nova：5 張全部可用，0 張 REVIEW，0 張 REJECT。**

> 🔑 **關鍵**：4 張合照的吊牌錯誤全部發生在 **Taco 那半邊**。
> 裁出 Nova 的部分後，這些圖對 Nova 完全乾淨。
> **同一張圖對 Nova 是 TRAIN，對 Taco 是 REVIEW** —— 兩個資料集必須分開判定。

---

## B. TACO DATASET INVENTORY

| 檔案 | 角度分類 | 黑點眉 | 銀吊牌檢查 | 判定 |
|---|---|---|---|---|
| `ref-square\taco_face.png` | **Close-up** | ✅ 兩顆清楚 | 橢圓形，**無文字** ✅ | **TRAIN** |
| `taco-ref-v4a-meme.jpg` | **Front full body**（瞇眼笑） | ✅ 兩顆清楚 | 葉形，**無文字** ✅ | **TRAIN** |
| `taco-ref-v4b-glare.jpg` | **3/4 side body**（張嘴笑）⭐ | ✅ 兩顆清楚 | 細長形，**無文字** ✅ | **TRAIN** |
| `ref-square\duo_full.png` | Front full body | ✅ 兩顆清楚 | 橢圓形，**無文字** ✅ | **TRAIN**（需裁切） |
| `taco-ref-v5-max.jpg` | Front full body（齜牙） | 🟡 **只有一顆清楚** | 葉形，無文字 ✅ | **REVIEW** |
| `duo-新臉-...jpg` | Front full body | ✅ 兩顆 | 🟡 太小無法判讀 | **REVIEW** |
| `duo-scene-remote.jpg` | Front（坐桌上） | ✅ 兩顆 | ❌ **吊牌寫「LUNA」** | **REVIEW** |
| `duo-scene-dogbed.jpg` | Lying（躺狗床） | ✅ 兩顆 | 🟡 文字不明（似「TO」） | **REVIEW** |
| `taco-ref-v3b-mastermind.jpg` | 走路 3/4 | ❌ **無** | ❌ **吊牌寫「Milo」+ 數字** | **REJECT** |
| `taco-ref-v3a-con.jpg` | Front（坐） | ❌ **無** | 橢圓，無文字 | **REJECT** |
| `taco-ref-v2-sly.jpg` | Front（坐） | ❌ **無** | 葉形，無文字 | **REJECT** |
| `taco-ref.jpg`（v1） | Front（坐） | ❌ **無**＋**焦糖耳斑** | 橢圓，無文字 | **REJECT** |

**Taco：4 張 TRAIN、4 張 REVIEW、4 張 REJECT。**

---

## C. TRAIN / REVIEW / REJECT 清單

### TRAIN（可直接進訓練，共 9 個項目）

**Nova（5）**：`nova_face.png`、`duo_full.png`✂、`duo-新臉`✂、`duo-scene-dogbed.jpg`✂、`duo-scene-remote.jpg`✂
**Taco（4）**：`taco_face.png`、`taco-ref-v4a-meme.jpg`、`taco-ref-v4b-glare.jpg`、`duo_full.png`✂

（✂ = 需先裁出單一角色）

### REVIEW（處理後可能可用，全部屬 Taco，共 4）

| 檔案 | 待處理事項 |
|---|---|
| `taco-ref-v5-max.jpg` | 黑點眉只有一顆 → 修圖補上第二顆，或降權使用 |
| `duo-新臉-...jpg` | 吊牌太小無法判讀 → 放大確認，或裁掉吊牌區域 |
| `duo-scene-remote.jpg` | **吊牌「LUNA」** → 遮蔽／裁切吊牌區域 |
| `duo-scene-dogbed.jpg` | 吊牌文字不明 → 同上 |

### REJECT（永久排除，共 4）

| 檔案 | 排除原因 |
|---|---|
| `taco-ref.jpg`（v1） | 焦糖耳斑 + 無黑點眉 + 無辜呆萌臉（三項皆違反現行設定） |
| `taco-ref-v2-sly.jpg` | 改版前設計，無黑點眉，毛色偏米白 |
| `taco-ref-v3a-con.jpg` | 改版前設計，無黑點眉 |
| `taco-ref-v3b-mastermind.jpg` | 改版前設計，無黑點眉，**吊牌錯誤文字「Milo」** |

### 額外永久排除（非參考圖）

- 本機生圖測試的 4 個 seed 成品（配角全生成錯誤）
- 任何含 Bruno（黑拉布拉多）的畫面
- `video-01` 黑洞片 shot 1–3（舊角色設計）
- `d4s1-麵粉-有聲.mp4` 舊版（含幻覺幼犬）
- `d4s1` 第 70 幀後麵粉堆裡脫離身體的狗爪所在畫面

---

## D. 缺少的角度

| 角度 | Nova | Taco |
|---|---|---|
| Close-up | ✅ | ✅ |
| Front full body | ✅ ×2 | ✅ ×2 |
| 3/4 standing | ✅ | ✅（v4b 側身） |
| 3/4 lying | ✅ | ✅（dogbed） |
| **Pure side view（純側面）** | ❌ **缺** | ❌ **缺** |
| **Back view（背面）** | ❌ **缺** | ❌ **缺** |
| 俯視 / 仰視 | ❌ 缺 | ❌ 缺 |

## E. 缺少的表情

| | Nova | Taco |
|---|---|---|
| 現有 | 瞇眼壞笑（5 張全部同一種） | 抬下巴高傲、瞇眼笑、張嘴笑、齜牙（**4 種，相對豐富**） |
| **缺** | **張嘴／吠、驚訝、睡（閉眼）、警覺** | **驚訝、被抓包、跑動中** |

> Nova 的表情多樣性是目前最單薄的一環——5 張全是同一個瞇眼表情。

## F. 缺少的光線

**兩隻狗完全相同：12 張全部是「客廳午後暖窗光」。**

| 光線 | 狀態 |
|---|---|
| 客廳暖窗光 | ✅ 12/12 |
| 夜晚 / 低光 | ❌ 缺 |
| 逆光 / 剪影 | ❌ 缺 |
| 戶外自然光 | ❌ 缺 |
| 高對比戲劇光 | ❌ 缺 |

⚠️ 光線單一會讓 LoRA 把「暖窗光」也一起學進角色特徵，之後換場景可能還原不出來。

---

## G. 角色核心特徵（訓練標籤用）

### Nova（`dog_support`）
```
siberian husky, grey and white fur, black facial mask, inverted V forehead marking,
clear light blue eyes, large body, upright triangular ears
```
**負面**：`pomeranian, fox-like dog, klee kai, small dog, brown eyes, cream fur, closed eyes`

### Taco（`dog_main`）
```
chihuahua, pure white short fur, two black eyebrow spots on forehead,
huge pointed ears, dark grey muzzle shading, blue collar, plain silver tag
```
**負面**：`caramel ear patch, cream fur, text on tag, engraved name, round innocent eyes`

---

## H. Dataset 污染風險

### 🔴 風險 1：吊牌上的隨機英文名（最嚴重）

實測發現**兩個不同的錯誤名字**：

| 檔案 | 吊牌文字 |
|---|---|
| `duo-scene-remote.jpg` | **LUNA** |
| `taco-ref-v3b-mastermind.jpg` | **Milo** + 一串數字 |

這證明**吊牌文字是模型隨機生成的，任何一張的吊牌文字都不可信任**。

若這些圖進入訓練集，LoRA 會學到「吊牌上有英文名字」，之後每次生成都可能吐出錯的名字——而且**這是會出現在成品影片裡的錯誤**。

**對策**：所有進 TRAIN 的圖，吊牌區域一律遮蔽或裁切；標籤寫 `plain silver tag`，負面詞加 `text on tag, engraved name`。

### 🔴 風險 2：AI 失敗品回流

本機生圖 4 個 seed 的配角全部生錯（狐狸犬／博美）。拿去訓練等於教模型「哈士奇長得像狐狸犬」，錯誤會自我強化且救不回來。**絕對禁止。**

### 🟠 風險 3：兩隻狗互相污染

4 張是合照。若不裁切直接訓練單一角色，會重演 IP-Adapter 的老問題——特徵被平均，Nova 被 Taco 的白色短毛拉走。**必須裁出單一角色。**

### 🟠 風險 4：光線單一

12/12 全是客廳暖窗光，LoRA 可能把光線學成角色特徵的一部分。

### 🟡 風險 5：新舊設計混入

v1/v2/v3 系列（4 張）全部沒有黑點眉、毛色偏米白。**已全部標記 REJECT。**

---

## I. 下一步 LoRA 訓練建議

### 先訓誰：**Nova**

理由：本機生圖唯一 0/4 全失的項目，也是整條產線脫離雲端的唯一障礙。而且 Nova 的 5 張素材**全部乾淨**，處理成本最低。

### 現有素材夠不夠

| | 現有可用 | 一般建議 | 判斷 |
|---|---|---|---|
| Nova | **5 張** | 15–30 張 | 🟡 偏少，但**寧缺勿濫** |
| Taco | **4 張**（+4 張處理後） | 15–30 張 | 🟡 同上 |

> **Dataset Quality > Dataset Quantity。**
> 不為了湊數把低品質圖塞進去——5 張乾淨的資料勝過 25 張混入錯誤犬種、錯誤吊牌的資料。
> 實務上 SDXL 角色 LoRA 用 8–15 張高品質圖就能訓出可用結果（**此為一般經驗值，本機未實測**）。

### 補素材的三條路

| 來源 | 可行性 |
|---|---|
| 1. 現有高品質參考圖 | ✅ 已盤點完，Nova 5 張、Taco 4 張 |
| 2. 現有影片抽幀 | 🟡 可行，但都是同一客廳情境，**角度不會變多**；優點是能補「不同表情」（例如 Nova 睡覺閉眼） |
| 3. **Gemini 生成補充圖** | ✅ **主力**。目前品質最高的一批圖就是 Gemini 生的 |
| 4. 本機 workflow 生成 | ❌ **絕對禁止**——本機生 Nova 就是 0/4 |

> **所有 Gemini 生成圖必須逐張人工審查後才能進 TRAIN**，檢查項目同本文件 A/B 表格的欄位。

### 補圖優先順序（若決定補）

1. Nova pure side view（純側面）
2. Nova back view（背面）
3. Nova 張嘴／警覺表情
4. 兩隻狗的非暖窗光版本
5. Taco pure side view / back view

### 訓練前必須先完成

1. 裁出單一角色（4 張合照）
2. 遮蔽吊牌區域（4 張 REVIEW）
3. 建立 `DATASET\dog_main\` 與 `DATASET\dog_support\` 的 TRAIN/REVIEW/REJECT 三層資料夾
4. 安裝 LoRA 訓練工具（目前一個都沒有，安裝前會先提出完整分析）

**以上皆未執行。本文件僅為盤點。**
