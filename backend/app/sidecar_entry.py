"""Sidecar entry: uvicorn server with --port argv from the Tauri shell.

This module exists because PyInstaller needs a concrete __main__ that
imports the FastAPI app; it parses `--port` (and optionally --host) from
its own argv rather than relying on environment variables, matching what
the Rust shell passes.
"""

import argparse

import uvicorn

from app.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="ChronoLens backend sidecar")
    parser.add_argument("--port", type=int, default=8756)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    # Access logs make request tracing possible when the GUI reports a
    # failure: the Rust shell pipes sidecar stdout/stderr to the system
    # console, so `log stream` shows every hit the backend receives.
    parser.add_argument(
        "--access-log",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Log every request (disable with --no-access-log).",
    )
    args = parser.parse_args()
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        access_log=args.access_log,
    )


if __name__ == "__main__":
    main()
