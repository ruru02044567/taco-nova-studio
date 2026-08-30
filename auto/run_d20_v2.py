# -*- coding: utf-8 -*-
"""D20 v2：三段都用「同一張起始圖」重生，不接尾幀。

v1 失敗原因（2026-08-30 逐幀驗片）：
  接龍拿尾幀當下一段首幀 → 第 2 段模型自己編劇（沒塗哈士奇、自己跳進黑桶），
  第 3 段從已經半黑的尾幀繼續 → Taco 變成黑白花臉＝換了一隻狗，
  還長出憑空的黑漿細線與脫臼似的嘴。錯誤會沿著接龍累積放大。

v2 作法：三段都錨在 d20s1_scene_ACCEPTED.png，構圖與角色不會漂；
  每段只要求「一個模型畫得出來的物理動作」，不要求執行連續劇情。
"""
import os, subprocess, sys, time
sys.stdout.reconfigure(encoding='utf-8')

PY = r"C:\Users\TUF Gaming\ai-video-local\venv\Scripts\python.exe"
H3 = r"C:\Users\TUF Gaming\ai-video-local\h3-tools\run_h3.py"
COMFY_IN = r"C:\Users\TUF Gaming\ai-video-local\ComfyUI\input"
HERE = os.path.dirname(os.path.abspath(__file__))
FIRST = os.path.join(HERE, 'clips', 'd20s1_scene_ACCEPTED.png')
PDIR = os.path.join(HERE, 'clips', 'd20_v2')
OUT = os.path.join(HERE, 'clips', 'd20_v2_out')
LEN, W, H = 124, 480, 832
SEGS = [('s1', 771), ('s2', 5150), ('s3', 8823)]

os.makedirs(OUT, exist_ok=True)
ff = 'd20v2_first.png'
r = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', FIRST, '-vf',
                    'scale=%d:%d' % (W, H), '-frames:v', '1', '-update', '1',
                    os.path.join(COMFY_IN, ff)])
if r.returncode != 0:
    sys.exit('[X] 首幀落地失敗')
print('[ok] 首幀 -> %s（三段共用）' % ff, flush=True)

t0 = time.time()
for name, seed in SEGS:
    out = os.path.join(OUT, name + '.mp4')
    if os.path.exists(out):
        print('[skip] %s 已存在' % name, flush=True)
        continue
    prompt = open(os.path.join(PDIR, 'seg%s.txt' % name[1]), encoding='utf-8').read().strip()
    print('=== %s seed=%d（錨定同一張起始圖）===' % (name, seed), flush=True)
    t = time.time()
    r = subprocess.run([PY, '-u', H3, out, str(W), str(H), str(LEN), str(seed),
                        '--first-frame', ff, '--prompt', prompt])
    if r.returncode != 0 or not os.path.exists(out):
        sys.exit('[X] %s 生成失敗 exit=%d' % (name, r.returncode))
    print('[ok] %s 完成 %.1f 分' % (name, (time.time() - t) / 60), flush=True)
print('RESULT=OK 全程 %.0f 分' % ((time.time() - t0) / 60), flush=True)
