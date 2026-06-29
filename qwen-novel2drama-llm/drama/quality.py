from __future__ import annotations

from typing import Any


def quality_story(outline: dict[str, Any], storyboard: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    expected = {item.get("episode_id") for item in outline.get("episodes") or []}
    actual = {item.get("episode_id") for item in storyboard.get("episodes") or []}
    for episode_id in expected - actual:
        issues.append({"type": "episode_without_shots", "level": "high", "message": str(episode_id)})
    for episode in storyboard.get("episodes") or []:
        if int(episode.get("shot_count") or 0) <= 0:
            issues.append({"type": "empty_episode", "level": "high", "message": str(episode.get("episode_id"))})
    return issues


def quality_characters(character_system: dict[str, Any], prompts: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    prompt_text = "\n".join(str(item.get("prompt") or "") for item in prompts.get("items") or [])
    for card in character_system.get("characters") or []:
        name = str(card.get("name") or "")
        if name and name not in prompt_text:
            issues.append({"type": "character_reference_missing", "level": "medium", "message": name})
    return issues


def quality_shots(storyboard: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for episode in storyboard.get("episodes") or []:
        for shot in episode.get("shots") or []:
            if not shot.get("action"):
                issues.append({"type": "shot_action_missing", "level": "medium", "shot_id": shot.get("shot_id")})
            if int(shot.get("duration_seconds") or 0) <= 0:
                issues.append({"type": "shot_duration_invalid", "level": "high", "shot_id": shot.get("shot_id")})
    return issues


def quality_prompts(prompts: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for item in prompts.get("items") or []:
        if not item.get("prompt"):
            issues.append({"type": "video_prompt_missing", "level": "high", "shot_id": item.get("shot_id")})
    return issues


def quality_report(outline: dict[str, Any], character_system: dict[str, Any], storyboard: dict[str, Any], prompts: dict[str, Any]) -> dict[str, Any]:
    issues = quality_story(outline, storyboard) + quality_characters(character_system, prompts) + quality_shots(storyboard) + quality_prompts(prompts)
    high = sum(1 for item in issues if item.get("level") == "high")
    medium = sum(1 for item in issues if item.get("level") == "medium")
    return {"status": "passed" if high == 0 else "failed", "issue_count": len(issues), "high_count": high, "medium_count": medium, "issues": issues}
