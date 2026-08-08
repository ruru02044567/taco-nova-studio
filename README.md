# 財富密碼 — 版控說明

這個資料夾是**純本地 git repo**，沒有遠端。目的有兩個：

1. Paperclip 的 `claude_local` adapter 在啟動「有連到專案」的 issue 前會做 workspace 驗證，
   沒有 `.git` 就直接拒絕啟動（`workspace_validation_failed / missing_git_metadata`）。
2. 更重要的是**檔案救得回來**。CMP-5 和 CMP-6 兩個 agent 各自寫了同一個檔名
   `主題提案-5支.md`，後寫的把先寫的整份蓋掉，CMP-6 的五個點子在磁碟上直接消失。
   有了版控，同樣的事再發生時 `git checkout` 一下就回來了。

> 專案內容本身請看 [`IP總覽.md`](IP總覽.md)。這份 README 只講版控。

---

## ⚠️ Clone 一份 **不會**拿到全部檔案

以下東西**不在版控裡**（見 [`.gitignore`](.gitignore)），只存在賢賢桌面的這份原始資料夾：

| 沒進版控的東西 | 檔案 | 為什麼 |
| --- | --- | --- |
| 成片與草稿影片 | `taco-*.mp4`、`video-01/clips/*.mp4` | 約 65 MB，可從 Veo／本機重跑產生 |
| 影片縮圖 | `*-thumb.jpg` | 從 mp4 抽格的衍生檔，隨時能再抽 |
| 頻道視覺 | `channel-avatar.jpg`、`channel-banner.png` | 已上傳到 YouTube，那邊有一份 |

**要完整素材請直接拿原始資料夾，不要只 clone。**

## ✅ 定裝照是例外，有進版控

`character/` 底下的 `taco-ref-*.jpg`、`duo-scene-*.jpg` **納入版控**，用
`!character/*.jpg` 從 `*.jpg` 規則反向排除出來。

理由：這九張是生成正片時餵給 Veo 的參考圖，是必要輸入。它們是 AI 生成的，
重跑不會得到同一隻 Taco —— 弄丟就是永久弄丟，不像縮圖可以再抽一次。
合計約 8.6 MB，對一個不推遠端的本地 repo 來說成本可以忽略，
而「防覆蓋、救得回來」正是這個 repo 存在的理由，最不能弄丟的檔案更該受保護。

## 進版控的東西

- 所有文件：`IP總覽.md`、`對標計畫.md`、`發布資訊-第一支.md`、`主題提案-5支.md`、
  `character/角色設定.md`、`video-01/腳本.md`、`video-01/進度.md`
- 生產用的文字資產：`video-01/prompts.txt`（Veo prompts）、`video-01/assemble.py`（組裝腳本）
- `character/` 定裝照（如上）

`video-01/output/` 是空目錄，git 不追蹤空目錄，所以它不會出現在 repo 裡。
等裡面產出檔案時再依 `.gitignore` 規則處理（`.mp4` 會被忽略）。

## git 設定備註

這台機器沒有設 global `user.name`／`user.email`，所以這個 repo 設了 repo-local 身分
`Paperclip Agent <agent@paperclip.local>`。

一開始設的是 `Paperclip Agent (Video)`，但 repo-local 設定是**所有 agent 共用**的 ——
結果 CMP-7（內容部）的 commit 也被蓋上「Video」的名字，變成張冠李戴。
所以改成中性的 `Paperclip Agent`：分不出是哪個 agent，至少不會指錯人。
要追是誰做的，看 commit message 裡的票號（`CMP-7`、`CMP-11`…）比看作者名可靠。

賢賢要換成自己的，在這個資料夾下跑：

```
git config user.name "你的名字"
git config user.email "你的信箱"
```

另外 `core.autocrlf` 在這個 repo 明確設成 `false`，確保檔案在版控裡跟磁碟上**逐位元組相同**，
不會有換行被偷改的問題（現有檔案全部是 LF）。
