# 開拍前 prompt 模板

> **每支片開拍前讀這一份就好，不要去讀 G-Brain 那五份 AI 影片筆記（96 KB）。**
> 這份是從那五份萃取出來的，只留「對我們這條產線真的有用」的部分，
> 並且標明哪些是我們自己驗過的、哪些還是別人環境的假設。
>
> 我們的產線：Gemini 生場景圖（雲端）→ 本機 ComfyUI Wan 2.2 兩段接龍 i2v → 自製音效 → −14 LUFS。
> 原始五份留在 `.claude\G-Brain\02-環境\`，出問題查表用，平常不要打開。

---

## ① 直接貼的字串

### 角色記號（Gemini 場景圖用，放 prompt 最前面）

```
EXACT 2 IDENTICAL MARKINGS — NO MORE, NO FEWER: two small solid black round dots
on his forehead, one directly above each eye, perfectly symmetrical, exactly the
same size, each perfectly round with clean crisp edges. They are round dots,
not eyebrow lines, not curved strokes, not arched brows.
```

✅ **今晚實測有效。** 前半的「EXACT N ＋計數表頭」來自知識庫；
後半三個 `not` 是我們自己踩出來的 —— 原本寫 `like little eyebrows`，
Gemini 就真的畫成一邊粗黑弧線、一邊小圓點。

⚠️ **後半那三個 `not` 只對 Gemini 生圖有效，本機 Wan 的負面詞無效。**
知識庫有三份都叫你「不要寫否定句」，那是 Seedance 的結論，別照做。

### 道具鎖定（i2v 用）

```
The <道具> stays gripped in his teeth throughout, visible in every frame — it does
not disappear, change shape, or change color. The set contains only what the
reference image shows — no added furniture, rooms, or geography beyond the reference.
```

⚠️ 知識庫建議，**沒驗過**。但對得上我們已知的 Wan 道具漂移坑（手上的東西會憑空消失），
而且今晚 D5 那句「叼著坐墊拖過地毯」一句鎖定都沒寫，純粹是運氣好沒中。

### 焦段（雙狗同框時）

```
35mm equivalent, F5.6, deep focus — both dogs equally sharp
```

⚠️ 沒驗過，但這是攝影物理不是模型行為，風險低。
今晚 D5 寫的是 `shallow depth of field`，等於主動把 Nova 的表情推進失焦區。
（不過本機生成實際上做不出真景深，所以今晚沒真的害到。）

---

## ② 禁用詞 → 替代詞

| 不要寫 | 改寫成 | 證據 |
|---|---|---|
| `like little eyebrows`（任何「像什麼」的比喻） | `solid round dots, same size`（寫形狀＋寫不是什麼） | ✅ 今晚實測 |
| `For the first beat... Then he...`（時間節拍） | 一段只寫**一個連續動作**，節奏在剪輯做 | ✅ 今晚實測 |
| `holds completely still` | `stays braced, ribcage rising with one slow breath, one ear flicking` | ⚠️ 沒驗 |
| `tiny` / `large`（相對大小） | `about one third the husky's body length`（綁錨點） | ⚠️ 沒驗 |
| `At 0s: ... At 1s: ...` | 寫「意圖＋結果」，讓模型自己補中間 | ✅ 今晚實測（同第 2 條） |

---

## ③ 開拍前自檢六項

1. **一段只有一個動作嗎？** 5 秒扛不動兩個拍點。
2. **外觀描述有沒有洩漏到動作段？** 身分（毛色／黑點／項圈）集中在最前面，
   動作段一個字都不要再提 —— 模型處理動作時重讀臉部描述會讓臉變形。⚠️ 沒驗，但兩段接龍時風險最高。
3. **道具鎖定句寫了嗎？**
4. **選題角色演得出來嗎？** 白狗不能演「被白色覆蓋」（麵粉片就是栽在這）。
   深色物質才是 Taco 的題材：可可粉、泥巴、墨水、煤灰、岩漿。
5. **Nova 有沒有自己的視線和動作？** 只寫「躺在沙發上」會變人偶。
   給她一個收尾反應（抬頭、眨眼、翻身）就是現成的笑點句號。
6. **首幀單格成立嗎？** Shorts 沒有封面，第一格就是全部。
   要能一眼讀出一個問句（「地板怎麼變岩漿了」），不能只呈現「事後」。

---

## ④ 生完之後量三個數字

```powershell
$env:PYTHONIOENCODING="utf-8"
python auto\momentum.py 待審核\<片子>.mp4
```

| 指標 | 目標 | 怎麼看 |
|---|---|---|
| **響度** | **−14 LUFS** | d3s1 是 −19.2 → 只有 34 觀看。低 5 dB 是純技術性失血 |
| **LRA**（響度範圍） | 越低越好 | 爆款只有 **1.4 LU**。畫面可以留白，**聲音不行** |
| **動量峰值/基線** | **≥ 3 倍** | 爆款 22.8、D5 3.0、被否決的 D4 2.5。低於 3 就是「很忙但什麼都沒發生」 |

⚠️ Wan 不吃時間節拍，動量對比只能在剪輯階段做：
開頭 0.7 秒 `trim` ＋ `setpts=PTS*2.6` 放慢成 1.8 秒，1.4 倍 → 3.2 倍。
比整格凍住好，因為背景還在動，不會讓人以為影片壞掉。

---

## 這份文件的證據強度

- ✅ 標記的是**我們自己在這台機器上驗證過的**
- ⚠️ 標記的來自 Higgsfield《Hell Grind》製作系統（為 Seedance 寫的），**一條都沒在 Wan 上驗過**
- **下一支片一次只試一兩條 ⚠️ 的**，一口氣全上，生壞了不知道是哪條的錯

*2026-08-11 建立。來源五份原文在 `.claude\G-Brain\02-環境\AI影片*.md`。*
