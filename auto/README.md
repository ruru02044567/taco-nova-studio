# 七天自動產線（不靠 Claude 對話活著）

## 一句話

Windows 工作排程器每 20 分鐘叫醒 `pipeline.py`，它自己看 `schedule.json` 該做哪一支，做完寫進 `state.json`。
**電腦關機沒關係**——排程器設了「錯過就開機後盡快補跑」，開機後幾分鐘內會自動接上進度。

## 檔案

| 檔案 | 做什麼 |
|---|---|
| `schedule.json` | 七天 21 支的題材、prompt、標題、說明（唯一要改的檔） |
| `state.json` | 進度記錄，哪支生好了、哪支發布了、網址是什麼 |
| `schedule.json` | 七天 21 支的題材、prompt、標題、說明（唯一要改的檔） |
| `pipeline.py` | 主控：判斷該做哪一支 → 生圖 → 生片 → **送待審**（不再自動發布） |
| `make_scene.py` | Gemini 生場景圖（免費，不佔影片額度） |
| `make_video_cloud.py` | Veo 生 10 秒片，**發布用的片只能出自這支** |
| `make_video_local.py` | 本機 ComfyUI 704×1280，**只能當草稿，不接進產線** |
| `publish_video.py` | 上傳＋合規設定＋公開發布（只有核准過才會被呼叫） |
| `pipeline.log` | 每一步的流水帳，出事看這個 |
| `..\待審核\` | 生好等賢賢過目的片子＋三格畫面截圖＋標題說明 |

## 發布前一定要人工過目

賢賢定的鐵律：**發之前一定先給賢賢看過。**

> **2026-08-11 更新：解除「只能用 Veo」的限制。**
> 原本的鐵律是「本機 ComfyUI 的片子不准發布，發布只能用 Veo」，
> 起因是 8/8 那天 Veo 額度掛掉、產線自動退回本機生成並直接發布，
> 結果 D1S1 後段憑空多長出第二隻哈士奇、Taco 的黑點眉和藍項圈也不見了。
>
> **現在改走本機生圖、本機生成。** 這條限制解除的理由有三個：
> 1. Veo 免費額度已耗盡（`You're out of videos for now`），等不到就等於停產
> 2. 8/11 實測證明**畫質不是流量瓶頸** —— 9,882 觀看那支就是本機生的，
>    而 198 觀看那支是純 Veo。真正的差異在文案（見 `desc_spec.py`）
> 3. 當初出事的根因不是「本機」，是**沒有驗收就自動發布**。
>    現在有七項回歸驗收表 ＋ 三方獨立審片，那個根因已經被堵住了
>
> **沒有解除的部分**：發布前一定要人工過目，這條不變。

新流程：

```
場景圖(Gemini，失敗自動退本機) → 影片(本機 Wan 2.2) → 七項驗收 → 待審核\
                                                          → 賢賢看過 → ok → 發布
```

- 有片子在待審時，產線**不會**再往下生新的，避免囤一堆沒人看的片。
- 想看待審的片：`python pipeline.py review`，或直接開專案下的 `待審核\` 資料夾，
  裡面每支都有 `xxx-畫面.jpg`（三格截圖），不用真的播影片就知道畫面對不對。

## 發布時段（台北時間）

| slot | 台北 | 美東 |
|---|---|---|
| 1 | 08:00 | 20:00 美國晚間黃金 |
| 2 | 20:00 | 08:00 美國早晨通勤 |
| 3 | 00:00 | 12:00 美國午休 |

**錯過怎麼辦**：晚 6 小時內就照原時段補；超過 6 小時直接立刻補發，不硬等下一輪。
規則寫在 `pipeline.py` 的 `LATE_TOLERANCE_H`。

## 常用指令

```powershell
cd "C:\Users\TUF Gaming\Desktop\我的專案\財富密碼\auto"
python pipeline.py status   # 看 21 支的進度與已發布網址
python pipeline.py plan     # 看現在有哪些到期待辦
python pipeline.py tick     # 手動催一次（排程器平常自己會做）
python pipeline.py review   # 有哪些片在等我過目
python pipeline.py ok       # 看過覺得可以 → 立刻發布（可加 d1s3 指定哪支）
python pipeline.py no       # 看過覺得不行 → 砍掉重生（可加 d1s3 指定哪支）
```

排程器本身：

```powershell
Get-ScheduledTask -TaskName "TacoNova-Pipeline"        # 看狀態
Start-ScheduledTask -TaskName "TacoNova-Pipeline"      # 立刻跑一次
Disable-ScheduledTask -TaskName "TacoNova-Pipeline"    # 暫停整條產線
Enable-ScheduledTask  -TaskName "TacoNova-Pipeline"    # 恢復
```

## 三個已知限制（老實說）

1. **電腦完全關機時什麼都不會跑**——沒有雲端主機，開機才補。想要真正 24 小時不斷，得把產線搬到雲端主機，那是另一筆錢和另一次施工。
2. **Veo 夜間（約 20:00 後）常抽風**（錯誤 4／1155／「請檢查網路連線」）。以前會退回本機版硬發，現在改成等一小時重試，最多 8 次；等於那個時段可能整晚生不出片，寧可不發也不發爛的。額度台北 15:00 重置。
3. **遙控用的 Edge 視窗不能關**：腳本會自己開（開在螢幕外 2000,2000），看到它別手動關掉。

## 同一時間只能有一支腳本操作瀏覽器（2026-08-10 新增）

排程器每 20 分鐘跑一次，人也會在對話視窗裡手動跑同一批腳本。兩邊開頭都會
`goto('gemini.google.com/app')` 開新對話，**排程器一跑就把手動那支正在等 Veo 生片的
對話沖掉**，兩邊一起失敗——而且症狀偽裝成「Veo 自己斷線」，非常難查。

`browser_lock.py` 負責卡位：`make_video_cloud` / `make_scene` / `make_scene_ref` /
`veo_resume` 開頭都會先搶鎖，搶不到就 **exit 8＝讓路**（不是失敗，`pipeline.py`
不會累計 `veo_fails`）。鎖檔是 `auto\.browser.lock`，30 分鐘沒更新視為過期可被蓋掉。

要專心手動作業，就先 `Disable-ScheduledTask -TaskName "TacoNova-Pipeline"`，
**做完一定要 Enable 回來**。
