# FAILURE_DATABASE — 失敗案例資料庫

> 建立日期：2026-08-12｜本檔案為**既有失敗紀錄的整理**，非新測試
> 原始來源：`本機生圖測試\獨立驗證-圖片評分.md`、`待審核\審片-畫面品質.md`、`02-技術選型\本機生圖-實測報告.md`、`auto\state.json`

## 失敗分類與發生率

| 代碼 | 失敗類型 | 發生率 | 嚴重度 | 已知根因 |
|---|---|---|---|---|
| `WRONG_ANIMAL` | 配角變成別的品種 | **4/4 生圖** | 🔴 致命 | IP-Adapter 用合照，特徵被平均 |
| `WRONG_PROPORTION` | 體型差不足（1.3× vs 應 2.5–3×） | **4/4 生圖** | 🔴 致命 | ControlNet 深度圖把相對大小一起鎖死 |
| `MISSING_MARK` | 黑點眉消失 | **4/4 生圖**；Veo、Pixverse 也失敗 | 🔴 致命 | 小面積特徵，IP-Adapter 0.65 撈不回 |
| `WRONG_FUR` | Taco 毛色被染成奶油／淺褐 | 2/4 生圖 | 🟠 高 | cfg 拉高會削弱 IP-Adapter 的角色鎖 |
| `OBJECT_DRIFT` | 地板液體／散落物走鐘 | 3/4 生圖 | 🟠 高 | DA3 深度圖把攤平液體誤判成立體物 |
| `BACKGROUND_DRIFT` | 地毯材質每個 seed 不同 | 4/4 生圖 | 🟠 高 | 由 prompt 管，prompt 管不住 |
| `PHANTOM_LIMB` | 麵粉堆裡脫離身體的狗爪 | 1 次（D4S1，持續 7 秒） | 🟠 高 | 結塊被模型讀成爪子 |
| `NOISE_ARTIFACT` | 滿地紅點／灰色砂礫 | 3/4 生圖 | 🟡 中 | — |
| `TEXTURE_ERROR` | Nova 頭頂長青苔感 | 1 次（D4S1，第 180 幀後） | 🟡 中 | — |
| `UNSOURCED_EFFECT` | 無來源的粉塵爆發 | 1 次（D4S1，6.0–6.9 秒） | 🟡 中 | — |
| `MATERIAL_BLUR` | 中段材質變糊成塊面 | 1 次（D4S1，第 50–70 幀） | 🟡 中 | i2v 中段畫質衰減 |
| `COLOR_NOISE` | 單幀紫色色斑 | 1 次（D4S1 第 58 幀） | 🟢 低 | 一閃而過 |
| `WEAK_FIRST_FRAME` | 首幀角色沒看鏡頭 | 1 次（D4S1） | 🟠 高 | Shorts 無封面，第一格權重最高 |
| `HALLUCINATED_PUPPY` | 畫面出現幻覺幼犬 | 1 次（`d4s1-麵粉-有聲.mp4` 舊版） | 🔴 致命 | 已用 v4 最終版取代，舊版標記勿發 |

---

## 三條已驗證的通則

### 1. 文字不是變數
改 prompt 措辭（`stain` / `soaked liquid` / `puddle`）三種寫法生出來**幾乎一模一樣**。
→ 當某個東西一直錯，**先懷疑圖像條件（深度圖／參考圖），不要一直改字**。

### 2. 負面詞擋不住道具漂移，只有正向詞有效
麵粉結塊被讀成狗爪，寫 `no clumps` 在 negative 無效；寫 `loose powder, smooth drifts` 在 positive 才有效。

### 3. 分清楚「誰在穩、誰在飄」
- **穩住的**（4/4 一致）＝ ControlNet 管的：站位、姿勢、鏡頭距離、視線方向
- **全飄的**（每 seed 一樣）＝ prompt 管的：品種、地毯、酒漬

> **「每次壞在不同地方」就是抽獎的定義**，不是「有一個固定的小毛病」。

---

## 一個必須避免的致命陷阱

**AI 生成的失敗品絕對不能回流訓練集。**

本機生圖那 4 個 seed 的成品，配角全部生錯（狐狸犬／博美）。若拿去訓練 Nova LoRA，等於教模型「哈士奇長得像狐狸犬」，錯誤會自我強化且再也救不回來。

---

## 記錄格式（之後每次失敗照這個填）

```
日期：
檔案：
失敗代碼：
Prompt：
Model / LoRA：
Seed / Steps / CFG / Resolution：
現象描述：
判定：REJECT / REGENERATE / REVISION / APPROVED
推測根因：
下一次的對策：
```
