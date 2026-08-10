# YouTube 動物爆款 Shorts 研究

抓取日期：**2026-08-10**
範圍：觀看數 5000 萬以上、經逐支驗證的直式 Shorts，共 **861 支**（貓 221、狗 195、貓狗同框 7、其他動物 332、動畫角色 58、無動物 48）。

## 要看資料，開這三個其中一個

| 想做什麼 | 開這個 |
| --- | --- |
| 用瀏覽器逛榜單、篩選排序 | 雙擊 `shorts-report.html`（離線可用，不需連網） |
| 手機上看、或分享給別人 | https://claude.ai/code/artifact/1d240fa0-1400-4007-a5e3-b7acbfceaed5 |
| 用 Excel 自己排序、做表 | `爆款Shorts清單.csv`（UTF-8 BOM，Excel 直接開不會亂碼） |

網頁版和 HTML 檔內容一樣。網址那份預設是私人的，要給別人看得從頁面的分享選單開權限。
在 Claude Code 網頁版可以到 `claude.ai/code/artifacts` 找回所有發布過的頁面。

## 檔案

- `shorts-report.html` — 互動榜單，可依物種／題材／AI 生成篩選，依觀看數、按讚率、上傳日、片長、頻道訂閱數排序
- `爆款Shorts清單.csv` — 同樣 861 支的試算表版
- `dataset.json` — 完整原始欄位（含影片 id、縮圖網址、留言數）
- `scripts/` — 重跑用的腳本與中間檔

## 主要發現

1. **AI 生成能爆，但換不到認同**：AI 生成貓狗觀看中位數 8900 萬，真實拍攝 9600 萬，幾乎打平；按讚率 AI 只有 0.71%，真拍 1.31%。
2. **越短衝觀看、越長換互動**：10 秒內觀看中位 9500 萬／讚率 0.57%；60 秒以上觀看 7600 萬／讚率 2.35%。
3. **訂閱數不是門檻**：423 支貓狗爆款有 61 支來自訂閱不到 100 萬的頻道，最猛的只有 25.6 萬訂閱衝出 7.8 億觀看。
4. **單一角色會複利**：Sonyakisa8 TT 靠一隻叫 Sonya 的貓，22 支上榜、合計 55.9 億觀看，標題常常只有一個 emoji 加 `#cat #cats`。
5. **題材**：搞笑意外 154 支（36%）數量最多但讚率只有 1.19%；知識科普 3.2%、挑戰實驗 2.08% 才是高互動題材。
6. **榜單很新**：2025 年上傳 155 支、2026 年至今 48 支，兩年就占近一半。

## 怎麼重跑（想更新數字或改門檻時）

跟 Claude 說「**重跑爆款榜**」就行，或自己照順序跑：

```bash
cd scripts
bash crawl.sh          # 掃 86 組關鍵字（raw/ 已有的會自動跳過，想全部重抓就先清空 raw/）
python filter.py       # 篩出 5000 萬以上、3 分鐘內 → candidates.json
python verify2.py      # 判定真 Shorts → isshorts.json
python report2.py      # 初步分類 → final.json
python enrich.py       # oEmbed 補正確標題 → oembed.json
python enrich2.py      # 補上傳日／按讚數／訂閱數 → stats.json
python merge.py        # 合併 → dataset.json + CSV
python build_html.py   # 產生網頁
```

改門檻：`filter.py` 裡的 `THRESHOLD`。加關鍵字：`crawl.sh` 裡的 `KEYWORDS`。
物種與題材分類是靠 AI 逐支判讀標題與 hashtag（`merge.py` 讀取分類結果），重跑時這步要請 Claude 重新派工。

## 三個技術要點（免 YouTube API key）

1. **按觀看數排序**：yt-dlp 直接吃搜尋 URL，`sp=CAMSAhgB` = 觀看數降冪 + 只要 4 分鐘內短片。不加這個參數會按相關性排序，撈不到爆款。
2. **判定真 Shorts**：打 `youtube.com/shorts/<id>`，200 = 真 Shorts，303 = 橫式影片被轉址。這步濾掉了 304 支偽裝成短片的兒歌 MV 和音樂錄影帶。
3. **繞過 bot 檢查**：並行超過 6 就會被擋。用 `--extractor-args "youtube:player_client=ios" --ignore-no-formats-error` 可以繼續抓 metadata。

## 已知限制

- 物種與題材由 AI 判讀標題、頻道名、hashtag，非人工核對，少數可能誤判。
- 觀看數為 2026-08-10 擷取當下數值。
- 66 支影片關閉了按讚顯示，按讚率為空。
- 涵蓋範圍是「YouTube 搜尋前 120 名 × 86 組關鍵字」，不是 YouTube 全站普查——冷門語言或沒有明顯動物關鍵字的爆款可能漏掉。
