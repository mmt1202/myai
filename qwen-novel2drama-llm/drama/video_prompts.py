from __future__ import annotations

from typing import Any


PLATFORM_STYLES = {
    "jimeng": "即梦AI，3D真人感，写实影视风，竖屏9:16，电影级布光，动作连贯",
    "kling": "可灵AI，真实人物运动，镜头稳定，竖屏短剧质感，细节自然",
    "runway": "Runway cinematic vertical video, realistic actors, dramatic lighting, smooth motion",
    "pika": "Pika vertical drama shot, realistic cinematic style, clear action, emotional expression",
}

NEGATIVE_PROMPT = "无文字，无水印，无logo，无海报排版，避免畸形手指，避免面部崩坏，避免穿帮，避免角色外貌漂移"


def platform_prompt(shot: dict[str, Any], *, platform: str = "jimeng", character_prompts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    style = PLATFORM_STYLES.get(platform, PLATFORM_STYLES["jimeng"])
    character_hint = "；".join(item.get("prompt", "") for item in (character_prompts or [])[:2])
    prompt = "，".join([
        style,
        f"场景：{shot.get('scene')}",
        f"镜头：{shot.get('shot_type')}，{shot.get('camera')}",
        f"动作：{shot.get('action')}",
        f"情绪/剧情：{shot.get('beat')}",
        character_hint,
    ])
    return {"shot_id": shot.get("shot_id"), "platform": platform, "prompt": prompt, "negative_prompt": NEGATIVE_PROMPT, "duration_seconds": shot.get("duration_seconds") or 8, "aspect_ratio": "9:16"}


def generate_video_prompts(storyboard: dict[str, Any], character_system: dict[str, Any], *, platforms: list[str] | None = None) -> dict[str, Any]:
    selected = platforms or ["jimeng", "kling", "runway", "pika"]
    character_prompts = character_system.get("character_prompts") or []
    items: list[dict[str, Any]] = []
    for episode in storyboard.get("episodes") or []:
        for shot in episode.get("shots") or []:
            for platform in selected:
                items.append(platform_prompt(shot, platform=platform, character_prompts=character_prompts))
    return {"prompt_count": len(items), "platforms": selected, "items": items}
