"""Packaged desktop entry point. Stdout is reserved for one readiness message."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import socket
import sys
import threading
from pathlib import Path


def configure_environment(data_root: Path) -> None:
    """Use application-owned paths, independent of checkout and working directory."""
    root = data_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        {
            "CARDLAB_ENV_FILE": str(root / "config.env"),
            "CARDLAB_RESOURCE_ROOT": str(Path(__file__).resolve().parent),
            "DATA_DIR": str(root),
            "SQLITE_PATH": str(root / "db" / "app.db"),
            "MODELS_DIR": str(root / "models"),
            "PUZZLE_DIR": str(root / "puzzles"),
            "VCR_DIR": str(root / "vcr"),
            "VCR_MODE": "off",
            "APP_DEBUG": "false",
            "MCP_HTTP_ENABLED": "false",
            "CORS_ORIGINS": "[]",
        }
    )


async def serve(data_root: Path, frontend: Path) -> None:
    configure_environment(data_root)
    # Configure environment before importing Settings and shared dependencies.
    import uvicorn

    from app.desktop_host import DesktopSession, attach_frontend
    from app.main import app

    attach_frontend(app, frontend)
    ticket = secrets.token_urlsafe(32)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
        session = DesktopSession(app, origin, ticket)
        server = uvicorn.Server(
            uvicorn.Config(
                session, access_log=False, log_level="warning", timeout_graceful_shutdown=5
            )
        )

        def parent_watch() -> None:
            # The parent holds stdin open. Closing it requests graceful shutdown.
            while sys.stdin.buffer.read(1):
                pass
            server.should_exit = True

        threading.Thread(target=parent_watch, daemon=True).start()
        task = asyncio.create_task(server.serve(sockets=[listener]))
        while not server.started and not task.done():
            await asyncio.sleep(0.05)
        if server.started:
            protocol_out.write(json.dumps({"url": f"{origin}/desktop-session/{ticket}"}) + "\n")
            protocol_out.flush()
        await task


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    protocol_out = sys.stdout
    sys.stdout = sys.stderr
    # PyInstaller preserves __file__ relative to its bundled resource directory.
    frontend_root = Path(__file__).resolve().parent / "frontend"
    asyncio.run(serve(args.data_root, frontend_root))
