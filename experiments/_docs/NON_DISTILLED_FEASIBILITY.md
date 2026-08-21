# 非蒸餾版 Wan 這台跑不跑得動

> 2026-08-21｜賢賢問的｜**只做調查，沒有下載任何東西**
> 本機規格（實測）：RTX 5050 Laptop **8151 MiB VRAM**／RAM **15.26 GB**／C 槽餘 **159.9 GB**／分頁檔配置 34 GB

---

## 一、先講結論

| 方案 | 跑不跑得動 | 一支 5 秒要多久 | 判斷 |
|---|---|---|---|
| **現在**：Wan2.2 5B **Turbo**（蒸餾）Q4_K_M 3.44 GB | ✅ 在跑 | **6.4 分鐘** | 基準 |
| **非蒸餾 5B**：Wan2.2-TI2V-5B Q4_K_M **3.43 GB** | ✅ **跑得動，VRAM 需求幾乎一樣** | **約 18 分鐘**（推估） | 🟢 **值得試** |
| **非蒸餾 14B**：Wan2.2-I2V-A14B Q4_K_M **9.65 GB × 2** | ❌ 這台不行 | — | 🔴 **放棄** |

---

## 二、非蒸餾 5B：跑得動，而且成本只有「慢 2.8 倍」

### 為什麼確定跑得動

我們現在跑的 `wan22_5b_turbo_Q4_K_M.gguf` 是 **3,437,927,136 bytes = 3.44 GB**。
官方非蒸餾版 `Wan2.2-TI2V-5B-Q4_K_M.gguf` 是 **3.43 GB**。

**同一個架構、同樣的參數量、同樣的量化等級 —— 檔案大小差不到 1%。**
Turbo 版是把蒸餾權重合併進去的同一個模型，不是另一顆更大的模型。
所以 **VRAM 需求跟現在完全一樣**（實測峰值 6.3–6.9 GB / 8.15 GB，還餘 1.2–1.8 GB）。

### 慢多少：用本機自己的資料算，不是猜

8/14 那輪 steps 掃描量過同一台機器、同樣 704×1280 × 121 格的時間：

| steps | 實測分鐘 |
|---|---|
| 4 | 5.0 |
| 6 | 5.8 |
| 8 | 6.5 |
| 10 | 7.3 |
| 16 | 9.3 |
| 24 | 12.0 |

線性擬合得到 **時間（分）≈ 3.6 ＋ 0.35 × 前向次數**
（3.6 分是固定開銷：載模型＋VAE encode＋VAEDecodeTiled；每一步約 21 秒）。
六個點全部吻合到 0.2 分鐘以內。

非蒸餾版的官方 ComfyUI 模板設定是 **steps 20 / cfg 5.0 / uni_pc + simple / shift 8 /
704×1280 / 121 格** —— 除了 steps 與 cfg 之外**跟我們現在一模一樣**。

`cfg > 1` 每一步要跑兩次前向（正面一次、負面一次），所以：

```
前向次數 = 20 步 × 2 = 40
時間 ≈ 3.6 + 0.35 × 40 = 17.6 分鐘
```

**約 18 分鐘／支，是現在的 2.8 倍。** 如果照 I2V 建議拉到 30–40 步，會變成 25–32 分鐘。

⚠️ 這是**推估不是實測**。誤差來源：cfg 開啟後 ComfyUI 可能把正負兩個 batch 併成一次
前向（那樣會比 2× 快一點但吃更多 VRAM），也可能拆成兩次（那樣就是 2×）。
8 GB 的卡配 121×704×1280 的 latent，我推測會走「拆成兩次」那條路。

---

## 三、⭐ 最重要的發現：現在的負面 prompt 完全沒有作用

`make_video_local_5s.py` 裡有一段 **766 字元**的負面 prompt，是一路被事故逼出來的：
`extra limbs, extra legs, two huskies, three dogs, animal shape hidden in the pile,
face emerging from powder, dust cloud from behind…`

同一支檔案裡 KSampler 寫的是 **`"cfg": 1.0`**。

查 ComfyUI 原始碼 `comfy/samplers.py:610`：

```python
def sampling_function(model, x, timestep, uncond, cond, cond_scale, model_options={}, seed=None):
    if math.isclose(cond_scale, 1.0) and model_options.get("disable_cfg1_optimization", False) == False:
        uncond_ = None          # ← 負面條件被丟掉，根本不會送進模型
    else:
        uncond_ = uncond
```

我們的工作流沒有設 `disable_cfg1_optimization`，所以走的是上面那條。

> **cfg = 1.0 的意思是「完全不做 classifier-free guidance」，
> 那 766 字元的負面 prompt 在程式碼層級確定是死的 —— 從第一支片到現在都是。**

它不是「效果不好」，是**根本沒有被評估過**。CLIPTextEncode 有跑（浪費一點時間），
結果在取樣時被丟掉。

### 這跟我們自己量到的東西對得上

記憶檔《本機生影片的道具漂移》寫著：
> 「負面詞完全擋不住，只能寫進正面 prompt。」

當時是**觀察到**這個現象，不知道為什麼。現在知道機制了：因為 cfg 1.0 把它整條關掉。
`prompt_ab` 那輪也對得上 —— 我們把「不准有第二隻狗」寫進**正面** prompt 才有效果
（PB 砍掉會身體拉伸，PB2 加回去就好了），因為正面 prompt 是唯一真的會被讀的那條。

### 所以換非蒸餾版可能真的有差

不是因為模型比較大（它一樣大），是因為**cfg 會回來**：

1. 那 766 字元的負面 prompt 第一次真的開始作用
2. cfg 5.0 會強化 prompt 遵循度 —— 而「prompt 寫的動作不執行」正是我們最大的抱怨

⚠️ **但這是推論，不是結論。** 蒸餾作者宣稱 4 步品質「與 base 相當甚至更好」，
那是講畫面品質，沒講動作可控性。**這台從來沒跑過非蒸餾版**，沒有任何本機數據。

也要注意 8/14 那輪的結論**不能拿來套**：那輪是拿 **turbo 模型**去跑 steps 16/24，
發現角色穩定度退步 —— 那是把蒸餾模型推出它的設計區間，跟「非蒸餾模型跑 20 步」
是兩件完全不同的事。

---

## 四、非蒸餾 14B：這台不行

| 為什麼 | 數字 |
|---|---|
| 模型比 VRAM 大 | Q4_K_M **9.65 GB** > 8.15 GB VRAM |
| **而且要兩顆** | A14B 是 MoE，官方要求同時準備 `high_noise` 與 `low_noise` 兩個檔，取樣中途切換 → 共 **19.3 GB** |
| RAM 不夠接住 offload | 社群共識 **24 GB 起跳、32 GB 建議**；這台 **15.26 GB**（umt5 文字編碼器自己就吃 6.74 GB） |
| 速度 | 社群回報 8 GB 卡跑 A14B GGUF＋offload 是 **20 分鐘以上／支，而且只有 480p** |
| 我們的規格更重 | 我們跑 704×1280，像素量是 480×832 的 **2.3 倍** |

降到 Q3_K_S（6.52 GB × 2 ＝ 13 GB）也救不了：
現在 3.44 GB 的模型峰值就要 6.3–6.9 GB（代表 activation 約 3 GB），
6.52 ＋ 3 ≈ 9.5 GB 還是超過 8.15 GB。

**結論：14B 這條路要換機器，不是換設定。**

---

## 五、如果要驗，成本很低

| 項目 | 成本 |
|---|---|
| 下載 | 3.43 GB（C 槽餘 159.9 GB，⚠️ 這台路由器 DNS 會被大流量打掛，要加 `--doh-url`） |
| 跑一組對照 | 約 18 分鐘 × 1 支 |
| 風險 | **零**。新模型放進 `models/unet/`，換 `unet_name` 就好，舊模型完全不動 |
| 可回滾 | 改一個字串回去即可 |

單變數設計（沿用現有實驗架構）：

| | 現行 | 對照 |
|---|---|---|
| 模型 | `wan22_5b_turbo_Q4_K_M.gguf` | `Wan2.2-TI2V-5B-Q4_K_M.gguf` |
| steps / cfg / sampler | 8 / 1.0 / euler | 20 / 5.0 / uni_pc |
| 其餘 | shift 8 / 121 格 / 704×1280 / 同 seed / 同 prompt / 同接龍來源 | 同左 |

⚠️ 這組**不是嚴格單變數**（模型、steps、cfg、sampler 四個一起變），
但那四個是綁在一起的 —— 非蒸餾模型跑 8 步 cfg 1.0 只會出垃圾，拆不開。
所以它是「兩種設定組合」的比較，不是「一個變數」的比較，報告要照實這樣寫。

要看的是那件我們一直解不掉的事：**抬起單邊前腳畫不畫得好、鏡頭聽不聽指令。**

---

## 資料來源

- 檔案大小：[QuantStack/Wan2.2-TI2V-5B-GGUF](https://huggingface.co/QuantStack/Wan2.2-TI2V-5B-GGUF)、[QuantStack/Wan2.2-I2V-A14B-GGUF](https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF)
- 官方兩個 expert 檔、5B 適合 8GB：[ComfyUI Wan2.2 官方教學](https://docs.comfy.org/tutorials/video/wan/wan2_2)
- 非蒸餾 5B 模板參數（steps 20 / cfg 5 / uni_pc / shift 8 / 704×1280 / 121）：[Wan2.2_5B_Ti2V.json](https://huggingface.co/datasets/stablediffusiontutorials/wan-workflows/blob/main/Wan2.2_5B_Ti2V.json)
- 8GB 跑 14B 的實務限制與 RAM 門檻：[Will It Run AI — Wan 2.2 VRAM Requirements](https://willitrunai.com/blog/wan-2-2-vram-requirements)、[Next Diffusion — Wan2.2 GGUF Low VRAM](https://www.nextdiffusion.ai/tutorials/how-to-run-wan22-image-to-video-gguf-models-in-comfyui-low-vram)
- 蒸餾版品質宣稱：[lightx2v/Wan2.2-Distill-Models](https://huggingface.co/lightx2v/Wan2.2-Distill-Models)、[Wan2.2-Lightning](https://github.com/ModelTC/Wan2.2-Lightning)
- cfg=1.0 丟棄負面條件：本機 `ai-video-local/ComfyUI/comfy/samplers.py:610`（原始碼直接查證）
- 時間模型：本機 `LOCAL-AI-STUDIO/PRODUCTION/_exp_20260814/E*.log`（6 個實測點）
