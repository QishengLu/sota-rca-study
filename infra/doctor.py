#!/usr/bin/env python
"""sota-rca-study environment doctor — checks all prerequisites.

Usage:
    uv run python infra/doctor.py
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}✓{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"{RED}✗{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}!{RESET} {msg}")


def header(msg: str) -> None:
    print(f"\n{CYAN}==> {msg}{RESET}")


def check_command(name: str, *, required: bool = True, version_flag: str = "--version") -> bool:
    path = shutil.which(name)
    if not path:
        (fail if required else warn)(f"{name} not in PATH")
        return False
    try:
        out = subprocess.run(
            [name, version_flag], capture_output=True, text=True, timeout=5, check=False
        ).stdout.strip().splitlines()[0] or "(no version info)"
    except Exception as e:
        warn(f"{name} found at {path} but version check failed: {e}")
        return True
    ok(f"{name}: {out}")
    return True


def check_python() -> bool:
    v = sys.version_info
    if v.major == 3 and v.minor >= 12:
        ok(f"python: {v.major}.{v.minor}.{v.micro}")
        return True
    fail(f"python: {v.major}.{v.minor}.{v.micro} (need ≥ 3.12)")
    return False


def check_postgres() -> bool:
    import socket

    port = int(os.environ.get("POSTGRES_PORT", "5433"))
    try:
        with socket.create_connection(("localhost", port), timeout=2):
            ok(f"PostgreSQL reachable at localhost:{port}")
            return True
    except OSError:
        warn(f"PostgreSQL NOT reachable at localhost:{port} (run docker compose up -d)")
        return False


def check_env_keys() -> int:
    """Returns count of provider API keys present."""
    keys = [
        "SHUBIAOBIAO_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "DASHSCOPE_API_KEY",
        "ZHIPU_API_KEY",
        "MOONSHOT_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
    ]
    present = [k for k in keys if os.environ.get(k)]
    if present:
        ok(f"API keys set: {', '.join(present)}")
    else:
        warn("No provider API keys set in env. Edit .env and source it.")
    return len(present)


def check_repo_structure() -> bool:
    repo = Path(__file__).resolve().parent.parent
    required = [
        "pyproject.toml",
        "sdk/sota_rca",
        "frameworks",
        "configs/matrix",
        "configs/models",
        "scripts",
        "dashboard/backend",
        "infra",
        ".env.example",
    ]
    missing = [p for p in required if not (repo / p).exists()]
    if missing:
        fail(f"Missing repo paths: {missing}")
        return False
    ok("Repo structure OK")
    return True


def check_dataset() -> bool:
    cache = Path.home() / ".cache" / "sota-rca" / "ops-lite"
    if cache.exists() and any(cache.iterdir()):
        ok(f"ops-lite dataset found at {cache}")
        return True
    warn(f"ops-lite dataset NOT found at {cache}. Run: uv run sota-rca data download")
    return False


def main() -> int:
    print(f"{CYAN}sota-rca-study Environment Doctor{RESET}")
    print(f"  OS: {platform.system()} {platform.machine()}")
    print(f"  Python: {sys.executable}")

    header("Core tools")
    issues = 0
    issues += 0 if check_python() else 1
    issues += 0 if check_command("uv", required=True) else 1
    issues += 0 if check_command("git", required=True) else 1
    issues += 0 if check_command("docker", required=True) else 1
    check_command("node", required=False, version_flag="--version")
    check_command("npm", required=False, version_flag="--version")
    check_command("claude", required=False, version_flag="--version")  # Claude Code CLI

    header("Runtime services")
    check_postgres()

    header("Environment / Secrets")
    n_keys = check_env_keys()
    if n_keys == 0:
        issues += 1

    header("Repository")
    issues += 0 if check_repo_structure() else 1
    check_dataset()

    header("Summary")
    if issues == 0:
        ok("All critical checks passed.")
        return 0
    fail(f"{issues} critical issue(s) need attention.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
