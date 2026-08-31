# TOCO／Taco & Nova 產線開工必讀（2026-08-18 建立，2026-08-22 生效）

這是每天在動的影片產線。開工先做兩件事：讀 `C:\AI-COMPANY\99_INBOX\懸念清單.md`（未完成事項）、跑 `python auto\pipeline.py status`（產線現狀）。

## 真相排序（衝突時上面贏）

1. `auto\state.json` — 發布與審核狀態的唯一真相
2. `character\角色聖經.json` — **角色長相的唯一真相**（見下方鐵律 3）
3. `auto\pipeline.py` 等程式碼本身
4. `接手-下次開機.md` — 活文件
5. 其他 .md（**`導覽.md` 已失準，別照它做**）

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
2. 全本機生成，Veo 已移除；本機做不到 → **先換本機引擎、多抽淘汰**（人物演戲＝H3、
   風景動物姿勢控制＝Wan，互換試拍），還不行才改劇本——改劇本＝改成品長相，必須先問賢賢。
   （2026-08-28 賢賢核准修訂：舊版「改劇本不換模型」與運動量閘門互相矛盾；H3 跑通後解除。
   plan_model 的能力表只描述 Wan，被它判 BLOCKED 的動作戲一律先丟 H3 試拍。）
3. **角色只看 `character\角色聖經.json` 的 canonical_prompt，其他 75 份檔案提到角色一律不算數。**
   2026-08-31 賢賢一句話定案：**「一隻吉娃娃，眉毛上面有兩個黑色的毛」**——白色吉娃娃＋
   眼睛上方兩塊深色毛斑＋藍項圈銀吊牌＋大立耳。就這樣，不要再加條件、不要數顆數。
   ⚠️ `character\角色設定.md` 與 `LOCAL-AI-STUDIO\DATASET_STATUS.md` 已加註「不算數」橫幅——
   那兩份裡的「焦糖耳斑」「REJECT 清單」都是歷史，2026-08-31 前的 AI 讀錯過，別再踩。
   **角色固定的機制是「同一張起始圖」，不是 prompt 寫得多詳細**（H3 沒有記憶，每次從零開始）。
4. prompt 沒寫到的角色一定崩——六個崩壞規律見 `LOCAL-AI-STUDIO\PRODUCTION\`。
5. 審片標準：`LOCAL-AI-STUDIO\PRODUCTION\PUBLISH_GATE.md`（10 條＋角色驗收清單）。
6. 發布後跑 `python auto\sync_ledger.py` 讓公司帳本自動更新。

## 公司歸屬

本專案屬 AI-COMPANY（文件在 `C:\AI-COMPANY\02_PROJECTS\TOCO\`，二手資料）。STOP 規則八條適用，最常用：資料離開本機要 CEO 確認。
