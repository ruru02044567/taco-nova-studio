# experiments/ — 多鏡產線實驗區

> 建立：2026-08-21｜**這個資料夾完全獨立於正式產線。整個刪掉，產線一點事都沒有。**

## 規矩

1. **不改正式腳本。** 生片一律 `subprocess` 呼叫 `auto\make_video_local_5s.py`，不複製它的邏輯。
   （複製一份改成「實驗版」是最常見的自欺：實驗過了、產線沒過，查半天才發現兩邊 workflow 早就不一樣。）
2. **不下載模型、不安裝套件。** 只用系統 Python 3.13 已有的 numpy / PIL / cv2 / scipy / skimage。
3. **每一組把完整設定寫成 JSON 落地**（`out\*.json`），可回溯、可重跑、可比較。
4. **輸出存在就跳過**，除非 `--force`。一支 6.4 分鐘，斷了不該從頭再燒。
5. **代理指標一律標 ⚠️。** 量不到的東西不要假裝量得到。

## 目錄

```
_lib\
  measure.py    客觀量測：接縫幀差、anchor 保真度、亮度／色彩漂移、光流抖動、
                銳利度、前景面積穩定度、對照圖。單獨跑：python _lib\measure.py <影片>
  runner.py     跑批器：呼叫 make_video_local_5s、計時、輪詢 nvidia-smi 記 VRAM 峰值

multi_frame_chain\   anchor 1/13/17/21/25 單變數掃描（吃 GPU，約 32 分鐘）
prompt_ab\           I2V prompt 最小化 A/B/B2（吃 GPU，約 13 分鐘）
hidden_cut\          10 種藏切 × 2 情境（不吃 GPU，約 2 分鐘）

report.py            彙整三個 results.json → _docs\EXPERIMENT_REPORT.md

_docs\
  CURRENT_PIPELINE_MAP.md        目前真實執行流程（唯讀盤點結果）
  MULTI_SHOT_PIPELINE_DESIGN.md  多鏡產線設計提案
  SHOT_STATE_SCHEMA.md           鏡頭狀態資料結構提案
  HIDDEN_CUT_PLAYBOOK.md         藏切策略與實測排名
  SCORE_VIDEO_V2_DESIGN.md       段間自審設計提案
  EXPERIMENT_REPORT.md           ← report.py 自動生成，不要手改
```

## 跑法

```powershell
# 不吃顯卡的先跑
python experiments\hidden_cut\run.py

# 吃顯卡的（會搶 studio_lock，一次只能一個）
python experiments\multi_frame_chain\run.py
python experiments\prompt_ab\run.py

# 彙整
python experiments\report.py
```

## ⚠️ 產線互斥

吃 GPU 的實驗會透過 `make_video_local_5s.py` 搶 `auto\.studio.lock`。
排程器每 20 分鐘會叫 `pipeline.py tick`，如果剛好有片要生就會排隊 ——
這是對的，這台只有一張顯卡。查誰在用：`python auto\studio_lock.py status`。

## 這些文件的地位

`_docs\` 裡除了 `EXPERIMENT_REPORT.md` 之外**全部是提案，尚未生效**。
故意放在這裡而不是 `LOCAL-AI-STUDIO\PRODUCTION\` —— 那個資料夾裡的東西是
已經在執法的規則，混進提案會讓值班視窗把「還在驗的想法」當成「已定的規矩」執行。
提案被賢賢採納之後才搬過去。
