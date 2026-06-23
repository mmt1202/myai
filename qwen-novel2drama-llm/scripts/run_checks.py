"""跨平台运行项目轻量检查。"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(command: list[str], cwd: Path) -> None:
    """运行命令，失败时直接抛出清晰错误。"""
    print(f"\n>>> {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="运行项目静态检查、数据校验、单元测试和 Python 编译检查。")
    parser.add_argument("--project-root", default=".", help="项目根目录，默认当前目录。")
    parser.add_argument("--skip-compile", action="store_true", help="跳过 compileall 语法检查。")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    python = sys.executable
    commands: list[list[str]] = [
        [python, "scripts/check_project.py", "--project-root", "."],
        [python, "scripts/validate_dataset.py", "--file", "datasets/train.jsonl"],
        [python, "scripts/validate_dataset.py", "--file", "datasets/val.jsonl"],
        [python, "scripts/analyze_dataset.py", "--file", "datasets/train.jsonl"],
        [python, "-m", "unittest", "discover", "-s", "tests"],
    ]
    if not args.skip_compile:
        commands.append([python, "-m", "compileall", "scripts", "inference", "eval", "tests"])

    try:
        for command in commands:
            run_command(command, project_root)
    except subprocess.CalledProcessError as exc:
        print(f"\n检查失败，退出码：{exc.returncode}", file=sys.stderr)
        return exc.returncode

    print("\n全部检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
