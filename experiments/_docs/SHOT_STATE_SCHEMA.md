# SHOT_STATE_SCHEMA — 鏡頭狀態資料結構提案

> 建立：2026-08-21｜狀態：**只定資料結構，不改造現有系統**
> 核心原則：**不要讓 AI 自己猜世界狀態，由產線指定狀態。**

---

## 一、為什麼需要（先講清楚問題，不然這只是多一個 JSON）

現在世界狀態是**寫在 prompt 的散文裡**的：

> 「…standing dead centre on the egg-covered white bed, **both front paws stained bright yellow**,
> caught red-handed… an overturned cardboard egg carton, **about twelve smashed raw eggs**…」

這造成三個具體的失敗，全部有案可查：

| 事故 | 根因 |
|---|---|
| D11S1 標題寫熊貓、畫面是斑點狗（8/20 擅自發布事故） | 劇本改了，標題沒改。**沒有任何地方記錄「這一鏡的角色狀態是什麼」**，所以沒有東西比對得出來 |
| D10 三輪重生（雙狗 → 單狗 → 補眉） | 每一鏡的 prompt 各寫各的，S1 說「兩隻狗」S2 說「一隻狗」，程式看不出矛盾 |
| Wan 的道具漂移（記憶檔：手上的道具憑空消失、角色數量自己增生） | 第二段的 prompt 沒有「上一段結束時世界長什麼樣」這個資訊，模型只能重新想像 |

**共同點**：狀態存在散文裡 → 程式讀不到 → 沒有東西擋得住。
這跟 8/18 那條教訓一模一樣：**寫成程式的規則會擋，寫成文件的規則靠運氣。**

---

## 二、三個狀態軸

```yaml
character_state:      # 角色此刻的情緒／姿態
  - normal            # 平常站著
  - happy             # 開心、搖尾
  - scared            # 受驚、耳朵下垂、身體壓低
  - angry             # 齜牙、低吼
  - running           # 移動中
  - guilty            # ⭐ 這個頻道的招牌：心虛直視鏡頭（D10/D12 的主鏡都是這個）
  - sleeping          # 睡著（Nova 常用）

object_state:         # 劇情道具此刻的破壞程度
  - full              # 完好
  - bite_01           # 咬了一口／破了一點
  - bite_02           # 咬了兩口／破了一半
  - destroyed         # 全毀
  - spilled           # 打翻／灑出來（蛋、麵粉、油漆都走這個）

scene_state:          # 場景整體
  - normal            # 乾淨
  - messy             # 一片狼藉
  - dark              # 暗
  - wet               # 濕
  - covered           # 被東西蓋滿（麵粉、泡泡）
```

⚠️ 這幾組值是**從已發布的 13 支片倒推出來的**，不是拍腦袋定的。
不夠用就加，但**每加一個值必須指得出是哪一支片需要它** —— 否則會長成一個沒人用的分類法。

---

## 三、SHOT 資料結構

```jsonc
{
  "key": "d16s1",
  "title": "Chihuahua Cracks 12 Eggs 🥚",
  "shots": [
    {
      "id": "S01",
      "role": "opening",              // opening / insert / main / ending
      "duration": 5.04,               // 秒。121 格 ÷ 24
      "start": {                      // 起始條件二選一
        "type": "scene_image",        // scene_image | chain
        "scene_prompt_ref": "d16s1_scene.txt",
        "postfx": { "dots": ["402,371", "466,368"], "radius": 8 }
      },
      "camera": "static locked-off, floor level, eye-level pet angle",
      "motion": "slowly turns his head toward the camera and holds a long stare",
      "character_state": { "taco": "guilty" },
      "object_state":    { "egg_carton": "spilled", "eggs": "destroyed" },
      "scene_state":     "messy",
      "cut_to_next":     { "type": "chain", "anchor": 17 }
    },
    {
      "id": "INS1",
      "role": "insert",
      "duration": 1.45,
      "start": { "type": "crop_from", "shot": "S01",
                 "src_range": [0.30, 1.75], "crop": "486:864:0:600" },
      "note": "打翻的蛋盒特寫＝第二鉤子，落在 2.80s（對標區間 1.6–2.6s）",
      "cut_to_next": { "type": "jump_cut_behind_insert" }
    },
    {
      "id": "S02",
      "role": "main",
      "duration": 4.33,               // 121 − 17 = 104 格
      "start": { "type": "chain", "from": "S01", "anchor": 17 },
      "camera": "same as S01",
      "motion": "lowers his head to sniff the yolk, then lifts it back up",
      "character_state": { "taco": "guilty" },
      "object_state":    { "egg_carton": "spilled", "eggs": "destroyed" },
      "scene_state":     "messy",
      "cut_to_next":     null         // 最後一鏡
    }
  ]
}
```

---

## 四、狀態欄位真正在做什麼（不是為了好看）

### 4.1 產生 prompt 的「狀態句」，不是產生整段 prompt

狀態欄位**不取代 prompt**。它產生 prompt 裡那幾句**必須跨鏡一致**的話：

```
object_state.eggs = "destroyed"
  → "about twelve smashed raw eggs with glossy orange-yellow yolks soaking into the white sheet"

scene_state = "messy"
  → "shell fragments scattered around"

character_state.taco = "guilty"
  → "holds a long guilty stare straight into the lens, his eyes going wide and round"
```

這幾句由**同一個對照表**產生，所以 S01 和 S02 寫出來的字**逐字相同** ——
現在是人手寫兩次，寫歪了沒人知道。

### 4.2 讓程式擋得住「跨鏡狀態倒退」

```
S01: eggs = destroyed
S02: eggs = full        ← 蛋自己復原了。程式一行就擋得住，散文擋不住
```

規則很少但很硬：`object_state` 只准單向前進（`full → bite_01 → bite_02 → destroyed`），
要倒退必須在 shot 裡明寫 `"state_reset": "劇情理由"`。

### 4.3 讓標題承諾對得上畫面（PUBLISH_GATE 第 10 條的程式版）

D11S1 事故那條規則現在是靠人「把標題拆成承諾清單，逐項在幀上指證據」。
有了狀態表，`Turned Into A Tiny Panda 🐼` 這種標題可以直接比對
`character_state` 有沒有出現對應的值 —— **對不上就在生成前擋掉，不用等成片。**

---

## 五、與現有系統怎麼共存（重點：不破壞）

| 現有 | 新的 shots.json | 關係 |
|---|---|---|
| `schedule.json` 的 `scenePrompt` / `videoPrompt` | 仍然是**唯一的真相來源** | shots.json 先只做**旁註**：記狀態、記接點、記時間軸 |
| `state.json` | 不動 | shots.json 是獨立檔，`clips\{key}_shots.json` |
| `_build_dNN.py` 的時間軸 | 手寫在原始碼 | 第一步只是把同樣的資訊**抄進 shots.json**，兩邊並存比對 |
| `plan_model.py` | 只吃 text | 不變。未來可以多讀 `motion` 欄位提高判斷準度 |

**落地順序**（每一步都可停）：

1. 先幫 D10S1 與 D12S1 這兩支**已完成**的片補寫 shots.json ——
   用「能不能把已知的成片描述完整」驗證這個結構夠不夠用。**這步不生任何新片。**
2. `assemble.py` 改成讀 shots.json（而不是讀死在原始碼的時間軸），輸出要跟現有 `-cut.mp4` 對得上
3. 新片開始用 shots.json 寫劇本
4. 再談 prompt 自動組裝與狀態檢查

⛔ **不要一次做到第 4 步。** 這個結構有沒有用，要等第 1 步寫完兩支才知道 ——
寫不下去就是結構錯了，那時候還沒有任何東西依賴它。
