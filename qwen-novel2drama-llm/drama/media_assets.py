from __future__ import annotations

from pathlib import Path
from typing import Any

from providers.media_generation import MediaProviderConfig, poll_media_generation, save_asset_record, submit_media_generation


def submit_character_images(character_system: dict[str, Any], config: MediaProviderConfig, *, asset_root: Path, options: dict[str, Any] | None = None, transport=None) -> dict[str, Any]:
    jobs = []
    kwargs = {"transport": transport} if transport else {}
    for item in character_system.get("character_prompts") or []:
        prompt = str(item.get("prompt") or "")
        if not prompt:
            continue
        job = submit_media_generation(config, media_type="image", prompt=prompt, negative_prompt="无文字，无水印，无logo", options={"aspect_ratio": "9:16", **(options or {})}, **kwargs)
        record = save_asset_record(job, asset_root / "images")
        jobs.append({"character_id": item.get("character_id"), "job": job.to_dict(), "record": record})
    return {"status": "ok", "job_count": len(jobs), "jobs": jobs}


def submit_storyboard_videos(video_prompts: dict[str, Any], config: MediaProviderConfig, *, asset_root: Path, platform: str | None = None, options: dict[str, Any] | None = None, transport=None) -> dict[str, Any]:
    jobs = []
    kwargs = {"transport": transport} if transport else {}
    for item in video_prompts.get("items") or []:
        if platform and item.get("platform") != platform:
            continue
        prompt = str(item.get("prompt") or "")
        if not prompt:
            continue
        job = submit_media_generation(config, media_type="video", prompt=prompt, negative_prompt=item.get("negative_prompt"), options={"duration_seconds": item.get("duration_seconds") or 8, "aspect_ratio": item.get("aspect_ratio") or "9:16", **(options or {})}, **kwargs)
        record = save_asset_record(job, asset_root / "videos")
        jobs.append({"shot_id": item.get("shot_id"), "platform": item.get("platform"), "job": job.to_dict(), "record": record})
    return {"status": "ok", "job_count": len(jobs), "jobs": jobs}


def poll_generation_jobs(jobs: list[dict[str, Any]], config: MediaProviderConfig, *, asset_root: Path, transport=None) -> dict[str, Any]:
    results = []
    kwargs = {"transport": transport} if transport else {}
    for item in jobs:
        job_data = item.get("job") or item
        job = poll_media_generation(config, job_id=str(job_data.get("job_id")), media_type=str(job_data.get("media_type") or "video"), prompt=str(job_data.get("prompt") or ""), **kwargs)
        record = save_asset_record(job, asset_root / "status")
        results.append({"job": job.to_dict(), "record": record})
    completed = sum(1 for item in results if item["job"].get("status") in {"succeeded", "completed", "done"})
    return {"status": "ok", "job_count": len(results), "completed_count": completed, "results": results}
