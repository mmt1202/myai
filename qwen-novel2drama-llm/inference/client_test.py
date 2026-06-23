"""测试 FastAPI /generate 接口。"""
from __future__ import annotations

import argparse
import requests


def main() -> int:
    parser = argparse.ArgumentParser(description="调用本地 novel2drama API 生成接口。")
    parser.add_argument("--url", default="http://127.0.0.1:8000/generate", help="/generate 接口地址。")
    args = parser.parse_args()
    payload = {"prompt": "请把女主订婚宴被背叛的片段改成 60 秒竖屏分镜。", "max_new_tokens": 512, "temperature": 0.7}
    response = requests.post(args.url, json=payload, timeout=120)
    response.raise_for_status()
    print(response.json()["result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
