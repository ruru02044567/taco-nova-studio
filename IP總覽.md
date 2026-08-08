# 財富密碼 — 吉娃娃 × 哈士奇 IP 專案

> 2026-08-06 立項。目標：把機歪吉娃娃 Taco ＋ 哈士奇搭檔做成跨平台 IP。
> YouTube Shorts 先行測流量 → 之後 IG Reels／臉書／抖音串聯。

## 角色（正式版）

- **Taco**：全白吉娃娃、眼睛上兩個黑點眉（頻道辨識物）、藍項圈銀牌。人設＝機歪到極致的小屁孩，保持眼神接觸做壞事
- **哈士奇**（名字暫定 Nova）：灰白哈士奇、淡藍眼。人設＝浮誇反應擔當、受害者兼告狀仔
- 定裝照都在 `character\`：v5-max（極限機歪）、v4a（瞇眼迷因笑）、v4b（睜眼齜牙）、duo-scene-remote（同框）
- 設計沿革與舊版（焦糖耳斑＋Bruno）封存在 `character\角色設定.md`

## 生產線（實測可用）

| 用途 | 工具 | 成本 |
|---|---|---|
| 定裝照／場景圖 | Google Gemini 生圖 | 免費不佔額度 |
| 正式影片（有音效） | Google Veo（每天約 2 支/波，台北 15:00 重置） | 免費 |
| 草稿／量產實驗 | 本機 ComfyUI（`ai-video-local\`，場景圖當起始格） | 免費無限 |

標準流程：Gemini 生同框場景圖 → 雲端 Veo 生正式片（附圖鎖角色）／本機 i2v 生草稿 → ffmpeg 組裝。
⚠ ffmpeg 遇中文路徑會靜默失敗：影片後製一律在 `ai-video-local\` 做完再把成品複製進來。

生成腳本在 `C:\Users\TUF Gaming\ai-video-local\`（`gen_troll10.py`、`gen_final_local.py`），
開頭都有一行 `PROJECT = ...\我的專案\財富密碼`——**這個資料夾若再搬家，只要改那一行**，
且素材不見時腳本會直接報錯講明白，不會白跑。

## 文案格式（招牌）

每支影片說明固定用 **Taco 官方聲明體**：條列式無恥自白 ＋ 甩鍋哈士奇 ＋ 問觀眾問題收尾。
範本（首支實際使用）：
```
official statement from Taco:
1. yes i did it 💅
2. no i am not sorry
3. the remote had it coming 💀
the husky is NOT a reliable witness. do not trust him 🙄
what did YOUR dog destroy today? 👇
```

## 平台佈局

| 平台 | 狀態 |
|---|---|
| YouTube | ✅ 首支已發（暫掛 Mochi & Boss）；Taco & Nova 專屬頻道等驗證生效 |
| IG Reels／臉書／抖音 | 📅 YouTube 測出爆款公式後開，同素材多發 |

## 現有成品

- `taco-troll-10s-veo-v2.mp4`：**已發布** https://youtube.com/shorts/b8E_mWTPgb8（物理 bug 修正版）
- `taco-troll-10s-veo.mp4`：初版（遙控器會飛回桌上，留存對照）
- `taco-troll-10s-local.mp4`：本機無聲版
- `taco-plant-draft.mp4`：20 秒打翻盆栽草稿（舊臉時期）
- `video-01\`：黑洞片（舊設計，shot 1-3 已入庫，發不發等賢賢決定）
