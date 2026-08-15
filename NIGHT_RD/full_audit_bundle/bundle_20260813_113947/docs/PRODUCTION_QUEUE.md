# PRODUCTION_QUEUE — 發片佇列

> 建立 2026-08-13｜**Production 不停。R&D 不得阻塞這條線。**

## 🔴 立即可發（不需要生成，已完成）

### D4S1 — 麵粉片
```
檔案   待審核\d4s1-麵粉-最終版.mp4
標題   Taco Detonated A Whole Bag Of Flour And Only His Eyes Still Work 😂💨
規格   1080×1920 / 24fps / 10.09 秒 / AAC / -14.7 LUFS
來源   Gemini 場景圖 → 本機 Wan 2.2 i2v → 自製音效
做完   2026-08-11 20:54
```
**PUBLISH_GATE：九項全過 → PASS**

狀態卡在 `awaiting_review=True, approved=False`。
**這支只差賢賢一句「發」，不需要任何生成工作。**

發布指令：
```powershell
python auto\pipeline.py ok d4s1
```
（或 `python auto\publish_video.py <video> <title.txt> <desc.txt>`）

⚠️ 排程 `TacoNova-Pipeline` 目前是停用狀態，要自動發要先
`Enable-ScheduledTask -TaskName "TacoNova-Pipeline"`。

---

## 📋 待生成佇列（排程順序）

| 順位 | 代號 | 標題 | 需要 Nova？ | 建議工作流 |
|---|---|---|---|---|
| 1 | **D6S1** | Taco Tries To Nose An Entire Plant Back Into Its Pot 🪴 | ✅ 睡在旁邊 | Gemini 場景圖 → 本機 i2v |
| 2 | D7S1 | Taco Threw Dad's Slipper Into A Glowing Portal 🟣 | 待確認 | 同上 |
| 3 | D8S1 | Taco Is Glued To The Floor By Pink Slime 💗 | 待確認 | 同上 |
| 4 | D9S1 | Taco Wiped Up The Red Wine And Made It 3x Worse 🍷 | ✅ | 同上（技術驗收片已存在，不可發） |

排程上總共 19 支，已發 6 支（含 2 支重複），還有 13 支未發。

## D6S1（下一支要生的）

**一句話**：一盆大盆栽倒在地上，Taco 拚命用鼻子把土推回盆裡，結果推得更開。
**viralScore**：8

**分鏡（Shot List）**

| Shot | 內容 | 角色 | 長度 |
|---|---|---|---|
| 001 | 災難現場：盆栽倒地、土呈扇形噴開，Taco 站在土中央、鼻子沾滿泥，故作無辜往旁邊看；Nova 睡在土堆另一側 | Taco ＋ Nova | 5 秒 |
| 002 | Taco 低頭用鼻子推土，土反而被推得更散 | Taco（可單狗） | 5 秒 |

**Shot 001 需要 Nova 入鏡** → 依 `BEST_KNOWN_WORKFLOW`，必須走 Gemini 場景圖。
**Shot 002 可以純本機**（單狗 ＋ Taco LoRA 0.35）。

## 每週節奏

- 目標：**每週至少 1 支**
- 現有素材：D4S1 立即可發 → 本週的量已經有了
- D6S1 生成後 → 下週的量

## 發布前必跑

1. `PUBLISH_GATE.md` 九項檢查
2. 抽 6 幀 contact sheet
3. 角色驗收（Nova 犬種／Taco 黑點眉＋吊牌無字）
4. 通過才進 `待審核\`，等賢賢點頭
