"""从用户明确授权的网页采集文本，生成待标注原始语料 JSONL。"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

USER_AGENT = "qwen-novel2drama-llm-data-collector/0.1"
BLOCK_TAGS = {"script", "style", "noscript", "svg", "canvas", "header", "footer", "nav"}


class TextExtractor(HTMLParser):
    """轻量 HTML 正文提取器，避免引入额外依赖。"""

    def __init__(self) -> None:
        super().__init__()
        self._skip_stack: list[str] = []
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in BLOCK_TAGS:
            self._skip_stack.append(tag.lower())
        if tag.lower() in {"p", "br", "div", "section", "article", "li", "h1", "h2", "h3"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._skip_stack and self._skip_stack[-1] == tag:
            self._skip_stack.pop()
        if tag in {"p", "div", "section", "article", "li"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_stack:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)

    def get_text(self) -> str:
        text = " ".join(self._chunks)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        return text.strip()


def load_sources(path: Path) -> list[dict[str, Any]]:
    """读取 JSONL 来源清单。"""
    if not path.exists():
        raise FileNotFoundError(f"来源清单不存在：{path}")
    sources: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as reader:
        for line_no, line in enumerate(reader, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            if not item.get("url"):
                raise ValueError(f"第 {line_no} 行缺少 url")
            if item.get("allow_training") is not True:
                raise ValueError(f"第 {line_no} 行 allow_training 必须为 true，表示你确认该来源可用于训练")
            if not item.get("license"):
                raise ValueError(f"第 {line_no} 行缺少 license/授权说明")
            sources.append(item)
    return sources


def can_fetch(url: str, user_agent: str) -> bool:
    """检查 robots.txt 是否允许抓取。"""
    parsed = urllib.parse.urlparse(url)
    robots_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception:  # noqa: BLE001 - robots 读取失败时保守跳过
        return False
    return parser.can_fetch(user_agent, url)


def fetch_html(url: str, timeout: int, user_agent: str) -> str:
    """下载网页 HTML。"""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - 只处理用户声明授权 URL
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            raise ValueError(f"非 HTML 响应：{content_type}")
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def html_to_text(html: str) -> str:
    extractor = TextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def main() -> int:
    parser = argparse.ArgumentParser(description="采集用户授权网页文本，输出 raw corpus JSONL。")
    parser.add_argument("--sources", required=True, help="来源 JSONL，每行包含 url/license/allow_training。")
    parser.add_argument("--output", required=True, help="输出 JSONL 路径，建议写入 datasets/raw_corpus.jsonl。")
    parser.add_argument("--delay", type=float, default=2.0, help="每个请求之间的延迟秒数，默认 2。")
    parser.add_argument("--timeout", type=int, default=30, help="请求超时秒数，默认 30。")
    parser.add_argument("--ignore-robots", action="store_true", help="仅用于你自有站点调试；默认严格遵守 robots.txt。")
    args = parser.parse_args()

    sources = load_sources(Path(args.sources))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    success = 0
    failed = 0
    with output_path.open("w", encoding="utf-8") as writer:
        for item in sources:
            url = item["url"]
            try:
                if not args.ignore_robots and not can_fetch(url, USER_AGENT):
                    raise PermissionError(f"robots.txt 不允许抓取：{url}")
                html = fetch_html(url, args.timeout, USER_AGENT)
                text = html_to_text(html)
                if len(text) < 100:
                    raise ValueError("正文过短，疑似提取失败")
                record = {
                    "url": url,
                    "source_name": item.get("source_name", ""),
                    "license": item["license"],
                    "text": text,
                }
                writer.write(json.dumps(record, ensure_ascii=False) + "\n")
                success += 1
            except (urllib.error.URLError, TimeoutError, ValueError, PermissionError) as exc:
                failed += 1
                print(f"采集失败：{url}，原因：{exc}", file=sys.stderr)
            time.sleep(max(args.delay, 0))
    print(f"采集完成：成功 {success}，失败 {failed}，输出：{output_path}")
    return 0 if success > 0 or not sources else 1


if __name__ == "__main__":
    raise SystemExit(main())
