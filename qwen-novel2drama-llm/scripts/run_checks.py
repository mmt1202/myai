"""跨平台运行项目轻量检查。"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


CORE_COMPILE_DIRS = [
    "agent",
    "providers",
    "services",
    "skills",
    "mcp",
    "drama",
    "inference",
    "scripts",
    "eval",
    "evals",
    "tests",
]


def existing_compile_dirs(project_root: Path) -> list[str]:
    return [item for item in CORE_COMPILE_DIRS if (project_root / item).exists()]


def run_command(command: list[str], cwd: Path) -> None:
    """运行命令，失败时直接抛出清晰错误。"""
    print(f"\n>>> {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="运行项目静态检查、数据校验、单元测试和 Python 编译检查。")
    parser.add_argument("--project-root", default=".", help="项目根目录，默认当前目录。")
    parser.add_argument("--skip-compile", action="store_true", help="跳过 compileall 语法检查。")
    parser.add_argument("--skip-data", action="store_true", help="跳过数据集校验和分析。")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    python = sys.executable
    commands: list[list[str]] = [[python, "scripts/check_project.py", "--project-root", "."]]
    if not args.skip_data:
        commands.extend([
            [python, "scripts/validate_dataset.py", "--file", "datasets/train.jsonl"],
            [python, "scripts/validate_dataset.py", "--file", "datasets/val.jsonl"],
            [python, "scripts/analyze_dataset.py", "--file", "datasets/train.jsonl"],
        ])
    commands.extend([
        [python, "-m", "unittest", "discover", "-s", "tests"],
        [python, "-m", "skills.registry", "--registry", "configs/skills/foundation_skills.json", "--validate"],
        [python, "-m", "mcp.adapter", "--registry", "configs/skills/foundation_skills.json", "--validate"],
        [python, "inference/model_router.py", "--request", "examples/route_request.json"],
    ])
    if not args.skip_compile:
        commands.append([python, "-m", "compileall", *existing_compile_dirs(project_root)])

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
