# D9S1_VERIFY — 技術驗收片

**STATUS = TEST ONLY，不發布。不要刪除。**

日期：2026-08-13
工作流：**ControlNet ＋ IP-Adapter，No LoRA**
起始圖：A/B/C/D 對照的 C 組
影片：Wan 2.2 i2v 單段 5 秒（1080×1920 / 24fps / 121 幀 / 5.5 MB）

## 結果

| 項目 | 判定 |
|---|---|
| Taco | ✅ PASS |
| Scene | ✅ PASS |
| Motion | ✅ PASS |
| Wine Stain | ✅ PASS |
| **Nova Breed** | ❌ **FAIL — 生成為棕白博美／狐狸犬** |

## 它證明了什麼

ControlNet ＋ IP-Adapter 能穩定做到：
1080×1920、24fps、約 5 秒、場景不漂移、Taco 身份穩定、
災難主體（紅酒漬）敘事清楚、動作連貫。

## 它證明不了什麼

**Nova 的身份特徵表示不足。** 這不是 seed 運氣問題——
A/B/C/D 四組實測，不掛 LoRA 時配角 4/4 全部生成錯誤犬種。

→ 解法在 `R&D_QUEUE.md` 的 Nova V2 資料集，不在抽 seed。
