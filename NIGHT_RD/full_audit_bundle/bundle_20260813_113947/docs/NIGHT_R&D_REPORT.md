# NIGHT R&D REPORT — D4S1 原地甩身動作

## 1. 測試時間

2026-08-13　01:34 – 02:05（約 31 分鐘，GPU 實際運算 13.8 分鐘）

## 2. 測試 seeds

`424242` / `424243` / `424244` — **三顆，沒有超額**

## 3. 使用的 Workflow

```
起始圖   auto/clips/d4s1_scene.jpg（原場景圖，未重生）
生成     auto/make_video_local_5s.py（ComfyUI API）
模型     wan22_5b_turbo_Q4_K_M.gguf ＋ wan2.2_vae ＋ umt5_xxl_fp8
解析度   704×1280 → 輸出 1080×1920
Steps    4
CFG      1.0
Sampler  euler / simple
長度     121 幀 @ 24fps = 5.04 秒
ControlNet / IP-Adapter：本階段未使用（i2v 直接吃起始圖）
```

**唯一變數：seed（v1/v2）與 prompt 版本（v3）。** 其餘全部固定。

## 4. 使用的 Prompt

| 版本 | 檔案 | 差異 |
|---|---|---|
| V1 | `auto/clips/d4s1_video_shake.txt` | 白天版。已解決吐白粉，但甩身演成往前走 |
| **V2** | `NIGHT_RD/prompt_V2.txt` | 加入「四腳釘在同兩塊地板」「與鏡頭距離不變」「佔畫面比例不變」「純繞自身軸旋轉」 |
| **V3** | `NIGHT_RD/prompt_V3.txt` | V2 再加「最後一格與第一格同位置同大小」的終點鎖定 ＋「扭身是全片唯一動作」 |

## 5–6. 每個 seed 的結果與分數

### v1 — seed 424242 / prompt V2 → **REJECT**

| 項目 | 配分 | 得分 |
|---|---|---|
| A Taco Identity | 20 | 16 |
| B Nova Identity | 10 | 10 |
| C Scene Stability | 10 | 10 |
| D Full-body Shake | 25 | **3** |
| E Flour From Fur | 15 | 2 |
| F No Mouth Flour | 10 | 10 |
| G Motion Quality | 5 | 3 |
| H Overall Story | 5 | 2 |
| **總分** | 100 | **56** |

**淘汰原因：向前撲。** 客觀量測（rembg 前景 bbox）：
狗在畫面中的高度變化 **60%**（676→1055 px），中心 x 從 534 移到 759。
3.0–3.5 秒明顯衝向鏡頭。

### v2 — seed 424243 / prompt V2 → ★ **最佳**

| 項目 | 配分 | 得分 |
|---|---|---|
| A Taco Identity | 20 | 17 |
| B Nova Identity | 10 | 10 |
| C Scene Stability | 10 | 10 |
| D Full-body Shake | 25 | **17** |
| E Flour From Fur | 15 | 5 |
| F No Mouth Flour | 10 | 10 |
| G Motion Quality | 5 | 4 |
| H Overall Story | 5 | 4 |
| **總分** | 100 | **77** |

**1.5–2.5 秒有真正的軀幹左右扭轉**，頭與耳自然跟隨。
客觀量測：高度變化 **20%**（三版最小），頭頂位置範圍 0.13–0.20（最穩定）。
未觸發任何淘汰條件。

### v3 — seed 424244 / prompt V3 → **REJECT**

| 項目 | 配分 | 得分 |
|---|---|---|
| A Taco Identity | 20 | 17 |
| B Nova Identity | 10 | 10 |
| C Scene Stability | 10 | 10 |
| D Full-body Shake | 25 | 12 |
| E Flour From Fur | 15 | 4 |
| F No Mouth Flour | 10 | 8 |
| G Motion Quality | 5 | 3 |
| H Overall Story | 5 | 3 |
| **總分** | 100 | **67** |

**淘汰原因：鼻子靠近地面。** 1.5–2.5 秒頭部明顯下低。
客觀量測：頭頂位置降到 **0.25**（v2 最低只到 0.20），高度變化 32%。

> ⚠️ 這是個反直覺的結果：**V3 的終點鎖定反而讓模型改用「低頭」來製造扭身**。
> 把位移的自由度鎖死，它就從別的軸找動作——這條要記著。

## 7. 最佳 seed

**424243**（prompt V2）

## 8. 最佳影片路徑

```
LOCAL-AI-STUDIO\NIGHT_RD\BEST_d4s1_shake_seed424243.mp4
（同檔另存 d4s1_shake_night_v2.mp4）
```

## 9. Contact Sheet 路徑

```
三版並排  LOCAL-AI-STUDIO\NIGHT_RD\sheets\_COMPARE_3版.jpg
最佳版    LOCAL-AI-STUDIO\NIGHT_RD\sheets\SHEET_v2_seed424243.jpg
v1        sheets\SHEET_v1_seed424242.jpg
v3        sheets\SHEET_v3_seed424244.jpg
```

## 10. 是否通過 Publish Gate

| 規則 | v2 判定 |
|---|---|
| 1 主角身份 | ✅ 純白、大立耳、藍項圈＋銀吊牌 |
| 2 動物種類 | ✅ Nova 灰白哈士奇，全程睡著未醒未移動 |
| 3 不換臉 | ✅ |
| 4 場景不漂移 | ✅ 沙發／植栽／紙袋位置一致 |
| 5 動作不變形 | ✅ |
| 6 故事看得懂 | 🟡 甩身成立，但粉塵抖落不明顯 |
| 7 第一秒 | ✅ |
| 8 無 AI 災難 | ✅ |
| 9 直式 | ✅ 1080×1920 / 24fps / 5.04 秒 |
| **10 非預期讀法** | ✅ **通過**——頭全程抬高，無嘴部粉塵 |

> ### 判定：**PASS（可發），但 E 項偏弱**

比白天版（`待審核\d4s1-麵粉-甩身v5.mp4`）**只有改善沒有退化**：
甩身從「沒有」變成「有」，前進位移從明顯變成輕微。

## 11. 仍存在的問題

1. **粉塵沒有明顯從毛上甩落**（E 項 5/15）。
   麵粉主要仍躺在地上，看不到「白粉爆開」那一下。
   推測是起始圖裡狗身上的麵粉附著感不夠強，i2v 沒有東西可以甩。**未驗證。**
2. **甩身幅度中等**，不是劇烈的 full-body shake。
3. **後半段仍有 20% 的輕微位移**，沒有做到完全定位。
4. **黑點眉在動態幀較淡**，只在靜止幀清楚。

## 12. 下一步建議

**優先順序由高到低：**

1. **改起始圖，不是改 prompt。**
   E 項弱的根因可能在起始圖——狗身上的麵粉層不夠厚，模型沒東西可甩。
   下一輪應該先生一張「Taco 全身厚厚覆蓋麵粉」的起始圖，再跑同一組 prompt V2 + seed 424243。
   **這是唯一還沒試過的變數。**

2. **不要再往 prompt 加約束。**
   V2 → V3 的實驗證明：鎖死一個自由度，模型會從另一個軸生出問題（鎖位移 → 改低頭）。
   V2 是目前的甜蜜點。

3. **不要再抽 seed。** 三顆已經看出模式：位移與低頭是 prompt 層級的傾向，不是 seed 運氣。

4. 若要直接發布，v2 已經可發——E 項弱只影響「精彩度」，不影響合規與角色一致性。

---

## 檔案保護確認

- ✅ 沒有刪除任何舊影片
- ✅ 沒有覆蓋原始影片（全部新檔名 `d4s1_shake_night_v1/v2/v3`）
- ✅ 沒有修改正式產線腳本（`make_video_local_5s.py` 的 `--seed` 是白天賢賢核准後加的，本夜未再改動）
- ✅ 沒有開始 LoRA 訓練
- ✅ 沒有下載新模型
- ✅ 沒有使用雲端 GPU 或付費 API
- ✅ 三顆 seed 用完即停
