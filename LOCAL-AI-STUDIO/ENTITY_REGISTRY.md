# ENTITY_REGISTRY — 實體清冊

> 盤點日期：2026-08-12｜來源：`character\角色設定.md`、`auto\schedule.json`（19 支）、已發布影片、審片報告

## 總覽

| 類型 | 數量 | 說明 |
|---|---|---|
| HUMAN | **0** | D7 標題出現「Dad's Slipper」，但 Dad 從未實際出鏡 |
| ANIMAL | **2 現役 + 1 封存** | Taco、Nova；Bruno 已停用 |
| CREATURE | **0** | 黑洞、傳送門屬特效不屬生物 |
| ROBOT | 0 | — |
| VEHICLE | 0 | — |
| OBJECT | **19+** | 每集一個核心道具，見下 |
| LOCATION | **2** | 客廳（主）、廚房 |

---

## ANIMAL / dog

### `dog_main` — Taco 🔴 最高優先

| 欄位 | 內容 |
|---|---|
| Entity ID | `dog_main` |
| Name | Taco |
| Type | ANIMAL / dog / chihuahua |
| Appearance | **純白短毛**吉娃娃，超大圓深棕眼、誇張大尖立耳 |
| **辨識物 1** | **額頭兩顆黑點眉**（頻道招牌，左顆略圓、右顆略斜） |
| **辨識物 2** | 細藍色項圈 + 小銀色橢圓吊牌 |
| Expression | 瞇眼壞笑、眼神 sly cunning glint，小軍師感，**不要無辜呆萌臉** |
| Personality | 好奇闖禍 → 連環掩蓋越蓋越糟 → 被抓包裝無辜 |
| Reference Images | `character\taco_face.png`、`taco-ref-v5-max.jpg`、`taco-ref-v4a-meme.jpg`、`taco-ref-v4b-glare.jpg` 等 7 張 |
| Dataset Path | ⚠️ 尚未建立 |
| LoRA Path | ❌ 無 |
| Consistency Score | 生圖 **2/4**（毛色會被染成奶白／淺褐）；影片 **通過**（D4S1 審片） |
| Version | v5（2026-08-06 大改版後） |

**已知失效點**：黑點眉在本機生圖 **4/4 全失**，Veo 與 Pixverse 也都掉。IP-Adapter weight 0.65 撈不回這種小面積特徵。

### `dog_support` — Nova 🔴 **第一個該訓練的對象**

| 欄位 | 內容 |
|---|---|
| Entity ID | `dog_support` |
| Name | Nova（2026-08-08 定名，頻道 handle `@tacoandnova` 已寫死，不可改） |
| Type | ANIMAL / dog / husky |
| Appearance | **大型灰白西伯利亞哈士奇**，灰黑臉罩、倒 V 額紋 |
| **辨識物** | **淺藍色眼睛**、標準哈士奇臉罩 |
| Body Proportion | **體型是 Taco 的 2.5～3 倍**（審片報告實測 D4S1 達 3～4 倍，正確） |
| Function | 浮誇反應擔當；常態是睡死的目擊者 |
| Reference Images | `character\nova_face.png`（**單獨圖只有這 1 張**）、`duo_full.png`、`duo-新臉-奸詐哈士奇×高傲吉娃娃.jpg`、`duo-scene-remote.jpg`、`duo-scene-dogbed.jpg`（合照） |
| Dataset Path | ⚠️ 尚未建立 |
| LoRA Path | ❌ 無 |
| Consistency Score | 生圖 **0/4（全失）**；影片 **通過**（因為起點是 Gemini 場景圖） |
| Version | v1 |

**已知失效點（本次 audit 最重要的一條）**：
本機生圖 4 個 seed 全部生不出哈士奇——三張變成白色狐狸犬／博美，一張變成棕紅色迷你哈士奇（Klee Kai）。

**根因**：IP-Adapter 拿的是一張「吉娃娃＋哈士奇合照」，它把**整張圖的風格**餵給整個畫面，不會分辨「這隻要像左邊、那隻要像右邊」。Nova 被 Taco 的白色短毛特徵拉走。

### `dog_archived` — Bruno（封存）

黑色拉布拉多。2026-08-06 改版後停用，僅 `video-01`（黑洞片）shot 1-3 使用舊設計。**不進入訓練資料。**

---

## LOCATION

### `loc_livingroom` — 客廳（主場景，19 支全部）

淺木地板、灰色布沙發、單人扶手椅、琴葉榕、牆上畫框、窗戶、白色長毛地毯、午後暖窗光。
手機隨手拍感、**地板高度視角**、淺景深。

⚠️ 地毯是高頻漂移項：實測 4 個 seed 生出「灰米平織／整片深紅長毛／米白織紋／米白厚長毛」四種不同結果。

### `loc_kitchen` — 廚房

暖木櫥櫃，沿用客廳風格。目前使用率低。

---

## OBJECT（19 集核心道具）

| 集 | 道具 | 生成難度 |
|---|---|---|
| D1 / D19 | 黑洞 🕳️ | 高（特效） |
| D2 | 融化的巧克力 | 中 |
| D3 | 淹水 + 小毛巾 | 中 |
| D4 | 麵粉袋（GOLD MEDAL）+ 粉塵 | ✅ 已驗證可生 |
| D5 | 岩漿地板 + 沙發抱枕 | ✅ 已驗證可生 |
| D6 | 盆栽 🪴 | 低 |
| D7 | 拖鞋 + 發光傳送門 | 高（特效） |
| D8 | 粉紅史萊姆 | 中 |
| D9 | **紅酒漬 + 打翻的酒杯** | 🔴 **抽獎級**，同參數換 seed 就走鐘 |
| D10 | 12 顆破蛋 + 毯子 | 中 |
| D11 | 黑漆 | 中 |
| D12 | 藍色腳印 | 中 |
| D13 | 枕頭 + 羽毛 | 中 |
| D14 | 金色物件 ✨ | 高 |
| D15 | 義大利麵 | 中 |
| D16 | 蜂蜜罐 | 中 |
| D17 | 爆米花（埋住 Nova） | 中 |
| D18 | 咖啡 + 筆電 | 中 |

**共通失效模式**：**攤在地板上的液體／散落物**是全系列最難的一類。
根因不在 prompt，在深度圖——DA3 會把攤平的液體誤判成有高低起伏的物體，ControlNet 忠實照做。
解法是 `clean_depth.py`（地板區域套中值濾波磨平），但仍不穩定。

受影響的集數：**D3 淹水、D8 史萊姆、D9 紅酒、D11 黑漆、D12 腳印、D16 蜂蜜、D18 咖啡 = 19 支裡有 7 支**。

---

## 自動調用對照表（文件第十九節）

| 劇本出現 | 自動調用 |
|---|---|
| Taco / 吉娃娃 / 主角 / 小狗 | `dog_main` |
| Nova / 哈士奇 / 大狗 / 配角 | `dog_support` |
| 客廳 / 家 / 沙發 / 地毯 | `loc_livingroom` |
| 廚房 | `loc_kitchen` |
