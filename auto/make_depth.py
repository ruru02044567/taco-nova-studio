# -*- coding: utf-8 -*-
"""把一張構圖模板圖抽成深度圖存起來。抽一次就好，之後所有生成都重複用。

為什麼要拆出來（2026-08-11 的教訓）：
把 DA3 深度模型跟 SDXL ＋ IP-Adapter ＋ ControlNet 塞在同一個 workflow 裡，
這台 16 GB RAM 的機器直接 `Fatal Python error: Aborted` —— ComfyUI 整個進程崩掉，
佇列卡在 running=1 二十分鐘沒有任何產出，看起來像「很慢」其實是死了。

深度圖是**同一張模板永遠算出同一個結果**的東西，本來就沒有理由每次重算。
抽好存成 PNG，生成時用 LoadImage 讀進來，就不必再載 DA3。

用法：python make_depth.py <input圖檔名> <輸出檔名>
      （input 圖要先放進 ComfyUI/input/）
"""
import shutil
import sys

import comfy_api as C

sys.stdout.reconfigure(encoding="utf-8")

src = sys.argv[1]
out_name = sys.argv[2] if len(sys.argv) > 2 else "depth_" + src

W, H = 768, 1152

wf = {
    "30": {"class_type": "LoadImage", "inputs": {"image": src}},
    "31": {"class_type": "ImageScale",
           "inputs": {"image": ["30", 0], "width": W, "height": H,
                      "upscale_method": "lanczos", "crop": "center"}},
    "11": {"class_type": "LoadDA3Model",
           "inputs": {"model_name": "depth_anything_3_base.safetensors",
                      "weight_dtype": "fp16"}},
    "12": {"class_type": "DA3Inference",
           "inputs": {"da3_model": ["11", 0], "image": ["31", 0],
                      "resolution": 504, "resize_method": "upper_bound_resize",
                      "mode": "mono"}},
    "13": {"class_type": "DA3Render",
           "inputs": {"da3_geometry": ["12", 0], "output": "depth",
                      "output.normalization": "v2_style",
                      "output.apply_sky_clip": False}},
    "14": {"class_type": "SaveImage",
           "inputs": {"images": ["13", 0], "filename_prefix": "pet/depthmap"}},
}

C.require_server()
imgs = C.run(wf, tag="depth", timeout=900)
if not imgs:
    print("FAILED: 深度圖沒抽出來")
    sys.exit(1)

dest = C.COMFY_INPUT + "\\" + out_name
shutil.copy(imgs[0], dest)
print("saved", imgs[0])
print("已放進 ComfyUI/input：", out_name)
print("\n之後生成時用 --depth", out_name, "就不會再載 DA3 了")

# 抽完就把模型卸掉，把記憶體讓給接下來的 SDXL
try:
    C.free_memory()
    print("已釋放模型記憶體")
except Exception:
    pass
