# 財富密碼 — 專案健檢摘要

**2026-08-13**｜只讀盤點，未執行任何生成／訓練／發布。
四個查證出的問題**已全部修復並實測**，見第五節。

---

## 一、專案是什麼

YouTube Shorts 頻道 **Taco & Nova**（AI 生成的吉娃娃 × 哈士奇短劇）的自動化產線。
排程共 19 支，**已發布 7 支**，待審佇列目前是空的。

```
財富密碼\
├── auto\               產線：排程、生成、發布（pipeline.py 是總控）
├── LOCAL-AI-STUDIO\    本機 AI 研發：LoRA 訓練、生圖實驗、發布門檻文件
├── 待審核\              生好等人過目的影片
└── sfx\                音效庫
```

規模：3,930 檔 / 2.0 GB。掃描 311 個 `.py/.md/.txt`（排除第三方套件），91 個有命中。

---

## 二、產線目前的能力邊界

| 環節 | 狀態 |
|---|---|
| 場景圖（第一張圖） | 🔴 **仍綁雲端 Gemini**，本機生不出通過驗收的角色 |
| 影片生成 | ✅ 本機 Wan 2.2 i2v，單段 5 秒可交付 |
| 兩段接龍 | ❌ 三次實測第二段必崩，已禁用 |
| 音效／混音 | ✅ 本機 |
| 發布 | ✅ playwright 自動化上傳 |

**唯一還離不開雲端的就是第一張場景圖。** 原因見第四節。

---

## 三、盤點腳本本身的三處修改

原始腳本在 Windows PowerShell 5.1 上跑不完整：

| 問題 | 原本 | 改成 |
|---|---|---|
| **會直接語法錯誤** | `& $Py - <<PY … PY`（Bash here-doc） | 抽成獨立檔 `scan_code.py`，用參數傳路徑 |
| **結果被淹沒** | 掃全部 1,619 個文字檔 | 排除 `_trainlib`（1,308 個第三方 peft 套件檔） |
| 無作用的一行 | `python -c "print(...)"` | 移除 |

補充：`pipeline.log` 超過 1 MB 只取最後 200 行；`.md` 報告（19 份）直接收進 `docs\`。
第一次跑還漏掉「材料包自己會被掃進去」造成重複計數，已修正重跑。

---

## 四、查證出的四個問題

### 🔴 1. `state.json` 的 `d4s1.source` 描述的是已作廢的版本

`source` 寫「兩段接龍 i2v、-14.7 LUFS」，那是 8/11 的麵粉版 —— 那支已因
**PUBLISH_GATE 規則 10**（白粉從鼻口擴散，讀起來像從嘴裡噴白粉）判 REGENERATE。
實際發布的是 8/13 的甩身版：**單段 121 幀 = 5.04 秒、seed 424243、-16.2 LUFS**。
`note` 欄有更新，`source` 欄沒有。

> **更正**：本摘要第一版把 `d5s1` 也列為同類問題，那是**誤判**。
> d5s1 是 8/11 做的，當時尚未禁用接龍，`source` 記的是歷史事實，正確，不該改。

### 🔴 2. 「哪支影片不可發」程式讀不到

`待審核\` 有 10 支 .mp4，其中 5 支是 d4s1 的不同版本，**3 支已判定不可發**
（2 支踩規則 10、1 支有幻覺幼犬）。但這些判定只寫在 `.md` 註記和人腦裡。

發布腳本吃的是命令列帶進去的檔案路徑 —— **路徑挑錯一個版本就會發到被退回的片，程式不會攔。**

（`pipeline.py` 本身有 `awaiting_review` 機制且運作正常；問題出在這 5 支是**手動流程**
產出的，檔名是描述性的，不在 pipeline 的 `to_review()` 命名規則內，等於在管理範圍外。）

### 🟡 3. 發布時用錯 Python，連續失敗兩次才成功

```
10:37  rc=1  ModuleNotFoundError: No module named 'playwright'
10:39  rc=2  FAILED: 目前作用中的頻道不是 Taco & Nova
10:48  rc=0  PUBLISHED
```

根因：`pipeline.py` 的 `run()` 用 `sys.executable` 呼叫子腳本 —— 也就是「誰跑 pipeline
就用誰」。這台機器有兩個 Python，**playwright 只裝在系統 Python，torch 只裝在 ComfyUI venv**。
用 venv 跑 pipeline，發布腳本就必炸，而 `ModuleNotFoundError` 看不出該怎麼辦。

（第二次的頻道檢查是**正常運作**——那道防呆本來就該擋，Edge 冷啟動還沒切到 Taco & Nova。）

### 🟡 4. `sync_gbrain.py` 每次發布都跑、每次都 SKIP

G-Brain 共用知識庫 8/12 已停用搬離，索引檔不存在。這支每次印一行 `SKIP:`。
不影響發布（包在 try 裡），但是每次都出現的雜訊。

---

## 五、修復結果（全部已實測）

| # | 修法 | 驗證 |
|---|---|---|
| 1 | `d4s1.source` 改成甩身版的真實做法；舊描述移到新欄位 `source_history` 保留 | JSON 合法、`pipeline.py status` 正常 |
| 2 | 新增 **`auto\rejected.json`** 黑名單；`publish_video.py` 發布前比對檔名，命中就 `rc=8` 拒發。另加**重複發布檢查**：檔案已在 `state.json` 記為 published 就拒發 | ✅ 實測拒發被退回版本、✅ 實測拒發已發布過的檔案 |
| 3 | `pipeline.py` 新增 `SYS_PY` 與 `BROWSER_SCRIPTS`，需要瀏覽器的腳本一律用系統 Python；`publish_video.py` 攔截 `ModuleNotFoundError`，明確告知該用哪個 Python（`rc=7`） | ✅ 實測用 venv 跑會給出正確指引而非堆疊 |
| 4 | `pipeline.py` 改成「G-Brain 索引檔存在才呼叫」。腳本保留，G-Brain 復原後自動恢復 | `sync_gbrain.py --dry` 仍可獨立執行 |

三道新防線都可用 `--force` 繞過（刻意要重發或 A/B 測試時）。
改動前已備份原檔到 `auto\_舊版備份\*.20260813_修四問題前.*`。

---

## 六、一個會害你貼出亂碼的陷阱

`auto\pipeline.log` 是 **UTF-8 無 BOM**。PowerShell 5.1 的 `Get-Content` 預設用 cp950 讀，
中文會全變成「鞈Ｚ郭」。

```powershell
錯：Get-Content pipeline.log -Tail 200
對：Get-Content pipeline.log -Tail 200 -Encoding UTF8
```

---

## 七、目前最大的技術卡點（供參考）

角色 **Nova（哈士奇）** 在本機生圖時**過不了發布門檻**，這是整條產線還離不開雲端的原因。
2026-08-13 的實驗（`REPORT_EXP-07_2026-08-13.md`）用 10 張匿名圖 + 10 位獨立盲評查明：

- ✅ IP-Adapter 會壓掉虹膜藍色（有 IPA 5/5 全棕、無 IPA 3/5 出現藍）
- 🔴 但拿掉只換到**異色瞳**，不是雙眼藍
- 🔴 **真正的天花板是犬種與體型**：10 張全被判成 Alaskan Klee Kai／Pomsky，
  體型只有 Taco 的 1.45–2.2 倍（門檻要求 3 倍）

下一步方向是改深度圖把體型畫大，而不是繼續調眼睛。

---

## 八、這個包裡有什麼

| 檔案 | 內容 |
|---|---|
| `AUDIT_SUMMARY.md` | 就是這份 |
| `state.json` | 發布狀態（已修正） |
| `rejected.json` | 新增的不可發黑名單 |
| `PUBLISH_GATE.md` | 發布門檻十三條 |
| `BEST_KNOWN_WORKFLOW.md` | 目前唯一能過門檻的流程 |
| `REPORT_EXP-07_2026-08-13.md` | 最新實驗結論（Nova 卡點） |
| `code_search_summary.json` | 91 個檔的關鍵字命中與反向索引 |

完整版（含 3,930 檔索引、完整日誌、19 份報告）在
`財富密碼\NIGHT_RD\full_audit_bundle\bundle_20260813_113947\`。
