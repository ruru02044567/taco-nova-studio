# -*- coding: utf-8 -*-
r"""_run_d11.py — d11s1 手動生產 driver（2026-08-20 凌晨，賢賢授權值班發布）

為什麼手動：tick 的煞車被 d10s1 awaiting_review 擋住（設計如此），
但今晚要並行推 d11。完全沿用 pipeline.py 的函式與 state 慣例，
只是把 cmd_tick 的生成段拆成兩階段，中間留給人（AI 值班）做黑點眉校準：

  python auto\_run_d11.py scene   # FLUX 場景圖（含抗 AI 感尾段）→ 停，等目視校準眉點
  python auto\_run_d11.py video   # Wan 2.2 生片 → 送待審核

GPU 禮讓：comfy_api 會排隊等 d10s1 視窗的工作做完，不插隊。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline  # noqa: E402
import plan_model  # noqa: E402

KEY = "d11s1"
DAY, SLOT = 11, 1


def get_item():
    sched = pipeline.load(pipeline.SCHEDULE, None)
    return next(i for i in sched["schedule"] if i["day"] == DAY and i["slot"] == SLOT)


def stage_scene():
    item = get_item()
    state = pipeline.load(pipeline.STATE, {})
    st = state.get(KEY, {})

    plan = plan_model.decide(item.get("videoPrompt") or item["title"])
    if plan["model"] == "BLOCKED":
        pipeline.log(f"⛔ {KEY} 被 plan_model 擋下：{plan.get('bottleneck')}")
        sys.exit(1)
    st["model_selection"] = plan
    pipeline.log(f"{KEY} 模型判斷：{plan['model']}（{plan.get('motion_class')}，"
                 f"瓶頸「{plan.get('bottleneck') or '未分類'}」）")

    scene = pipeline.CLIPS / f"{KEY}_scene.jpg"
    prompt_file = pipeline.CLIPS / f"{KEY}_scene.txt"
    prompt_file.write_text(item["scenePrompt"], encoding="utf-8")
    if not pipeline.ensure_comfy():
        pipeline.log("ComfyUI 起不來")
        sys.exit(1)
    ok, out = pipeline.run("gen_scene_flux.py",
                           "--prompt-file", prompt_file, "--out", scene,
                           "--width", "704", "--height", "1280", timeout=1800)
    if not ok or not scene.exists():
        pipeline.log(f"FLUX 生圖失敗：{out[-300:]}")
        sys.exit(1)
    st["scene"] = str(scene)
    st["scene_source"] = "flux"
    state[KEY] = st
    pipeline.save(pipeline.STATE, state)
    pipeline.log(f"{KEY} 場景圖 OK：{scene.name} → 停，等眉點校準後跑 video 階段")


def stage_video():
    item = get_item()
    state = pipeline.load(pipeline.STATE, {})
    st = state.get(KEY, {})
    scene = Path(st.get("scene", ""))
    if not scene.is_file():
        pipeline.log("沒有場景圖，先跑 scene 階段")
        sys.exit(1)

    video = pipeline.CLIPS / f"{KEY}.mp4"
    vp = pipeline.CLIPS / f"{KEY}_video.txt"
    vp.write_text(item["videoPrompt"], encoding="utf-8")
    if not pipeline.ensure_comfy():
        pipeline.log("ComfyUI 起不來")
        sys.exit(1)
    steps = plan_model.POLICY["local_best_config"]["steps"]
    ok, out = pipeline.run("make_video_local_5s.py", scene, vp, video,
                           "--steps", str(steps), timeout=1800)
    if not ok or not video.exists():
        fails = st.get("local_fails", 0) + 1
        st["local_fails"] = fails
        st["local_last_error"] = out[-300:] if out else ""
        state[KEY] = st
        pipeline.save(pipeline.STATE, state)
        pipeline.log(f"{KEY} 生片失敗（第 {fails} 次）")
        sys.exit(1)
    st.update({"video": str(video), "source": "local", "local_fails": 0,
               "awaiting_review": True})
    state[KEY] = st
    pipeline.save(pipeline.STATE, state)
    pipeline.to_review(KEY, item, video, "本機 Wan 2.2（值班手動）")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "scene"
    {"scene": stage_scene, "video": stage_video}[stage]()
