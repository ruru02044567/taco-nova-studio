# -*- coding: utf-8 -*-
r"""
preflight.py — 發布前程式閘門（2026-08-18 建立）

背景：8/18 凌晨實證「寫成程式的規則會擋、寫成文件的規則靠運氣」
（desc_spec.py 擋下 D14S1、頻道確認擋下 D8S1）。本腳本把 PUBLISH_GATE
裡「可程式化」的幾條變成硬檢查；視覺類規則仍靠人審。

檢查項：
  1. 檔案存在且大小合理
  2. 有聲音軌（歷來最大盲區：pipeline 產的是無聲原片）
  3. 音軌不是靜音軌（mean_volume 過低視同無聲）
  4. 時長 3–60 秒（Shorts 限制）
  5. 直式（高 > 寬）
  6. rejected.json 黑名單——JSON 壞掉會「大聲失敗」而不是靜默跳過
     （修掉已知失效模式：手改漏逗號會讓黑名單檢查被靜默略過）

用法：python auto\preflight.py <成片路徑> [--key d8s1]
結果：全過 exit 0；任一項不過 exit 1；黑名單命中 exit 2；黑名單檔壞掉 exit 3
注意：ffmpeg 碰中文路徑會靜默失敗，所以一律先複製到純英文暫存路徑再檢查。
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTO = Path(__file__).resolve().parent
REJECTED = AUTO / "rejected.json"


def ffprobe_json(path):
    p = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, timeout=120,
        encoding="utf-8", errors="replace")
    if p.returncode != 0 or not p.stdout.strip():
        return None
    return json.loads(p.stdout)


def mean_volume_db(path):
    p = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(path), "-map", "0:a:0",
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace")
    m = re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB", p.stderr)
    return float(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="成片路徑（可含中文，會自動複製到英文暫存）")
    ap.add_argument("--key", default=None, help="影片 key，用於黑名單比對（如 d8s1）")
    args = ap.parse_args()

    src = Path(args.video)
    results = []  # (name, ok, detail)

    # 1. 檔案存在（Path("") 會變成 "."，exists() 誤回 True，所以用 is_file）
    if not args.video or not src.is_file():
        print(f"✗ 檔案不存在或不是檔案：{args.video!r}")
        sys.exit(1)
    size_mb = src.stat().st_size / 2**20
    results.append(("檔案大小", size_mb > 0.5, f"{size_mb:.1f} MB"))

    # key 僅供訊息顯示；黑名單比對用「檔名」——因為同一個 key 常同時有被拒版與已發布好版
    key = args.key
    if not key:
        m = re.match(r"(archived-)?(d\d+s\d+)", src.stem)
        key = m.group(2) if m else None

    # 黑名單（逐檔檔名比對；JSON 壞掉要大聲失敗，不得靜默跳過）
    if REJECTED.exists():
        try:
            data = json.loads(REJECTED.read_text(encoding="utf-8"))
            banned = [str(it.get("file", "")) for it in
                      (data.get("rejected", []) + data.get("superseded", []))
                      if isinstance(it, dict)]
        except Exception as e:
            print(f"✗✗ rejected.json 解析失敗（{e}）——依規定硬停，不得靜默跳過黑名單")
            sys.exit(3)
        hit = next((b for b in banned if b and b.lower() == src.name.lower()), None)
        if hit:
            print(f"✗✗ {src.name} 在黑名單 rejected.json 內（{hit}），禁止發布")
            sys.exit(2)
        results.append(("黑名單", True, f"{src.name} 不在 {len(banned)} 筆黑名單中"))
    else:
        results.append(("黑名單", True, "⚠ rejected.json 不存在，本項未檢查"))

    # 複製到英文暫存（避開 ffmpeg 中文路徑靜默失敗）
    with tempfile.TemporaryDirectory(prefix="preflight_") as td:
        tmp = Path(td) / ("check" + src.suffix)
        shutil.copy2(src, tmp)

        info = ffprobe_json(tmp)
        if info is None:
            print("✗ ffprobe 無法解析檔案（檔案損壞？）")
            sys.exit(1)

        streams = info.get("streams", [])
        v = next((s for s in streams if s.get("codec_type") == "video"), None)
        a = next((s for s in streams if s.get("codec_type") == "audio"), None)

        # 2. 聲音軌存在
        results.append(("有聲音軌", a is not None,
                        a["codec_name"] if a else "沒有音軌——這是無聲原片，不是成片"))

        # 3. 音軌不是靜音
        if a is not None:
            mv = mean_volume_db(tmp)
            if mv is None:
                results.append(("音量", False, "量不到 mean_volume"))
            else:
                results.append(("音量", mv > -50.0, f"mean_volume {mv:.1f} dB"
                                + ("（過低，疑似靜音軌）" if mv <= -50.0 else "")))

        # 4. 時長
        dur = float(info.get("format", {}).get("duration", 0))
        results.append(("時長 3–60s", 3.0 <= dur <= 60.0, f"{dur:.1f} s"))

        # 5. 直式
        if v:
            w, h = int(v.get("width", 0)), int(v.get("height", 0))
            results.append(("直式畫面", h > w, f"{w}x{h}"))
        else:
            results.append(("直式畫面", False, "沒有影像軌"))

    ok = all(r[1] for r in results)
    print(f"── preflight {src.name} ──")
    for name, passed, detail in results:
        print(f"  {'✓' if passed else '✗'} {name}: {detail}")
    print("── 全部通過 ──" if ok else "── 有項目未過，禁止發布 ──")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
