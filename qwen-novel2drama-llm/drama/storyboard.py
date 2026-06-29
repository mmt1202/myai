from __future__ import annotations

from typing import Any


SHOT_TYPES = ["特写", "中近景", "过肩镜头", "全景", "手持跟拍"]


def build_storyboard(outline: dict[str, Any], character_system: dict[str, Any]) -> dict[str, Any]:
    characters = character_system.get("characters") or []
    main_name = characters[0]["name"] if characters else "主角"
    episodes_out: list[dict[str, Any]] = []
    for episode in outline.get("episodes") or []:
        structure = episode.get("structure") or {}
        beats = [structure.get("opening_hook")] + list(structure.get("conflict_escalation") or []) + [structure.get("turning_point"), structure.get("ending_cliffhanger")]
        shots: list[dict[str, Any]] = []
        for index, beat in enumerate([item for item in beats if item]):
            shots.append({
                "shot_id": f"{episode['episode_id']}_shot_{index + 1:03d}",
                "episode_id": episode["episode_id"],
                "order": index + 1,
                "beat": beat,
                "shot_type": SHOT_TYPES[index % len(SHOT_TYPES)],
                "camera": "竖屏9:16，电影感，主体居中，情绪优先",
                "action": beat,
                "dialogue": f"{main_name}：这件事没有这么简单。" if index % 2 == 0 else "",
                "voiceover": "推动剧情快速进入下一个冲突点" if index % 2 == 1 else "",
                "duration_seconds": 8,
                "scene": "都市室内/关键冲突场景",
            })
        episodes_out.append({"episode_id": episode["episode_id"], "shots": shots, "shot_count": len(shots), "estimated_duration_seconds": sum(item["duration_seconds"] for item in shots)})
    return {"episodes": episodes_out, "total_shots": sum(item["shot_count"] for item in episodes_out)}


def flatten_shots(storyboard: dict[str, Any]) -> list[dict[str, Any]]:
    shots: list[dict[str, Any]] = []
    for episode in storyboard.get("episodes") or []:
        shots.extend(episode.get("shots") or [])
    return shots
