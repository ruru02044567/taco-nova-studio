# -*- coding: utf-8 -*-
"""把音效混進無聲的 Veo 影片。

Veo 給的音軌實測只有 -47dB（等於無聲），所以整條音訊由我們自己鋪：
  bed 層（環境底噪、黑洞嗡鳴）  -30 ~ -22 dB  全程鋪底
  foley 層（爪子、布料）        -18 ~ -12 dB  在指定秒數出現
  impact 層（掉落、被吞）       -12 ~ -8  dB  重點事件
最後用 loudnorm 統一到 -14 LUFS（YouTube 播放參考電平，只降不升，做太小聲就是吃虧）。

用法：python mix.py <影片> <輸出> [配方名稱]
"""
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
LIB = HERE / "lib"

# ── 音效配方：每支影片的劇情對應哪些聲音、在第幾秒、多大聲 ──────────
RECIPES = {
    # D1 黑洞：襪子遙控器掉進洞 → 拖地毯來蓋 → 地毯也被吞 → 洞變大
    # D1 黑洞：襪子遙控器掉進洞 → 拖地毯來蓋 → 地毯也被吞 → 洞變大
    # 密度目標：10 秒約 20 個事件（第一版只有 9 個，聽起來太空）
    "blackhole": [
        # ── bed 層：只是墊底，不能搶戲。v2 太厚把動作音壓掉了，這版整體降 6dB ──
        ("roomtone/Roomtone,Hvac,Drone,Hum,Low Mids,Loop.mp3", 0.0, -37, "highpass=f=80", True),
        ("amb-birds/AMB SUBURB Solo Bird Call, Early Morning, Distant Traffic Passbys, Montreal, Canada, LOOP.mp3",
         0.0, -39, "lowpass=f=1400", True),                      # 隔著窗戶的鳥叫與遠處車聲
        ("drone-low/hollow_drone_001.mp3", 0.0, -28, "lowpass=f=130,highpass=f=28", True),   # 黑洞嗡鳴
        ("air-suck/Wind,Int,Howl,Forceful,Tonal,Vocal,Gust.mp3", 0.0, -33, "lowpass=f=700,highpass=f=60", True),  # 被吸進去的氣流
        # ── 0-1s：災難已成形，兩個物件分開落地才有層次（全部提 3dB 讓它們跳出來） ──
        ("cloth-drop/Drop Soft - Single Plank, Drop 02.mp3", 0.15, -13, "lowpass=f=3500", False),   # 襪子
        ("plastic-drop/Vibration,Case,Objects,Rattle,Clatter,Rapid,Violent,Loop.mp3", 0.45, -10, "atrim=0:0.8", False),  # 遙控器
        ("rumble-sub/Low Boom 3.mp3", 0.9, -14, "lowpass=f=180", False),                    # 東西被吞下去的悶響
        # ── 2-6s：拖地毯（爪步＋抓地＋布料，三軌疊） ──
        ("paws-more/Paw 1_Wood_Trot-Walk.wav", 1.9, -11, "atempo=1.15", False),             # 真正的狗爪小跑
        ("claw-scratch/nails_on_towel_single_003.mp3", 2.3, -15, None, False),
        ("fabric-fine/Blanket-Lift_06.wav", 2.5, -9, "atempo=0.75", False),                 # 咬起地毯
        ("cloth-drag/CLOTHING_MATERIAL_MOVEMENT_08.wav", 3.1, -13, "atempo=0.8", False),
        ("paws-more/Paw 1_Wood_Trot-Walk.wav", 3.8, -12, "atempo=1.1", False),
        ("cloth-drag/ICE Skater cloth move 10.mp3", 4.4, -10, "atempo=0.85", False),        # 地毯拖過地板
        ("claw-scratch/nails_on_velvet_single_002.mp3", 5.2, -15, None, False),
        ("fabric-fine/Blanket-Lift_06.mp3", 5.6, -12, "atempo=0.9", False),
        # ── 6-7s：地毯被吞（三軌同時，這是全片最重的一下） ──
        ("whoosh/Organic_Whoosh_14.mp3", 6.25, -5, "asetrate=48000*0.6,aresample=48000,lowpass=f=900", False),
        ("fabric-fine/Blanket-Lift_06.wav", 6.4, -9, "atempo=1.6", False),                  # 布料被快速抽走
        ("rumble-sub/Low Boom 3.mp3", 6.85, -10, "lowpass=f=200", False),                   # 吞下去的低頻
        # ── 8-10s：退開、定格裝無辜 ──
        ("paws-more/Paw 1_Wood_Trot-Walk.wav", 7.9, -14, "atempo=1.2", False),
        ("claw-scratch/nails_on_towel_single_003.mp3", 8.9, -18, None, False),
    ],
}


def build(video, out, recipe):
    out = Path(out)          # 命令列傳進來是字串，下面 with_suffix 需要 Path
    dur = float(subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video],
        capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip())

    inputs, filters, labels = ["-i", str(video)], [], []
    for i, (rel, start, gain, extra, loop) in enumerate(recipe):
        src = LIB / rel
        if not src.exists():
            print(f"  ! 缺檔跳過：{rel}")
            continue
        if loop:
            inputs += ["-stream_loop", "-1", "-i", str(src)]
        else:
            inputs += ["-i", str(src)]
        idx = len(labels) + 1
        chain = f"[{idx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
        if extra:
            chain += f",{extra}"
        chain += f",volume={gain}dB"
        if start > 0:
            ms = int(start * 1000)
            chain += f",adelay={ms}|{ms}"
        chain += f",atrim=0:{dur:.3f},afade=t=in:st=0:d=0.02"
        chain += f"[a{idx}]"
        filters.append(chain)
        labels.append(f"[a{idx}]")

    mix = "".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0[mixed]"
    base_fc = ";".join(filters) + ";" + mix

    def run(post, dst):
        cmd = ["ffmpeg", "-v", "error", "-y", *inputs,
               "-filter_complex", base_fc + ";" + post,
               "-map", "0:v", "-map", "[aout]",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "384k", "-ar", "48000",
               "-movflags", "+faststart", "-shortest", str(dst)]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0:
            print("ffmpeg 失敗：", (p.stderr or "")[-900:])
            return False
        return True

    # 第一階段：先量測混完之後的整體響度。
    # 不能直接用 loudnorm 一次到位 —— 它預設是動態模式，會邊走邊壓縮，
    # 把落地聲、被吞那一下的尖峰全部壓平，聽起來就變成「一直有聲音但沒有重點」。
    probe = out.with_suffix(".probe.mp4")
    if not run("[mixed]anull[aout]", probe):
        return False
    meas = subprocess.run(["ffmpeg", "-i", str(probe), "-af", "ebur128=framelog=quiet",
                           "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    lufs = None
    for ln in meas.splitlines():
        if "I:" in ln and "LUFS" in ln:
            try:
                lufs = float(ln.split("I:")[1].split("LUFS")[0].strip())
            except Exception:
                pass
    probe.unlink(missing_ok=True)
    if lufs is None:
        print("量不到響度，退回 loudnorm")
        return run("[mixed]loudnorm=I=-14:TP=-1.5:LRA=11[aout]", out)

    gain = -14.0 - lufs
    print(f"混音後 {lufs:.1f} LUFS → 套用固定增益 {gain:+.1f} dB（動態完整保留）")
    # 第二階段：純線性增益 + 只在真的爆表時才動作的 limiter
    return run(f"[mixed]volume={gain:.2f}dB,alimiter=limit=-1.5dB:level=disabled[aout]", out)


if __name__ == "__main__":
    video, out = sys.argv[1], sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "blackhole"
    if build(video, out, RECIPES[name]):
        chk = subprocess.run(
            ["ffmpeg", "-v", "quiet", "-i", out, "-af",
             "astats=metadata=1:reset=48000,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
             "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        levels = [l.split("=")[1] for l in chk.stdout.splitlines() if "RMS_level" in l]
        print(f"完成：{out}")
        print("每秒音量(dB)：", " ".join(f"{float(x):.0f}" for x in levels if x != "-inf"))
