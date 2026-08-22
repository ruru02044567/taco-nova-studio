# TOCO／Taco & Nova 產線開工必讀（2026-08-18 建立，2026-08-22 生效）

這是每天在動的影片產線。開工先做兩件事：讀 `C:\AI-COMPANY\99_INBOX\懸念清單.md`（未完成事項）、跑 `python auto\pipeline.py status`（產線現狀）。

## 真相排序（衝突時上面贏）

1. `auto\state.json` — 發布與審核狀態的唯一真相
2. `auto\pipeline.py` 等程式碼本身
3. `接手-下次開機.md` — 活文件
4. 其他 .md（**`導覽.md` 已失準，別照它做**）

## 產線的真實形狀（2026-08-18 接線後）

- `pipeline.py tick` 做前半：到期判斷 → plan_model 分流 → 場景圖 → Wan I2V → 送 `待審核\`（無聲原片）。
- **後半一鍵組裝**：`python auto\finish_video.py <key> [--boomerang]` → 剪輯＋音效（優先用
  `sfx\mix_{key}.py` 專屬配方，**每支片一檔是定案作法**，沒有就先寫）＋ preflight，
  成功後 state 的 video 自動指向有聲成片並送待審。
- 發布：`pipeline.py ok <key>` **內建 preflight 硬閘門**（無聲片、靜音軌、黑名單、重複發布會被擋）。
- 發布後：`python auto\sync_ledger.py`（公司帳本）；隔天 `python auto\fetch_views.py`（觀看數）。
- 排程 `TacoNova-Pipeline`／`TacoNova-DailyReport` 自 8/11 起停用（CEO 裁示），一切人工觸發。
- 生圖主路徑是 Gemini 遙控（要 Edge 活著），fallback 本機 SDXL；FLUX 走 `auto\gen_scene_flux.py`
  （黑點眉大概率要後補，補繪尚未腳本化）。LoRA 已訓練**但未接線**（等 CEO 決策）。

## 鐵律

1. **發布前一定先給賢賢過目**，不例外。發布走 `pipeline.py ok <key>`。
2. 全本機生成，Veo 已移除；本機做不到就改劇本，不換模型。
3. Taco 黑點眉是招牌：兩顆、圓形、對稱、等大。場景圖畫錯就重生場景圖，影片救不回。
4. prompt 沒寫到的角色一定崩——六個崩壞規律見 `LOCAL-AI-STUDIO\PRODUCTION\`。
5. 審片標準：`LOCAL-AI-STUDIO\PRODUCTION\PUBLISH_GATE.md`（10 條＋角色驗收清單）。
6. 發布後跑 `python auto\sync_ledger.py` 讓公司帳本自動更新。

## 公司歸屬

本專案屬 AI-COMPANY（文件在 `C:\AI-COMPANY\02_PROJECTS\TOCO\`，二手資料）。STOP 規則八條適用，最常用：資料離開本機要 CEO 確認。
