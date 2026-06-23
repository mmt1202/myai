"""检查训练/推理环境是否准备就绪。"""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from typing import Any

PACKAGES = ["torch", "transformers", "peft", "fastapi", "uvicorn", "pydantic", "requests"]


def package_available(name: str) -> bool:
    """只检查包是否可发现，不导入重型依赖。"""
    return importlib.util.find_spec(name) is not None


def torch_status() -> dict[str, Any]:
    """可选导入 torch，检查 CUDA 状态。"""
    try:
        import torch  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001 - 环境诊断需要捕获导入错误
        return {"installed": False, "error": str(exc)}
    return {
        "installed": True,
        "version": getattr(torch, "__version__", "unknown"),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
        "cuda_version": getattr(torch.version, "cuda", None),
    }


def command_version(command: str) -> str | None:
    """读取命令版本/帮助信息的第一行。"""
    path = shutil.which(command)
    if not path:
        return None
    try:
        result = subprocess.run([command, "--help"], text=True, capture_output=True, timeout=10, check=False)
    except Exception:  # noqa: BLE001 - 命令存在但无法执行时返回路径即可
        return path
    first_line = (result.stdout or result.stderr or "").splitlines()
    return first_line[0] if first_line else path


def build_report(check_torch: bool) -> dict[str, Any]:
    """生成环境报告。"""
    report: dict[str, Any] = {
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "executables": {
            "python": shutil.which("python") or shutil.which("python3"),
            "pip": shutil.which("pip") or shutil.which("pip3"),
            "llamafactory-cli": shutil.which("llamafactory-cli"),
        },
        "packages_found": {name: package_available(name) for name in PACKAGES},
        "llamafactory_help": command_version("llamafactory-cli"),
    }
    if check_torch:
        report["torch"] = torch_status()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 Python、依赖、CUDA 和 LLaMA-Factory 环境。")
    parser.add_argument("--check-torch", action="store_true", help="导入 torch 并检查 CUDA 状态。")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出。")
    args = parser.parse_args()
    report = build_report(args.check_torch)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Python:", report["python"])
        print("Platform:", report["platform"])
        print("Executables:")
        for name, value in report["executables"].items():
            print(f"  - {name}: {value or '未找到'}")
        print("Packages:")
        for name, ok in report["packages_found"].items():
            print(f"  - {name}: {'OK' if ok else '未安装'}")
        if "torch" in report:
            print("Torch:", report["torch"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
