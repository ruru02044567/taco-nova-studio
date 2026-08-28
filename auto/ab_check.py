# -*- coding: utf-8 -*-
"""ab_check — 出廠前跟頻道最佳同類片做量化 A/B（2026-08-28 賢賢核准新增）。

score_video 十項全是「防壞」的地板；這支是天花板：
候選片必須在「運動量」「音量水位」兩個維度上追上參考片，差太多就退回重做。

用法：
  python ab_check.py <候選.mp4> <參考.mp4|參考音檔.m4a>

門檻（初版，2026-08-28 推的——用幾次之後要拿實際數據回來校準）：
  運動量中位數  >= 參考片的 60%
  整體音量 mean 與參考片差距 <= 4.0 dB
  0.5s RMS 包絡的中位數（聲音主體水位）差距 <= 5.0 dB

Exit code：0＝全過；1＝有 FAIL；2＝參考檔讀不到。
d6s2 第一版的教訓：聲音主體比參考片小 6~10 dB、開頭四秒近乎全空，
score_video 卻全過——因為它只有地板沒有天花板。這支工具就是那次補的。
"""
import re
import statistics
import subprocess
import sys


def sh(args):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "") + (r.stderr or "")


def motion_median(path):
    out = sh(["ffmpeg", "-i", path,
              "-vf", "select='gte(scene,0)',metadata=print", "-f", "null", "-"])
    scores = [float(x) for x in re.findall(r"scene_score=([0-9.]+)", out)]
    return statistics.median(scores) if scores else None


def mean_volume(path):
    out = sh(["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"])
    m = re.search(r"mean_volume: ([-\d.]+)", out)
    return float(m.group(1)) if m else None


def rms_body(path):
    """0.5 秒一段的 RMS 包絡取中位數＝聲音主體水位（48kHz 下 reset=24000 約 0.5s）。"""
    r = subprocess.run(["ffprobe", "-v", "error", "-f", "lavfi", "-i",
                        f"amovie='{path}',astats=metadata=1:reset=24000",
                        "-show_entries", "frame_tags=lavfi.astats.Overall.RMS_level",
                        "-of", "csv=p=0"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    # 只認純數字行（stderr 混進來的雜訊一律丟掉）
    vals = [float(x) for x in re.findall(r"^(-?\d+(?:\.\d+)?)\s*$",
                                         r.stdout or "", re.MULTILINE)]
    return statistics.median(vals) if vals else None


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    cand, ref = sys.argv[1], sys.argv[2]
    ref_is_audio = ref.lower().endswith((".m4a", ".mp3", ".wav", ".aac"))

    rows, fails = [], 0

    def add(name, cv, rv, spec, ok):
        nonlocal fails
        rows.append((name, cv, rv, spec, ok))
        if not ok:
            fails += 1

    # 運動量（參考檔是純音檔時跳過）
    cm = motion_median(cand)
    if not ref_is_audio:
        rm = motion_median(ref)
        if cm is None or rm is None:
            sys.exit(2)
        add("運動量中位數", f"{cm:.4f}", f"{rm:.4f}",
            ">= 參考 60%", cm >= rm * 0.60)
    elif cm is not None:
        rows.append(("運動量中位數", f"{cm:.4f}", "（參考為音檔，僅列出）", "-", True))

    cv, rv = mean_volume(cand), mean_volume(ref)
    if cv is None or rv is None:
        sys.exit(2)
    add("整體音量 mean", f"{cv:.1f} dB", f"{rv:.1f} dB",
        "差距 <= 4.0 dB", abs(cv - rv) <= 4.0)

    cb, rb = rms_body(cand), rms_body(ref)
    if cb is not None and rb is not None:
        add("聲音主體水位（RMS 中位）", f"{cb:.1f} dB", f"{rb:.1f} dB",
            "差距 <= 5.0 dB", abs(cb - rb) <= 5.0)

    w = max(len(r[0]) for r in rows)
    print(f"{'項目'.ljust(w)}  候選            參考            標準              判定")
    for name, c, r, spec, ok in rows:
        print(f"{name.ljust(w)}  {str(c):<14}  {str(r):<14}  {spec:<16}  {'PASS' if ok else '❌ FAIL'}")
    print(f"\n{'✅ A/B 全過' if fails == 0 else f'❌ {fails} 項 FAIL —— 退回重做，不送賢賢'}")
    sys.exit(0 if fails == 0 else 1)


if __name__ == "__main__":
    main()
