# D6S1 六版迭代紀錄 ＋ 可重用 PROMPT 模板

> 2026-08-13 下午｜從 v01 崩到 v06，每一版只動一個變數，找出本機 Wan 2.2 的行為規律

## 一、賢賢看片後的三點回饋（2026-08-13 約 15:00）

看的是 **v06 有聲版**。判斷「效果有進步」，但點出三個問題：

| # | 問題 | 我的判斷 | gate 抓不抓得到 |
|---|---|---|---|
| 1 | **聲音怪怪的** | 直接套用 d4s1 的 `flour_shake` 配方，時間軸是為「麵粉甩身」設計的，事件點對不上 v06 的動作；而且那配方裡有「粉塵撲落」的乾粉音，這支是濕土不是麵粉 | ❌ **抓不到**——gate 只驗畫面 |
| 2 | **盆栽打倒怪怪的** | 蕨葉叢與根球在視覺上是分離的（葉子躺在盆口左下、根球留在盆內），不像同一株被整個拔出來。**story 子代理也獨立提出同一點** | 🟡 部分——規則 6 只驗「災難主體在不在」，不驗「合不合理」 |
| 3 | **影格率／幀數怪怪的** | Wan 2.2 Turbo 只跑 4 步、121 幀，時間連續性本來就弱；加上這一版動作幾乎靜止，慢推鏡頭會放大抖動感 | ❌ **抓不到**——gate 抽 11 張靜態幀，完全看不到時間軸 |

> ### 🔴 這暴露了 PUBLISH_GATE 的兩個結構性盲區
>
> **盲區一：聲音沒有任何一條規則在管。** 十條規則全部是畫面。
> **盲區二：時間連續性沒有規則在管。** gate 的方法論是「抽幀 → 逐幀比對」，
> 規則 10 雖然要求看「動作連起來的意思」，但那是語意層，不是流暢度層。
> 幀與幀之間的抖動、跳格、速度不自然，抽樣 11 張永遠看不出來。
>
> **賢賢用肉眼三秒就抓到兩個 gate 跑了 68 萬 token 也抓不到的問題。**
> 這證實「發布前一定要賢賢過目」這條鐵律不能拿掉，gate 是過濾器不是替代品。

---

## 二、六版迭代：每一版改什麼、修好什麼

| 版本 | 唯一變數 | 結果 | 修好了 | 新問題 |
|---|---|---|---|---|
| **v01** | 原始批次 prompt | REGENERATE | — | 規則 1/3/4/5/6/8＋體型全掛。Taco 融解成長吻大型犬 |
| **v02** | 套 d4s1 成功寫法 | REGENERATE | 規則 4、6、體型、不再融解成大型犬 | 憑空第三條前腿、頸背融解、項圈飄到背上、**規則 10 從 PASS 退步成 FAIL** |
| **v03** | 動作改全身甩身＋`all four paws planted` | 自篩淘汰 | **腿修好**（兩條前腿）、項圈回脖子 | 泥面具糊掉整張臉 → 吻部變扁臉 |
| **v04** | **改場景圖**（拿掉泥面具） | 自篩淘汰 | **臉修好**（全程尖細吻） | 耳朵扭成彎曲角狀物 |
| **v05** | 鎖死耳朵 | REGENERATE | **耳朵修好**、Taco 全項達標 | Nova 的臉在 t3.0 後糊掉、黑點眉變逗號 |
| **v06** | 補 Nova 臉部鎖定＋黑點眉形狀 | gate 審核中 | **Nova 臉修好**（片尾臉罩／長吻／黑鼻／眼瞼線全在） | 賢賢指出聲音／盆栽／幀數 |
| **v07** | （無紀錄，生完就沒下文） | 未送審 | — | 中段項圈脹成藍塊、狗一路走向鏡頭 |
| **v08** | ⚠️ **一次改三個**：場景圖 v2＋加強鎖定句＋steps 6 | REGENERATE | 盆栽合理性（v2 場景圖有效） | **黑點增生成 4–5 顆**、後段臉崩、仍走向鏡頭 |

### v08 的兩個方法論教訓（2026-08-14）

**① 我違反了「每版只動一個變數」。** 場景圖、prompt、steps 三個一起改，
失敗之後完全無法歸因 —— 不知道是哪一個害的，等於整輪白跑。這是這份文件
自己在第二節寫下的紀律，卻在下一輪就被我打破。

**② 否定句擋不住走位，而且強調會招來增生。**
- 加 `never walks, never moves toward the camera, never comes closer to the lens`
  → 狗照走不誤。呼應已知規律：**Wan 2.2 對否定式動作指令無效**。
- 為了鎖黑點寫了大量 `two black dots ... perfectly circular ...` 的描述
  → 反而從 2 顆增生到 4–5 顆。**在 prompt 裡反覆強調一個視覺元素，模型會多畫幾個。**
  v06 的寫法比較克制，反而穩。

**修正方向**：回到 v06 的 prompt 與 steps 4，只換場景圖這一個變數（= v09）。

### 關鍵因果（每一條都是實測出來的，不是推論）

1. **10 秒劇本塞進 5 秒 → 角色融解。** v01 的 prompt 有 8 個動作、時間軸標到 `[00:08-00:10]`，
   但影片只有 5.04 秒。模型加速壓縮，角色就散了。
2. **局部單肢動作 → 多長一條腿。** v02 讓 Taco「用一隻前爪撥土」，t1.5–t3.0 就長出第三條前腿。
   換成全身同步動作（甩身）＋ `all four paws staying planted` 之後完全消失。
3. **場景圖的缺陷會被 i2v 放大。** v01–v03 吻部一直變扁，根因是 scenePrompt 寫了
   `muzzle caked in wet dark soil up to the cheeks like a dirty mask`——泥面具在動的過程中糊開，吃掉整張臉。
   **改場景圖比改 video prompt 有效得多。**
4. **prompt 沒寫到的角色就會崩。** v05 對 Nova 只寫「睡著、閉眼、不准醒」，
   一句臉部特徵都沒有 → 她的臉在 t3.0 後糊成白團。補上臉部鎖定後立刻修好。
5. **鎖定句加太多會把動作也鎖死。** v05 加了一堆 `never...`，結果 story 子代理報告
   「全身抖一下根本沒生出來，5 秒變成一張慢推的照片」。要在鎖定與動作之間拿捏。

---

## 三、可重用的 PROMPT 模板（本機 Wan 2.2 i2v 5 秒單段）

這是六版試出來的，套到其他 13 支未發布的片子上應該都適用。

### 骨架（照抄）

```
Static locked-off camera at floor level, eye-level pet angle, 9:16, camera never moves.
<主角完整外觀描述> ; and <配角完整外觀描述，包含臉部特徵>.
In a <場景>.
[00:00-00:01] Already done and settled: <災難的既成狀態>；主角站定，head held high and level,
              snout well clear of the floor, staring straight into the lens; only his eyes move.
[00:01-00:03] <唯一的一個全身同步動作>，all four paws staying planted flat on the floor.
[00:03-00:05] 動作收束，抬頭看鏡頭定格。
Throughout the entire shot: <所有鎖定句>
```

### 必備鎖定句（缺一個就會崩掉對應的部位）

| 鎖定句 | 防的是 |
|---|---|
| `camera never moves` | 鏡頭亂飄 |
| **時間軸只寫到 `[00:03-00:05]`** | **劇本超長 → 角色融解（v01 的死因）** |
| `head held high and level, snout well clear of the floor, mouth stays closed` | 低頭埋進災難物 → 臉變形＋規則 10 風險 |
| **`all four paws staying planted flat on the floor, never lifting a paw, never reaching out`** | **憑空第三條腿（v02 的死因）** |
| `he has exactly four legs and four paws at all times` | 同上，雙保險 |
| `his two oversized pointy ears stay upright, triangular, straight and rigid — never fold, flap, bend, curl, droop, or twist into any curved or horn-like shape` | **耳朵扭成角狀物（v04 的死因）** |
| `two black dots ... both perfectly circular with no tail, no hook, no comma shape, no streak and no smear ... including the very last frame` | **黑點眉退化成逗號（v05 的死因）** |
| `stays tiny throughout, roughly one third the size of the husky, and never grows` | 主角中途漲大 → 體型倍率不合格 |
| `his neck, shoulders and back keep visible short white fur texture and never turn into a smooth featureless shape` | 頸背融解成光滑白團塊 |
| **配角完整臉部鎖定**（見下） | **配角的臉在後段糊掉（v05 的死因）** |
| `the leafy green plant and its root ball stay clearly visible ... the whole time` | 災難主體被抹掉（v01 的死因） |

### 配角（Nova）臉部鎖定 — v06 驗證有效

```
The sleeping husky's face stays fully rendered and structurally intact in every single frame
including the very last one — her dark grey face mask, her long wedge-shaped muzzle,
her sharp black nose and her thin dark closed eyelid lines all stay crisp and clearly readable,
her head never shrinks, never blurs, never softens into a featureless white ball,
never loses its muzzle, and her face mask never fades away.
```

### 場景圖 prompt 的鐵則

- ❌ **絕對不要寫**「泥／粉／醬蓋住臉」這類描述（`caked up to the cheeks like a dirty mask`）
- ✅ 髒污證據放在**身體**：`dark soil smeared across his chest and down all four legs, both front paws caked`
- ✅ 臉要明確寫乾淨：`His face is CLEAN: a narrow tapered chihuahua snout, small black nose, clearly defined jawline, no mud mask`
- ✅ 場景圖一次生 3 張挑最好的（每張只要 30 秒，是整條產線最便宜的一步）
  - 挑選標準：主角距離適中（臉夠大細節保得住）、黑點眉對稱、配角完整入鏡

---

## 四、待辦（下一輪要處理的）

1. **音效重做** — 不能再直接套 `flour_shake`。要為「濕土」重配，並對齊 v06 實際的動作時間點
2. **盆栽的合理性** — 場景圖 prompt 要讓「葉子＋根球＋盆」看起來是同一株被整個拔出來，
   而不是三個分開的物件
3. **幀數／流暢度** — 這是 Wan 2.2 Turbo 4 步的天花板。可試的方向：
   提高 steps（會變慢）、或讓動作幅度再大一點蓋過抖動感。**尚未驗證，是推的**
4. **給 gate 補兩條規則** — 規則 11（聲音與畫面對齊）、規則 12（時間連續性／流暢度）。
   但這兩條子代理用靜態幀判不了，得靠人看或另想方法
