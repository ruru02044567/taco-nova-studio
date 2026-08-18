# -*- coding: utf-8 -*-
r"""score_video.py — 候選影片自審腳本（2026-08-19 建立）。

依《對標製作標準》的 numeric_checklist 逐項打分：拿 8 支對標實測值
（Tim & Jeffy 千萬觀看級）當 pass 區間。目的：**做的人先自己過完這關，
才准拿去給賢賢過目** —— 賢賢是驗收官，不是陪練員。

只放程式量得出來的項目；「感覺類」（笑點、表情、音色自然度）量不出來，
仍由賢賢的耳朵眼睛把關。

用法：python score_video.py <影片.mp4>
Exit code：0＝全過；1＝有 FAIL。
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def sh(args):
    p = subprocess.run(args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (p.stdout or "") + (p.stderr or "")


def main(video):
    # 中文路徑坑：先複製到英文暫存
    with tempfile.TemporaryDirectory(prefix="score_") as td:
        v = Path(td) / "v.mp4"
        import shutil
        shutil.copy2(video, v)
        v = str(v)

        rows = []          # (名稱, 實測, 區間, PASS/FAIL/SKIP)
        def add(name, value, cond_desc, ok):
            rows.append((name, value, cond_desc, "PASS" if ok else "FAIL"))

        # 1. 片長
        dur = float(sh(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", v]).strip())
        add("片長", f"{dur:.2f}s", "12.1–14.9s（對標實測）", 12.1 <= dur <= 14.9)

        # 2. 直式規格
        out = sh(["ffprobe", "-v", "quiet", "-select_streams", "v:0",
                  "-show_entries", "stream=width,height,r_frame_rate",
                  "-of", "csv=p=0", v]).strip()
        w_, h_, fr = out.split(",")[:3]
        num, den = fr.split("/")
        fps = float(num) / float(den)
        add("直式規格", f"{w_}x{h_}@{fps:.0f}", "1080x1920、fps>=24",
            w_ == "1080" and h_ == "1920" and fps >= 24)

        # 3-5. 鏡頭數／平均鏡長／主鏡（scene detection 0.2，對標同參數）
        sc = sh(["ffmpeg", "-i", v, "-vf", "select='gt(scene,0.2)',metadata=print",
                 "-f", "null", "-"])
        cuts = sorted(set(round(float(m), 2) for m in
                          re.findall(r"pts_time:([0-9.]+)", sc)))
        # 相鄰 0.5s 內的切點視為同一刀（偵測抖動）
        merged = []
        for c in cuts:
            if not merged or c - merged[-1] > 0.5:
                merged.append(c)
        bounds = [0.0] + merged + [dur]
        shots = [round(bounds[i + 1] - bounds[i], 2) for i in range(len(bounds) - 1)]
        n = len(shots)
        add("鏡頭數", f"{n}（切點 {merged}）", "1–7", 1 <= n <= 7)
        add("平均鏡長", f"{dur / n:.2f}s", "1.9–14.9s", 1.9 <= dur / n <= 14.9)
        add("主鏡存在", f"最長 {max(shots):.2f}s", ">=3.8s（要有反應戲主鏡）",
            max(shots) >= 3.8)

        # 6-7. 整體/峰值音量
        vd = sh(["ffmpeg", "-i", v, "-af", "volumedetect", "-f", "null", "-"])
        mean = float(re.search(r"mean_volume: ([-\d.]+)", vd).group(1))
        peak = float(re.search(r"max_volume: ([-\d.]+)", vd).group(1))
        add("整體音量", f"{mean:.1f} dB", "-25.0～-16.5", -25.0 <= mean <= -16.5)
        add("峰值音量", f"{peak:.1f} dB", ">=-3.0（打近滿刻度）", peak >= -3.0)

        # 8. 零靜音段
        sil = sh(["ffmpeg", "-i", v, "-af", "silencedetect=noise=-35dB:d=0.4",
                  "-f", "null", "-"])
        n_sil = len(re.findall(r"silence_start", sil))
        add("零靜音段", f"{n_sil} 段", "0 段（聲底必須連續）", n_sil == 0)

        # 9. 無淡出結尾
        tail = sh(["ffmpeg", "-ss", str(max(0, dur - 0.5)), "-i", v,
                   "-af", "volumedetect", "-f", "null", "-"])
        m = re.search(r"mean_volume: ([-\d.]+)", tail)
        tmean = float(m.group(1)) if m else -99.0
        add("無淡出結尾", f"末 0.5s {tmean:.1f} dB", ">=-33（戛然而止）", tmean >= -33.0)

        # 10. 結尾非定格（末 0.5 秒幀間差）
        fd = sh(["ffmpeg", "-ss", str(max(0, dur - 0.55)), "-i", v,
                 "-vf", "select='gte(scene,0)',metadata=print", "-f", "null", "-"])
        diffs = [float(x) for x in re.findall(r"scene_score=([0-9.]+)", fd)]
        avg_motion = (sum(diffs) / len(diffs)) if diffs else 0.0
        add("結尾非定格", f"末段平均變化 {avg_motion:.4f}",
            ">0.0008（動作中斷收尾，8/8 對標如此）", avg_motion > 0.0008)

        # 輸出
        print(f"\n═══ 自審：{Path(video).name} ═══")
        fails = 0
        for name, val, cond, res in rows:
            mark = "✅" if res == "PASS" else "❌"
            if res == "FAIL":
                fails += 1
            print(f" {mark} {name:8}  {val}　（要求：{cond}）")
        print(f"═══ {len(rows) - fails}/{len(rows)} 過 ═══")
        return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
