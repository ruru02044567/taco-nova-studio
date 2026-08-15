# -*- coding: utf-8 -*-
"""D5 岩漿片定剪：兩段接起來 → 配音效 → 拉到 -14 LUFS → 進待審核。

跟前幾支最大的不同是**開頭那一刀**：

8/11 審片量出「峰值/基線」這個指標 —— 爆款那支是 35 倍（安靜鋪陳→爆發→收乾淨），
本機生的片都只有 2 倍（從頭忙到尾，觀眾拿不到新資訊就滑走）。
我在 seg1 的 prompt 裡明寫「先靜止一拍，然後才拖抱枕」想製造對比，
**實測完全沒用**：Wan 2.2 不吃時間序指令，動量曲線量出來是平的 1.4 倍。

所以改在剪輯階段做：把 seg1 開頭 0.7 秒放慢成 1.8 秒當鋪陳拍。
一樣的素材，峰值/基線從 1.4 倍拉到 3.2 倍，而且畫面沒有靜止（熔岩還在冒泡），
不會讓人以為影片壞掉。

片長刻意做成 ~10.1 秒對齊 D4S1，這樣實驗 #1 的片長變數才不會又被污染。
"""
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).parent
CLIPS = HERE / "clips"
REVIEW = HERE.parent / "待審核"
SFX = HERE.parent / "sfx"

SEG1 = CLIPS / "d5s1_seg1.mp4"
SEG2 = CLIPS / "d5s1_seg2.mp4"
SILENT = CLIPS / "d5s1_silent.mp4"
OUT = REVIEW / "d5s1-岩漿-有聲.mp4"

RAMP_SRC = 0.7      # seg1 開頭拿多少秒來放慢
RAMP_X = 2.6        # 放慢幾倍
SEG2_KEEP = 3.97    # seg2 留多長（總長對齊 D4S1 的 10.09 秒）


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    if p.returncode != 0:
        print("失敗：", " ".join(str(c) for c in cmd[:6]), "\n", (p.stderr or "")[-800:])
        sys.exit(1)
    return p


def dur(path):
    return float(run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                      "-of", "csv=p=0", str(path)]).stdout.strip())


for f in (SEG1, SEG2):
    if not f.exists():
        print(f"FAILED: 缺 {f.name}")
        sys.exit(1)

print(f"seg1 {dur(SEG1):.2f}s   seg2 {dur(SEG2):.2f}s")

# 一次 filter_complex 做完：seg1 慢速頭 + seg1 其餘 + seg2 截段
fc = (
    f"[0:v]trim=0:{RAMP_SRC},setpts=PTS*{RAMP_X}[ramp];"
    f"[0:v]trim={RAMP_SRC},setpts=PTS-STARTPTS[rest];"
    f"[1:v]trim=0:{SEG2_KEEP},setpts=PTS-STARTPTS[tail];"
    f"[ramp][rest][tail]concat=n=3:v=1[out]"
)
run(["ffmpeg", "-y", "-v", "error", "-i", str(SEG1), "-i", str(SEG2),
     "-filter_complex", fc, "-map", "[out]",
     "-c:v", "libx264", "-preset", "medium", "-crf", "18",
     "-pix_fmt", "yuv420p", "-r", "24", str(SILENT)])
print(f"接好了：{SILENT.name}  {dur(SILENT):.2f}s")

# 配音效（lava 配方）＋ 拉到 -14 LUFS
sys.path.insert(0, str(SFX))
import mix  # noqa: E402

if not mix.build(str(SILENT), str(OUT), mix.RECIPES["lava"]):
    print("FAILED: 混音失敗")
    sys.exit(1)

print(f"\n完成：{OUT}  {dur(OUT):.2f}s")

# 四格截圖，方便快速看畫面
run(["ffmpeg", "-y", "-v", "error", "-i", str(OUT), "-vf",
     r"select='eq(n\,0)+eq(n\,45)+eq(n\,110)+eq(n\,160)+eq(n\,230)',scale=250:-1,tile=5x1",
     "-frames:v", "1", str(REVIEW / "d5s1-岩漿-畫面.jpg")])
print("截圖：待審核/d5s1-岩漿-畫面.jpg")
