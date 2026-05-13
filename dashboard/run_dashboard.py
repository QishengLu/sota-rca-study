#!/usr/bin/env python
"""Entry script to run the RCABench Evaluation Dashboard.

This script starts both the FastAPI backend and the Vite frontend dev server.
In production mode, it serves the built frontend from the backend.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR / "backend"
FRONTEND_DIR = SCRIPT_DIR / "frontend"


def check_node_installed() -> bool:
    """Check if Node.js is installed."""
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_frontend_deps() -> bool:
    """Check if frontend dependencies are installed."""
    return (FRONTEND_DIR / "node_modules").exists()


def install_frontend_deps():
    """Install frontend dependencies."""
    print("Installing frontend dependencies...")
    subprocess.run(["npm", "install"], cwd=FRONTEND_DIR, check=True)


def build_frontend():
    """Build the frontend for production."""
    print("Building frontend...")
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True)


def run_dev_mode(backend_port: int, frontend_port: int):
    """Run in development mode with hot reload."""
    processes = []

    try:
        # Start backend
        print(f"Starting backend on port {backend_port}...")
        backend_env = os.environ.copy()
        backend_env["DASHBOARD_PORT"] = str(backend_port)

        backend_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--reload",
                "--host",
                "0.0.0.0",
                "--port",
                str(backend_port),
            ],
            cwd=BACKEND_DIR,
            env=backend_env,
        )
        processes.append(backend_proc)

        # Start frontend dev server
        print(f"Starting frontend dev server on port {frontend_port}...")
        frontend_env = os.environ.copy()
        frontend_env["VITE_API_URL"] = f"http://localhost:{backend_port}"

        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev", "--", "--host", "--port", str(frontend_port)],
            cwd=FRONTEND_DIR,
            env=frontend_env,
        )
        processes.append(frontend_proc)

        print(f"\n{'=' * 60}")
        print("Dashboard running in development mode")
        print(f"  Frontend: http://localhost:{frontend_port}")
        print(f"  Backend:  http://localhost:{backend_port}")
        print(f"  API Docs: http://localhost:{backend_port}/docs")
        print(f"{'=' * 60}\n")

        # Wait for processes
        while True:
            for proc in processes:
                if proc.poll() is not None:
                    print(f"Process exited with code {proc.returncode}")
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        for proc in processes:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def run_prod_mode(port: int):
    """Run in production mode serving built frontend from backend."""
    # Check if frontend is built
    dist_dir = FRONTEND_DIR / "dist"
    if not dist_dir.exists():
        print("Frontend not built. Building now...")
        build_frontend()

    print(f"Starting dashboard on port {port}...")
    backend_env = os.environ.copy()
    backend_env["DASHBOARD_PORT"] = str(port)

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
            ],
            cwd=BACKEND_DIR,
            env=backend_env,
        )
    except KeyboardInterrupt:
        print("\nShutting down...")


def main():
    parser = argparse.ArgumentParser(description="Run RCABench Evaluation Dashboard")
    parser.add_argument(
        "--mode",
        choices=["dev", "prod", "demo"],
        default="dev",
        help="Run mode: dev (hot reload), prod (optimized), or demo (uses demo_cache.json)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Backend port (default: 8000)",
    )
    parser.add_argument(
        "--frontend-port",
        type=int,
        default=5173,
        help="Frontend dev server port (default: 5173, dev mode only)",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build frontend before running (prod mode)",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install frontend dependencies",
    )

    args = parser.parse_args()

    # Check Node.js for frontend
    if args.mode == "dev" or args.build or args.install:
        if not check_node_installed():
            print("Error: Node.js is required for frontend development.")
            print("Please install Node.js from https://nodejs.org/")
            sys.exit(1)

    # Install dependencies if requested or needed
    if args.install or (args.mode == "dev" and not check_frontend_deps()):
        install_frontend_deps()

    # Build if requested
    if args.build:
        if not check_frontend_deps():
            install_frontend_deps()
        build_frontend()

    # Set demo cache if demo mode
    if args.mode == "demo":
        demo_cache = str(SCRIPT_DIR / "demo_cache.json")
        os.environ["ANALYSIS_CACHE_FILE"] = demo_cache
        print(f"Demo mode: using {demo_cache}")
        args.mode = "prod"  # demo uses prod serving

    # Run
    if args.mode == "dev":
        if not check_frontend_deps():
            install_frontend_deps()
        run_dev_mode(args.port, args.frontend_port)
    else:
        run_prod_mode(args.port)


if __name__ == "__main__":
    main()
