from __future__ import annotations

from pathlib import Path
from typing import Any

from drama.characters import build_character_system
from drama.novel_parser import parse_novel
from drama.outline import build_episode_outline, build_series_bible
from drama.pipeline import build_drama_pipeline, write_pipeline_artifacts
from drama.quality import quality_report
from drama.storyboard import build_storyboard
from drama.video_prompts import generate_video_prompts


def drama_parse_api(body: dict[str, Any]) -> dict[str, Any]:
    text = str(body.get("text") or body.get("novel_text") or "")
    return {"status": "ok", "output": parse_novel(text)}


def drama_outline_api(body: dict[str, Any]) -> dict[str, Any]:
    parsed = body.get("parsed") or parse_novel(str(body.get("text") or body.get("novel_text") or ""))
    outline = build_episode_outline(parsed, episode_count=int(body.get("episode_count") or 3))
    return {"status": "ok", "output": {"outline": outline, "series_bible": build_series_bible(parsed, outline)}}


def drama_characters_api(body: dict[str, Any]) -> dict[str, Any]:
    parsed = body.get("parsed") or parse_novel(str(body.get("text") or body.get("novel_text") or ""))
    return {"status": "ok", "output": build_character_system(parsed)}


def drama_storyboard_api(body: dict[str, Any]) -> dict[str, Any]:
    parsed = body.get("parsed") or parse_novel(str(body.get("text") or body.get("novel_text") or ""))
    outline = body.get("outline") or build_episode_outline(parsed, episode_count=int(body.get("episode_count") or 3))
    characters = body.get("character_system") or build_character_system(parsed)
    return {"status": "ok", "output": build_storyboard(outline, characters)}


def drama_prompts_api(body: dict[str, Any]) -> dict[str, Any]:
    parsed = body.get("parsed") or parse_novel(str(body.get("text") or body.get("novel_text") or ""))
    outline = body.get("outline") or build_episode_outline(parsed, episode_count=int(body.get("episode_count") or 3))
    characters = body.get("character_system") or build_character_system(parsed)
    storyboard = body.get("storyboard") or build_storyboard(outline, characters)
    platforms = body.get("platforms") or ["jimeng", "kling", "runway", "pika"]
    return {"status": "ok", "output": generate_video_prompts(storyboard, characters, platforms=platforms)}


def drama_quality_api(body: dict[str, Any]) -> dict[str, Any]:
    pipeline = body.get("pipeline") or build_drama_pipeline(str(body.get("text") or body.get("novel_text") or ""), episode_count=int(body.get("episode_count") or 3), platforms=body.get("platforms"))
    report = quality_report(pipeline["outline"], pipeline["character_system"], pipeline["storyboard"], pipeline["video_prompts"])
    return {"status": "ok", "output": report}


def drama_pipeline_api(body: dict[str, Any], *, output_root: Path | None = None) -> dict[str, Any]:
    result = build_drama_pipeline(str(body.get("text") or body.get("novel_text") or ""), episode_count=int(body.get("episode_count") or 3), platforms=body.get("platforms"))
    output: dict[str, Any] = {"pipeline": result}
    if body.get("write_artifacts"):
        root = output_root or Path("outputs/drama")
        run_id = str(body.get("run_id") or body.get("request_id") or "latest")
        output["artifacts"] = write_pipeline_artifacts(result, root / run_id)
    return {"status": "ok", "output": output}
