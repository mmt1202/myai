from __future__ import annotations

from typing import Any


def build_episode_outline(parsed: dict[str, Any], *, episode_count: int = 3) -> dict[str, Any]:
    chapters = parsed.get("chapters") or []
    plotlines = parsed.get("plotlines") or []
    characters = parsed.get("characters") or []
    protagonist = characters[0]["name"] if characters else "主角"
    episodes: list[dict[str, Any]] = []
    total = max(1, int(episode_count))
    for index in range(total):
        source = plotlines[index % len(plotlines)] if plotlines else {"beats": [], "title": "原创"}
        beats = source.get("beats") or []
        core = beats[0] if beats else f"{protagonist}遭遇新的冲突"
        hook = source.get("conflict_hint") or (beats[-1] if beats else f"{protagonist}发现更大的秘密")
        episodes.append({
            "episode_id": f"ep_{index + 1:03d}",
            "title": f"第{index + 1}集：{source.get('title') or '命运转折'}",
            "logline": core,
            "structure": {
                "opening_hook": core,
                "conflict_escalation": beats[1:4] or [f"{protagonist}被迫做出选择"],
                "turning_point": beats[3] if len(beats) > 3 else hook,
                "ending_cliffhanger": hook,
            },
            "target_duration_seconds": 90,
            "platform_hook": f"3秒内抛出冲突：{core}",
        })
    return {"series_title": "短剧改编大纲", "source_chapter_count": len(chapters), "episode_count": len(episodes), "episodes": episodes}


def build_series_bible(parsed: dict[str, Any], outline: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": outline.get("series_title") or "短剧改编",
        "genre": (parsed.get("worldview") or {}).get("genre"),
        "premise": outline.get("episodes", [{}])[0].get("logline", "主角进入高压冲突"),
        "characters": parsed.get("characters") or [],
        "episode_count": outline.get("episode_count") or 0,
        "tone": "高冲突、强钩子、快节奏、竖屏短剧",
    }
