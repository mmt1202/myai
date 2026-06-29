from __future__ import annotations

from pathlib import Path
from typing import Any

from drama.media_assets import poll_generation_jobs, submit_character_images, submit_storyboard_videos
from drama.pipeline import build_drama_pipeline
from providers.media_generation import config_from_env, provider_ready


def media_config_from_body(body: dict[str, Any], *, media_type: str):
    provider = str(body.get("provider") or ("image_provider" if media_type == "image" else "video_provider"))
    prefix = str(body.get("env_prefix") or ("FOUNDATION_IMAGE_PROVIDER" if media_type == "image" else "FOUNDATION_VIDEO_PROVIDER"))
    return config_from_env(prefix, provider=provider)


def media_provider_health_api(body: dict[str, Any]) -> dict[str, Any]:
    media_type = str(body.get("media_type") or "image")
    config = media_config_from_body(body, media_type=media_type)
    return {"status": "ok", "output": provider_ready(config)}


def generate_character_images_api(body: dict[str, Any], *, output_root: Path | None = None, transport=None) -> dict[str, Any]:
    config = media_config_from_body(body, media_type="image")
    pipeline = body.get("pipeline") or build_drama_pipeline(str(body.get("text") or body.get("novel_text") or ""), episode_count=int(body.get("episode_count") or 3), platforms=body.get("platforms"))
    root = output_root or Path("outputs/drama_assets")
    result = submit_character_images(pipeline["character_system"], config, asset_root=root / str(body.get("run_id") or "latest"), options=body.get("options") or {}, transport=transport)
    return {"status": "ok", "output": result}


def generate_storyboard_videos_api(body: dict[str, Any], *, output_root: Path | None = None, transport=None) -> dict[str, Any]:
    config = media_config_from_body(body, media_type="video")
    pipeline = body.get("pipeline") or build_drama_pipeline(str(body.get("text") or body.get("novel_text") or ""), episode_count=int(body.get("episode_count") or 3), platforms=body.get("platforms"))
    root = output_root or Path("outputs/drama_assets")
    result = submit_storyboard_videos(pipeline["video_prompts"], config, asset_root=root / str(body.get("run_id") or "latest"), platform=body.get("platform"), options=body.get("options") or {}, transport=transport)
    return {"status": "ok", "output": result}


def poll_media_jobs_api(body: dict[str, Any], *, output_root: Path | None = None, transport=None) -> dict[str, Any]:
    media_type = str(body.get("media_type") or "video")
    config = media_config_from_body(body, media_type=media_type)
    root = output_root or Path("outputs/drama_assets")
    result = poll_generation_jobs(body.get("jobs") or [], config, asset_root=root / str(body.get("run_id") or "latest"), transport=transport)
    return {"status": "ok", "output": result}
