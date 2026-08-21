# CURRENT_PIPELINE_MAP — 目前真實執行流程

> 建立：2026-08-21｜方法：唯讀盤點，讀完 `auto/` 全部 30 支腳本 ＋ 5 份 PRODUCTION 文件 ＋ state/schedule/policy 三個資料檔
> **這份寫的是「程式碼實際會走的路」，不是文件宣稱的路。** 兩者有三處不一致，本文標了 ⚠️。

---

## 一、一句話版

排程器每 20 分鐘叫 `pipeline.py tick` → 生一張場景圖 → **生一段 5.04 秒影片** → 丟進 `待審核\` 停住等人。
剩下的（多鏡組裝、音效、成片、發布）**全部是人在對話裡手動叫的**，沒有自動化。

---

## 二、四層架構與真實接線

```
【排程層】Windows 工作排程器（每 20 分鐘）
    └─ pipeline.py tick
         ├─ schedule.json（19 支的劇本／標題／prompt）
         └─ state.json（每支走到哪一步）

【生成層】pipeline.py cmd_tick()  ← 唯一自動化的一段
    ├─ plan_model.py            讀 model_policy.json，判「本機拍不拍得出來」→ BLOCKED 就不拍
    ├─ check_prompt.py --day N  六崩壞規律健檢（⚠️ 只預警，不擋拍）
    ├─ ensure_edge()            Edge 起不來就這輪不做
    ├─ gen_scene_flux.py        FLUX schnell 704x1280，約 45 秒／張
    │    └─ 失敗 → gen_scene_local.py（SDXL＋ControlNet＋IP-Adapter）
    │    └─ (可選，手動) postfx.py  黑點眉補繪 v3 ＋ 相機缺陷（顆粒／色差／JPEG 痕）
    ├─ make_video_local_5s.py   ★ 影片唯一生成點，見第三節
    └─ to_review()              複製到 待審核\，state[key].awaiting_review = True
                                ⛔ 產線到此為止，自動化結束

【組裝層】⚠️ 沒有通用工具，每支片一支硬寫的腳本
    ├─ _build_d10_v2.py   d10 專用（時間軸寫死在原始碼裡）
    ├─ _build_d12.py      d12 專用
    └─ _build_d10.py      舊版（雙狗時代）
    做的事：S1 切成兩段 → 從 S1 自己 crop 出兩顆插入鏡 → 接 S2 → concat 5 段 → noise+unsharp

【成片層】finish_video.py <key>   ← 人手動叫
    ├─ frame_gate.has_pass(src)   ⛔ 硬閘門：沒有逐幀憑證不給出片（憑證綁影片 md5）
    ├─ [--boomerang]              正播＋反播
    ├─ sfx\mix_{key}.py           每支片一檔的專屬音效配方（沒有就要明示 --recipe）
    ├─ preflight.py               ⛔ 硬閘門 6 項
    ├─ score_video.py             ⛔ 硬閘門 10 項全過
    └─ → 待審核\{key}-有聲.mp4

【發布層】pipeline.py ok <key> --by-xianxian
    └─ publish_video.py（playwright 遙控 Edge）
       ⛔ 無 approved_by=賢賢 一律拒發（8/20 D11 擅自發布事故後加的牙齒）

【互斥】studio_lock.py — .studio.lock，45 分鐘 stale，可重入（STUDIO_LOCK_OWNER 環境變數）
       這台只有一張顯卡，兩個視窗同時生片只會互踩
```

---

## 三、ComfyUI 工作流（`make_video_local_5s.py` 組出來的節點圖）

```
 1 UnetLoaderGGUF          wan22_5b_turbo_Q4_K_M.gguf
 2 ModelSamplingSD3        shift = 8.0
 3 CLIPLoader              umt5_xxl_fp8_e4m3fn_scaled.safetensors (type=wan)
 4 CLIPTextEncode          正面 prompt
 5 CLIPTextEncode          負面 prompt（寫死在程式裡，含幻覺幼犬／粉塵／雙狗等歷史事故的封印）
 6 VAELoader               wan2.2_vae.safetensors

 ── 起始條件，兩條路 ─────────────────────────────
 (A) 單張場景圖  12 LoadImage ─────────────────────────┐
 (B) 多幀接龍    12 LoadVideo → 13 GetVideoComponents  │
                              → 14 ImageFromBatch      │
                                 (batch_index=-N, length=N)
                                                        ▼
 7 Wan22ImageToVideoLatent   704x1280, length=121, start_image ← 上面二選一
 8 KSampler                  steps 8, cfg 1.0, euler + simple, denoise 1.0
 9 VAEDecodeTiled            tile 256 / overlap 64 / temporal 64 / overlap 8
10 CreateVideo               fps 24
11 SaveVideo                 h264 mp4
```

輸出**兩份**：
- `out.mp4` — 1080x1920（lanczos 放大到 1080x1964 再裁 1080x1920），給人看與發布用
- `out.raw704.mp4` — 原生 704x1280，**下一段接龍只能餵這個**（餵成品等於接一張被縮放又換過構圖的圖）

---

## 四、賢賢問的十個問題，逐題回答

### A. 現在「5 秒影片」是在哪裡生成？

`auto\make_video_local_5s.py`，走 ComfyUI HTTP API（`127.0.0.1:8188`），實際算圖在
`C:\Users\TUF Gaming\ai-video-local\ComfyUI`。產線的呼叫點只有一處：`pipeline.py:474`。
`make_video_cloud.py`（Veo）程式碼還在，但 8/16 起自動流程**沒有任何路徑會走到它**，
留著是當手動救急工具。

### B. 第二段影片現在如何取得第一段的結尾？

**分兩條路，答案不一樣：**

| | 自動產線 | 手動 |
|---|---|---|
| 有沒有第二段 | **沒有。一支片只生一段 5.04 秒** | 有 |
| 怎麼取結尾 | 不適用 | `--continue <前段.mp4>`，程式自動改用旁邊的 `.raw704.mp4`，用 ffmpeg `trim=start_frame=總格數−N` 切出末 N 格、`crf 0` 無損寫成小 mp4 丟進 `ComfyUI/input` |

⚠️ **這是目前最大的架構落差**：自動化只做得出 5 秒，12–15 秒全靠人手動接。

### C. 現在是不是只餵最後一張 PNG？

**不是了**（8/20 起）。但要分清楚三種情況：

| 情況 | 餵什麼 | 誰在用 |
|---|---|---|
| 自動產線 | FLUX 新生的**場景圖**（不是前段末幀）→ LoadImage | 每一支片 |
| 手動單段重生 | 指定的一張圖 → LoadImage | 偶爾 |
| 手動接龍 | 前段末 N 格影片 → LoadVideo | D10S2、D12S2、兩次實驗 |

### D. 哪一個節點負責 LoadImage？

節點 **`"12"`**。單張圖模式 `class_type = LoadImage`；
接龍模式時節點 12 換成 `LoadVideo`，後面多接 `13 GetVideoComponents` 與
`14 ImageFromBatch(batch_index = −N, length = N)`，最後由節點 14 餵給
節點 7 `Wan22ImageToVideoLatent` 的 `start_image`。

負的 `batch_index` 在 ComfyUI 0.30.0 的 `ImageFromBatch` 裡會 `+= batch 長度`，
所以 `−N` 就是「最後 N 格」。

### E. 如何把前段最後 13 / 17 / 21 / 25 frames 餵進下一段？

**已經做好了，不用新寫**：

```
python auto\make_video_local_5s.py - <prompt.txt> <out.mp4> \
       --continue auto\clips\<前段>.raw704.mp4 --anchor 17
```

程式強制 `anchor % 4 == 1`（Wan 潛在空間時間軸 4 倍壓縮）且 `anchor < length`。
`--join <長鏡.mp4>` 會順便照正確接法（前段砍尾 ✅，不是新段砍頭 ❌）接成一支連續長鏡。

原理：`Wan22ImageToVideoLatent` 會把餵進去那幾格的 latent mask 成 0，
KSampler 完全不動它們 —— 接縫在數學上就是同一段畫面，不是「接得像」。

### F. 現有 finish_video.py 能不能直接接受 3 段影片？

**不能。** `--src` 只吃單一檔案路徑，內部也沒有任何 concat 邏輯。
3 段必須先組成一支再交給它。而組裝目前是每支片手寫一支 `_build_dNN.py`。

不過 **finish_video 本身不需要改** —— 它接手的是「一支完整無聲影片」，
上游是 1 段還是 5 段對它沒差別。要新增的是它前面那一塊。

### G. 現有 score_video 能不能評估多段影片？

**可以，而且它本來就是為 12–15 秒多鏡片寫的。**
片長 12.1–14.9s、鏡頭數 1–7、平均鏡長 ≥1.9s、主鏡 ≥3.8s ——
D9S1（12.17s）、D11S1（13.00s）、D12S1（12.13s）三支多段片都是它驗過的。

**但它有一整類盲區：段與段「之間」的問題一項都沒管。**

| 多段片會出的問題 | score_video 有沒有在看 |
|---|---|
| 段間色彩／亮度跳變 | ❌ 沒有 |
| 角色跨段漂移（毛色、體型、黑點眉） | ❌ 沒有 |
| 接縫可見度 | ❌ 沒有（scene detect 只數刀數，不評刀口醜不醜） |
| 道具跨段瞬移 | ❌ 沒有 |
| 段內亮度單調漂移 | ❌ 沒有 |

→ 這正是 `score_video_v2` 要補的清單。**現行版本不動**。

### H. publish gate 是否能維持不變？

**可以，一行都不用改。**

- `preflight.py` 六項（檔案／有聲軌／不靜音／3–60s／直式／黑名單）與段數無關
- `PUBLISH_GATE.md` 十二條本來就是「全片」層級的視覺規則
- `frame_gate.py` 抽 2fps 逐幀，段數多只是要填的表變長，機制不變
- `publish_video.py` 的 `--by-xianxian` 親核機制與段數無關

要加的是**新規則**（段間連戲），不是改舊規則。這點很重要 ——
現行 gate 是一次次事故打出來的牙齒，動它的風險遠大於收益。

### I. 哪些地方必須新增模組？

| # | 缺什麼 | 為什麼是硬缺口 |
|---|---|---|
| 1 | **通用多鏡組裝器** | 現在每支片一支 `_build_dNN.py`，時間軸與裁切座標寫死在原始碼。做第 20 支要寫第 20 支腳本 |
| 2 | **藏切模組** | 現在只有一招（從自己畫面 crop 插入鏡），且寫死在每支 build 裡，不能重用、不能換 |
| 3 | **段間統一調色** | 完全沒有。實測 d10s1 段內亮度就漂了 **−9.81**，多段接起來一定看得到跳變 |
| 4 | **SHOT 狀態表** | 世界狀態（蛋破了幾顆、腳掌沾到沒）全靠 prompt 文字口耳相傳，模型自己猜 |
| 5 | **score_video_v2 段間項** | 見 G |
| 6 | **pipeline.py 的多鏡編排** | `cmd_tick` 寫死「生一段就送審」，沒有 shot 迴圈 |

### J. 哪些地方完全不用動？

`make_video_local_5s.py`（接龍已完備，含接縫診斷）、`preflight.py`、`frame_gate.py`、
`publish_video.py`、`sfx\mix*.py`、`studio_lock.py`、`plan_model.py`、`model_policy.json`、
`rejected.json`、`postfx.py`、`gen_scene_flux.py`、`check_prompt.py`、`score_video.py`。

**這 13 支一行都不要碰。** 新東西全部加在「生成」與「成片」中間那段真空裡。

---

## 五、盤點時發現的三處「文件說的 ≠ 程式做的」

| # | 文件怎麼寫 | 實際 | 影響 |
|---|---|---|---|
| 1 | `LOCAL_VIDEO_ENGINE_ROADMAP.md` 第 17、119、169 行：「多鏡頭**絕不接龍**」「接龍第二段必崩」 | 8/20–8/21 兩輪實測推翻。接龍**擋得住**身體拉伸與增生肢體 | 高。值班視窗照這份文件做決策會直接排除正確方案 |
| 2 | `pipeline.py:463` 註解：「為什麼單段：8/9 三次實測接龍第二段每次都崩」 | 同上，已過時 | 中 |
| 3 | `_還原點-20260816-全本機改造.md` | 記憶檔已標「還原點文件本身寫錯，照它還原會錯」 | 高，但已知 |

⚠️ **本輪不改這三個檔**（唯讀階段不修正式文件）。列在這裡是要賢賢知道有這個雷。

---

## 六、現況數字（本輪實測，不是引用）

| 項目 | 值 | 來源 |
|---|---|---|
| GPU | RTX 5050 Laptop 8 GB（8151 MiB） | `nvidia-smi` |
| 生成一段 121 格 | 6.4–6.9 分鐘 | 本輪 anchor 掃描 |
| VRAM 峰值 | 6332–6364 MiB（餘 ~1.8 GB） | 本輪 anchor 掃描 |
| 段內亮度漂移 | d10s1：−9.81（頭 176.35 → 尾 166.54） | `measure.py` |
| 接縫幀差（8/20 量） | 正常跳動 1.58 / ✅ 接法 2.68 / ❌ 接法 8.58 / 硬接 24.56 | 檔頭註解 |
| 已發布片長 | d9s1 12.17s、d11s1 13.00s、d12s1 12.13s | ffprobe |
| 現有多段片組裝方式 | 手寫 `_build_dNN.py`，2 支 | 檔案清單 |

---

## 七、檔案關係圖（誰讀誰、誰寫誰）

```
schedule.json ──讀──► pipeline.py ──讀寫──► state.json
model_policy.json ──讀──► plan_model.py ──寫──► state.json
                              ▲
                              └── pipeline.py 呼叫

pipeline.py ──subprocess──► gen_scene_flux.py ──► clips\{key}_scene.jpg
            ──subprocess──► make_video_local_5s.py ──► clips\{key}.mp4
                                                  └──► clips\{key}.raw704.mp4  ← 接龍餵這個

（人手動）  _build_dNN.py ──► clips\{key}-cut.mp4
（人手動）  finish_video.py ──► frame_gate.py（憑證 _gate\pass_<md5>）
                          ──► sfx\mix_{key}.py ──► clips\{key}-final.mp4
                          ──► preflight.py ⛔
                          ──► score_video.py ⛔
                          ──► 待審核\{key}-有聲.mp4 ＋ 改寫 state[key].video

（賢賢核可）pipeline.py ok <key> --by-xianxian ──► publish_video.py ──► YouTube
                                              ──► rejected.json（拒發時）
```
