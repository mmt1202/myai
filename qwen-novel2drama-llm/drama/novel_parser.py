from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


CHAPTER_RE = re.compile(r"(?m)^\s*(第[一二三四五六七八九十百千万0-9]+[章节回幕].*|Chapter\s+\d+.*)\s*$")
NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,4}")


@dataclass(frozen=True)
class NovelChapter:
    chapter_id: str
    title: str
    text: str
    index: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def split_chapters(text: str) -> list[NovelChapter]:
    source = text.strip()
    if not source:
        return []
    matches = list(CHAPTER_RE.finditer(source))
    if not matches:
        return [NovelChapter(chapter_id="chapter_001", title="正文", text=source, index=1)]
    chapters: list[NovelChapter] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(source)
        title = match.group(1).strip()
        body = source[start:end].strip()
        chapters.append(NovelChapter(chapter_id=f"chapter_{idx + 1:03d}", title=title, text=body, index=idx + 1))
    return chapters


def extract_characters(text: str, *, max_characters: int = 12) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for name in NAME_RE.findall(text):
        if name.startswith(("第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十")):
            continue
        if name in {"一个", "他们", "我们", "你们", "这是", "然后", "因为", "所以", "但是", "如果", "已经", "没有"}:
            continue
        counts[name] = counts.get(name, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:max_characters]
    return [{"character_id": f"char_{index + 1:03d}", "name": name, "mentions": count, "role_hint": "protagonist" if index == 0 else "supporting"} for index, (name, count) in enumerate(ranked)]


def extract_worldview(text: str) -> dict[str, Any]:
    keywords = {
        "都市": ["公司", "总裁", "医院", "订婚", "豪门", "集团"],
        "古装": ["皇帝", "王爷", "宫中", "将军", "江湖", "宗门"],
        "玄幻": ["灵力", "修炼", "妖兽", "秘境", "飞升"],
        "科幻": ["星舰", "机甲", "AI", "宇宙", "基地"],
    }
    scores = {genre: sum(text.count(word) for word in words) for genre, words in keywords.items()}
    genre = max(scores, key=scores.get) if scores else "未知"
    if scores.get(genre, 0) == 0:
        genre = "现实/通用"
    return {"genre": genre, "signals": scores, "setting_hint": genre}


def extract_plotlines(chapters: list[NovelChapter]) -> list[dict[str, Any]]:
    plotlines: list[dict[str, Any]] = []
    for chapter in chapters:
        sentences = [item.strip() for item in re.split(r"[。！？!?\n]+", chapter.text) if item.strip()]
        beats = sentences[:5]
        plotlines.append({"chapter_id": chapter.chapter_id, "title": chapter.title, "beats": beats, "conflict_hint": beats[-1] if beats else ""})
    return plotlines


def parse_novel(text: str) -> dict[str, Any]:
    chapters = split_chapters(text)
    return {
        "chapter_count": len(chapters),
        "chapters": [chapter.to_dict() for chapter in chapters],
        "characters": extract_characters(text),
        "worldview": extract_worldview(text),
        "plotlines": extract_plotlines(chapters),
    }
