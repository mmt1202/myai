from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from drama.characters import build_character_system
from drama.novel_parser import parse_novel
from drama.outline import build_episode_outline, build_series_bible
from drama.quality import quality_report
from drama.storyboard import build_storyboard, flatten_shots
from drama.video_prompts import generate_video_prompts


def build_drama_pipeline(text: str, *, episode_count: int = 3, platforms: list[str] | None = None) -> dict[str, Any]:
    parsed = parse_novel(text)
    outline = build_episode_outline(parsed, episode_count=episode_count)
    bible = build_series_bible(parsed, outline)
    character_system = build_character_system(parsed)
    storyboard = build_storyboard(outline, character_system)
    video_prompts = generate_video_prompts(storyboard, character_system, platforms=platforms)
    quality = quality_report(outline, character_system, storyboard, video_prompts)
    assets = {
        "character_cards": character_system.get("characters") or [],
        "character_prompts": character_system.get("character_prompts") or [],
        "video_prompts": video_prompts.get("items") or [],
    }
    return {
        "status": "ok",
        "parsed": parsed,
        "series_bible": bible,
        "outline": outline,
        "character_system": character_system,
        "storyboard": storyboard,
        "shots": flatten_shots(storyboard),
        "video_prompts": video_prompts,
        "quality": quality,
        "assets": assets,
    }


def write_pipeline_artifacts(result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "parsed": output_dir / "parsed.json",
        "series_bible": output_dir / "series_bible.json",
        "outline": output_dir / "outline.json",
        "characters": output_dir / "characters.json",
        "storyboard": output_dir / "storyboard.json",
        "video_prompts": output_dir / "video_prompts.json",
        "quality": output_dir / "quality.json",
        "assets": output_dir / "assets.json",
        "full_pipeline": output_dir / "full_pipeline.json",
    }
    files["parsed"].write_text(json.dumps(result["parsed"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["series_bible"].write_text(json.dumps(result["series_bible"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["outline"].write_text(json.dumps(result["outline"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["characters"].write_text(json.dumps(result["character_system"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["storyboard"].write_text(json.dumps(result["storyboard"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["video_prompts"].write_text(json.dumps(result["video_prompts"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["quality"].write_text(json.dumps(result["quality"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["assets"].write_text(json.dumps(result["assets"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["full_pipeline"].write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"output_dir": str(output_dir), "files": {key: str(path) for key, path in files.items()}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a novel-to-short-drama production package.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--episode-count", type=int, default=3)
    parser.add_argument("--platforms", default="jimeng,kling,runway,pika")
    args = parser.parse_args()
    text = Path(args.input).read_text(encoding="utf-8")
    result = build_drama_pipeline(text, episode_count=args.episode_count, platforms=[item.strip() for item in args.platforms.split(",") if item.strip()])
    artifacts = write_pipeline_artifacts(result, Path(args.output_dir))
    print(json.dumps({"status": result["status"], "quality": result["quality"], "artifacts": artifacts}, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
