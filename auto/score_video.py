# -*- coding: utf-8 -*-
r"""score_video.py — 候選影片自審腳本（2026-08-19 建立）。

依《對標製作標準》的 numeric_checklist 逐項打分：拿 8 支對標實測值
（Tim & Jeffy 千萬觀看級）當 pass 區間。目的：**做的人先自己過完這關，
才准拿去給賢賢過目** —— 賢賢是驗收官，不是陪練員。

只放程式量得出來的項目；「感覺類」（笑點、表情、音色自然度）量不出來，
仍由賢賢的耳朵眼睛把關。

2026-08-22 補：加上「全片運動量」。在此之前十項裡只有「結尾非定格」碰到運動，
而且只量末 0.55 秒、門檻 0.0008 低到任何緩慢推鏡都能過，導致 D13S1 拿到 10/10
卻整支像靜態圖。全片幀間變化中位數從來沒有人量過 —— 不是漏看，是規則不存在。
現在中位數是硬門檻，另加逐鏡診斷抓出最死的那一顆鏡頭。

用法：python score_video.py <影片.mp4>
Exit code：0＝全過；1＝有 FAIL。
"""
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

# ── 運動量門檻（2026-08-21 實測校準，見 PUBLISH_GATE.md 第三個盲區）──
#   Tim & Jeffy 對標片 幀間變化中位數 = 0.0137
#   D13S1（過了全部閘門卻像靜態圖）    = 0.0052
MOTION_MEDIAN_MIN = 0.0100      # 硬門檻：實測校準值
SHOT_MOTION_WARN  = 0.0050      # 逐鏡警示：由硬門檻的一半推得，**尚未用對標片校準**

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

        rows = []          # (名稱, 實測, 區間, PASS/FAIL/WARN/INFO)
        def add(name, value, cond_desc, ok):
            rows.append((name, value, cond_desc, "PASS" if ok else "FAIL"))

        def warn(name, value, cond_desc, ok):
            """未經對標片校準的項目：不擋發布，只出聲。"""
            rows.append((name, value, cond_desc, "PASS" if ok else "WARN"))

        def info(name, value, cond_desc):
            """純診斷數字，不判定。"""
            rows.append((name, value, cond_desc, "INFO"))

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

        # ── 全片逐幀運動量：跑一次全片 scene_score，結尾與全片共用 ──
        # 舊版只取末 0.55 秒，導致「全片像靜態圖」完全量不到（2026-08-21 盲區）
        fd = sh(["ffmpeg", "-i", v,
                 "-vf", "select='gte(scene,0)',metadata=print", "-f", "null", "-"])
        samples = []          # (t, score)
        t_cur = None
        for line in fd.splitlines():
            mt = re.search(r"pts_time:([0-9.]+)", line)
            if mt:
                t_cur = float(mt.group(1))
                continue
            ms = re.search(r"scene_score=([0-9.]+)", line)
            if ms and t_cur is not None:
                samples.append((t_cur, float(ms.group(1))))
        scores = [s for _, s in samples]

        # 10. 結尾非定格（末 0.55 秒，門檻與行為與舊版一致）
        tail_scores = [s for t, s in samples if t >= dur - 0.55]
        avg_motion = (sum(tail_scores) / len(tail_scores)) if tail_scores else 0.0
        add("結尾非定格", f"末段平均變化 {avg_motion:.4f}",
            ">0.0008（動作中斷收尾，8/8 對標如此）", avg_motion > 0.0008)

        # 11. 全片運動量 ← 這一項就是 D13S1 明明 10/10 卻像靜態圖的漏洞
        med = statistics.median(scores) if scores else 0.0
        add("全片運動量", f"幀間變化中位數 {med:.4f}（{len(scores)} 幀）",
            f">={MOTION_MEDIAN_MIN:.4f}（對標 0.0137／D13S1 0.0052）",
            med >= MOTION_MEDIAN_MIN)

        # 12. 逐鏡運動量：全片中位數可能被單一活躍鏡頭拉高，要抓出最死的那一顆
        shot_meds = []
        for i in range(len(bounds) - 1):
            seg = [s for t, s in samples if bounds[i] <= t < bounds[i + 1]]
            shot_meds.append(statistics.median(seg) if seg else 0.0)
        if shot_meds:
            worst = min(shot_meds)
            widx = shot_meds.index(worst) + 1
            detail = "／".join(f"S{j+1} {m:.4f}" for j, m in enumerate(shot_meds))
            warn("逐鏡運動量", f"最低 S{widx} {worst:.4f}　（{detail}）",
                 f">={SHOT_MOTION_WARN:.4f}（推得值，尚未用對標片校準）",
                 worst >= SHOT_MOTION_WARN)

        # 13. 靜止幀比例（診斷用，不判定）
        # 8/21 實測：我們 23%、對標 22%，兩邊幾乎一樣 —— 所以問題不是「靜止幀太多」，
        # 而是「該動的時候動得太小」。這個數字放著是為了防止把歸因again 弄錯。
        if scores:
            still = sum(1 for s in scores if s < 0.002)
            info("靜止幀比例", f"{still}/{len(scores)}＝{still/len(scores)*100:.0f}%",
                 "對標同為 22%，此項不判定，只防止歸因錯誤")

        # 輸出
        print(f"\n═══ 自審：{Path(video).name} ═══")
        MARK = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "INFO": "ℹ️"}
        fails = sum(1 for r in rows if r[3] == "FAIL")
        warns = sum(1 for r in rows if r[3] == "WARN")
        judged = [r for r in rows if r[3] in ("PASS", "FAIL", "WARN")]
        for name, val, cond, res in rows:
            print(f" {MARK[res]} {name:10}{val}　（要求：{cond}）")
        passed = sum(1 for r in judged if r[3] == "PASS")
        tail = f"，{warns} 項警示" if warns else ""
        print(f"═══ {passed}/{len(judged)} 過{tail} ═══")
        if fails:
            print("   ⚠️ 有 FAIL，不得送交賢賢過目。")
        return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
