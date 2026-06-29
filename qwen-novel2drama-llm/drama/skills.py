from __future__ import annotations

from typing import Any

from drama.characters import build_character_system
from drama.novel_parser import parse_novel
from drama.outline import build_episode_outline
from drama.pipeline import build_drama_pipeline
from drama.quality import quality_report
from drama.storyboard import build_storyboard
from drama.video_prompts import generate_video_prompts


def novel_to_outline(text: str, episode_count: int = 3) -> dict[str, Any]:
    parsed = parse_novel(text)
    outline = build_episode_outline(parsed, episode_count=episode_count)
    return {"parsed": parsed, "outline": outline}


def character_design(text: str) -> dict[str, Any]:
    parsed = parse_novel(text)
    return build_character_system(parsed)


def scene_design(text: str, episode_count: int = 3) -> dict[str, Any]:
    parsed = parse_novel(text)
    outline = build_episode_outline(parsed, episode_count=episode_count)
    characters = build_character_system(parsed)
    storyboard = build_storyboard(outline, characters)
    scenes = []
    for episode in storyboard.get("episodes") or []:
        for shot in episode.get("shots") or []:
            scenes.append({"episode_id": episode.get("episode_id"), "shot_id": shot.get("shot_id"), "scene": shot.get("scene"), "camera": shot.get("camera")})
    return {"scene_count": len(scenes), "scenes": scenes}


def storyboard(text: str, episode_count: int = 3) -> dict[str, Any]:
    parsed = parse_novel(text)
    outline = build_episode_outline(parsed, episode_count=episode_count)
    characters = build_character_system(parsed)
    return build_storyboard(outline, characters)


def video_prompt(text: str, episode_count: int = 3, platforms: list[str] | None = None) -> dict[str, Any]:
    pipeline = build_drama_pipeline(text, episode_count=episode_count, platforms=platforms)
    return pipeline["video_prompts"]


def dubbing_script(text: str, episode_count: int = 3) -> dict[str, Any]:
    pipeline = build_drama_pipeline(text, episode_count=episode_count, platforms=["jimeng"])
    lines = []
    for shot in pipeline.get("shots") or []:
        if shot.get("dialogue"):
            lines.append({"shot_id": shot.get("shot_id"), "type": "dialogue", "text": shot.get("dialogue")})
        if shot.get("voiceover"):
            lines.append({"shot_id": shot.get("shot_id"), "type": "voiceover", "text": shot.get("voiceover")})
    return {"line_count": len(lines), "lines": lines}


def hook_twist(text: str, episode_count: int = 3) -> dict[str, Any]:
    parsed = parse_novel(text)
    outline = build_episode_outline(parsed, episode_count=episode_count)
    hooks = []
    for episode in outline.get("episodes") or []:
        structure = episode.get("structure") or {}
        hooks.append({"episode_id": episode.get("episode_id"), "opening_hook": structure.get("opening_hook"), "ending_cliffhanger": structure.get("ending_cliffhanger")})
    return {"hook_count": len(hooks), "hooks": hooks}


def quality_review(text: str, episode_count: int = 3, platforms: list[str] | None = None) -> dict[str, Any]:
    pipeline = build_drama_pipeline(text, episode_count=episode_count, platforms=platforms)
    return quality_report(pipeline["outline"], pipeline["character_system"], pipeline["storyboard"], pipeline["video_prompts"])
