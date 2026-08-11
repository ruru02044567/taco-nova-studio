# -*- coding: utf-8 -*-
"""
ComfyUI API 共用工具。

鐵律：
  * 這支程式「絕對不會」啟動或關閉 ComfyUI。
    伺服器沒開就直接報錯結束，請自己跑 auto/restart_comfy.ps1。
    （曾經踩過：兩支腳本各自「沒開就開、跑完關掉」，
      後結束的把伺服器關掉、順手殺掉前一支排隊中的工作。）
  * 中間檔一律寫到純英文路徑 _farmwork/，避免中文路徑的坑。
"""
import json
import os
import shutil
import sys
import time
import urllib.request
import urllib.error
import uuid

SERVER = "127.0.0.1:8188"
BASE = f"http://{SERVER}"

COMFY_ROOT = r"C:\Users\TUF Gaming\ai-video-local\ComfyUI"
COMFY_INPUT = os.path.join(COMFY_ROOT, "input")
COMFY_OUTPUT = os.path.join(COMFY_ROOT, "output")
WORK = r"C:\Users\TUF Gaming\ai-video-local\_farmwork\consistency"
os.makedirs(WORK, exist_ok=True)

CLIENT_ID = str(uuid.uuid4())


def _get(path, timeout=10):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def require_server():
    try:
        s = _get("/system_stats")
    except Exception as e:
        print("[X] ComfyUI 沒有在跑（或沒回應）:", e)
        print("    請先執行： powershell -File \"C:\\Users\\TUF Gaming\\Desktop\\我的專案\\卡通農場\\auto\\restart_comfy.ps1\"")
        sys.exit(1)
    dev = s["devices"][0]
    print(f"[ok] ComfyUI {s['system']['comfyui_version']} | {dev['name']} | "
          f"VRAM free {dev['vram_free']/2**30:.2f} / {dev['vram_total']/2**30:.2f} GB")
    return s


def free_memory(unload_models=True):
    """釋放 VRAM/RAM，但不關伺服器。切換大模型前先呼叫。"""
    body = json.dumps({"unload_models": unload_models, "free_memory": True}).encode()
    req = urllib.request.Request(f"{BASE}/free", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=120).read()
        print("[ok] 已請 ComfyUI 釋放記憶體")
    except Exception as e:
        print("[!] free 失敗（不影響後續）:", e)


def object_info(node=None):
    return _get("/object_info" + (f"/{node}" if node else ""), timeout=60)


def combo_options(node, field):
    """取得某個節點某個下拉欄位目前可選的值（用來確認模型檔有被掃到）。"""
    info = object_info(node)[node]["input"]
    spec = info.get("required", {}).get(field) or info.get("optional", {}).get(field)
    if spec is None:
        return []
    v = spec[0]
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        return v.get("options", [])
    return []


def is_complete_safetensors(path):
    """檔案還在下載中就會是壞的 safetensors。踩過一次：腳本自動挑了下載到一半的
    checkpoint，八組測試全部炸在 CheckpointLoaderSimple。"""
    import struct
    try:
        sz = os.path.getsize(path)
        with open(path, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            if n <= 0 or n > 100_000_000:
                return False
            hdr = json.loads(f.read(n))
        need = 8 + n + max((v["data_offsets"][1] for v in hdr.values()
                            if isinstance(v, dict) and "data_offsets" in v), default=0)
        return sz >= need
    except Exception:
        return False


def usable_checkpoints():
    """只回傳「下載完整、真的能載入」的 checkpoint。"""
    out = []
    for name in combo_options("CheckpointLoaderSimple", "ckpt_name"):
        p = os.path.join(COMFY_ROOT, "models", "checkpoints", name)
        if os.path.exists(p) and is_complete_safetensors(p):
            out.append(name)
        else:
            print(f"[!] 跳過 {name}（檔案不完整，可能還在下載）")
    return out


def wait_for_free_queue(timeout=3600, poll=10):
    """禮讓：賢賢的 Wan 生影片工作在跑就等它跑完，不要插隊。

    8GB VRAM 同時載兩套模型會嚴重拖慢甚至 OOM，所以一次只讓一種模型佔著 GPU。
    """
    t0 = time.time()
    waited = False
    while time.time() - t0 < timeout:
        try:
            q = _get("/queue", timeout=10)
        except Exception:
            time.sleep(poll)
            continue
        busy = len(q["queue_running"]) + len(q["queue_pending"])
        if busy == 0:
            if waited:
                print(f"[ok] 佇列空了（等了 {int(time.time()-t0)}s），接手")
            return True
        if not waited:
            print(f"[…] 別人的工作在跑（running={len(q['queue_running'])} "
                  f"pending={len(q['queue_pending'])}），禮讓等待中…")
            waited = True
        time.sleep(poll)
    print("[!] 等太久了，還是先跑（可能會跟別的工作搶 VRAM）")
    return False


def submit(workflow):
    body = json.dumps({"prompt": workflow, "client_id": CLIENT_ID}).encode()
    req = urllib.request.Request(f"{BASE}/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        res = json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        print("[X] 工作流被拒絕：")
        print(detail[:4000])
        sys.exit(2)
    if res.get("node_errors"):
        print("[!] node_errors:", json.dumps(res["node_errors"], ensure_ascii=False)[:2000])
    return res["prompt_id"]


def wait(prompt_id, timeout=1800, poll=2.0):
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout:
        try:
            hist = _get(f"/history/{prompt_id}", timeout=15)
        except Exception:
            time.sleep(poll)
            continue
        if prompt_id in hist:
            h = hist[prompt_id]
            st = h.get("status", {})
            if st.get("status_str") == "error" or not st.get("completed", True):
                for m in st.get("messages", []):
                    if m[0] in ("execution_error", "execution_interrupted"):
                        d = m[1]
                        print(f"[X] 執行失敗 node={d.get('node_id')} "
                              f"({d.get('node_type')}): "
                              f"{d.get('exception_type')}: {d.get('exception_message')}"[:400])
                if st.get("status_str") == "error":
                    return None
            return h
        try:
            q = _get("/queue", timeout=10)
            msg = f"  ...排隊中 running={len(q['queue_running'])} pending={len(q['queue_pending'])} " \
                  f"({int(time.time()-t0)}s)"
            if msg != last:
                print(msg, flush=True)
                last = msg
        except Exception:
            pass
        time.sleep(poll)
    print("[X] 逾時")
    return None


def collect_images(history, dest_dir=WORK, tag=""):
    """把 SaveImage 產生的檔案從 ComfyUI/output 複製到工作目錄，回傳新路徑清單。"""
    out = []
    if not history:
        return out
    for node_id, node_out in history.get("outputs", {}).items():
        for im in node_out.get("images", []):
            if im.get("type") != "output":
                continue
            src = os.path.join(COMFY_OUTPUT, im.get("subfolder", ""), im["filename"])
            if not os.path.exists(src):
                continue
            name = (tag + "_" if tag else "") + im["filename"]
            dst = os.path.join(dest_dir, name)
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(src, dst)
            out.append(dst)
    return out


def run(workflow, tag="", timeout=1800, yield_queue=True):
    if yield_queue:
        wait_for_free_queue()
    pid = submit(workflow)
    print(f"[>] prompt_id={pid} tag={tag}")
    t0 = time.time()
    h = wait(pid, timeout=timeout)
    if h is None:
        return []
    imgs = collect_images(h, tag=tag)
    print(f"[ok] {tag} 完成，{time.time()-t0:.0f}s，產出 {len(imgs)} 張")
    for p in imgs:
        print("    ", p)
    return imgs
