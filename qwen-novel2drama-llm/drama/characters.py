from __future__ import annotations

from typing import Any


def build_character_cards(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for index, character in enumerate(parsed.get("characters") or []):
        name = character.get("name") or f"角色{index + 1}"
        role = character.get("role_hint") or ("protagonist" if index == 0 else "supporting")
        cards.append({
            "character_id": character.get("character_id") or f"char_{index + 1:03d}",
            "name": name,
            "role": role,
            "personality": "目标强烈、情绪外显、适合短剧高冲突表达" if role == "protagonist" else "推动冲突或揭示信息",
            "visual_profile": {
                "age_range": "20-35",
                "style": "3D真人感，写实影视风，竖屏短剧审美",
                "signature": f"{name}的稳定造型关键词",
            },
            "voice_profile": {"tone": "自然口语化", "pace": "快节奏"},
            "consistency_rules": ["姓名、年龄段、核心气质保持一致", "同一集内服装和发型连续", "关键道具和关系不可随机变化"],
        })
    return cards


def build_relationships(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not cards:
        return []
    protagonist = cards[0]
    relationships: list[dict[str, Any]] = []
    for card in cards[1:]:
        relationships.append({"from": protagonist["character_id"], "to": card["character_id"], "type": "conflict_or_ally", "description": f"{card['name']}与{protagonist['name']}形成剧情推动关系"})
    return relationships


def character_prompt(card: dict[str, Any]) -> str:
    visual = card.get("visual_profile") or {}
    return "，".join([
        "无文字，无海报排版，纯角色定妆图",
        f"角色：{card.get('name')}",
        f"身份：{card.get('role')}",
        str(visual.get("style") or "3D真人感，写实影视风"),
        str(visual.get("signature") or "稳定角色特征"),
        "清晰面部，电影级布光，竖屏9:16",
    ])


def build_character_system(parsed: dict[str, Any]) -> dict[str, Any]:
    cards = build_character_cards(parsed)
    return {"characters": cards, "relationships": build_relationships(cards), "character_prompts": [{"character_id": item["character_id"], "prompt": character_prompt(item)} for item in cards]}
