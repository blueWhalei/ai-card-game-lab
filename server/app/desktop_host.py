"""Desktop transport boundary around the shared research application."""

from __future__ import annotations

import secrets
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from typing import Any

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send


class FrontendFiles(StaticFiles):
    """Serve built assets and Vue history routes without masking missing APIs."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            route = path.replace("\\", "/").lstrip("/")
            if exc.status_code != 404 or route.split("/", 1)[0] in {"api", "assets", "mcp"}:
                raise
            if Path(path).suffix or scope["method"] not in {"GET", "HEAD"}:
                raise
            return await super().get_response("index.html", scope)


class DesktopSession:
    """One-use launch ticket, process-local cookie and same-origin HTTP/WS access.

    This wrapper has no native commands or research endpoints. Launch tickets
    are sent only over the parent's private stdout pipe; access logging is off.
    """

    def __init__(self, app: ASGIApp, origin: str, ticket: str) -> None:
        self.app = app
        self.origin = origin
        self.authority = origin.removeprefix("http://")
        self.ticket: str | None = ticket
        self.cookie = secrets.token_urlsafe(32)
        # Cookies are not port-scoped: use a distinct name for every process.
        self.cookie_name = "cardlab_" + secrets.token_hex(12)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        authority_ok = headers.get("host") == self.authority
        origin_ok = origin is None or origin == self.origin
        if scope["type"] == "websocket":
            origin_ok = origin == self.origin
        if not authority_ok or not origin_ok:
            await self._deny(scope, receive, send)
            return

        if scope["type"] == "http" and scope["path"].startswith("/desktop-session/"):
            supplied = scope["path"].removeprefix("/desktop-session/")
            if (
                scope["method"] == "GET"
                and self.ticket
                and secrets.compare_digest(supplied, self.ticket)
            ):
                self.ticket = None
                response = RedirectResponse("/", status_code=303)
                response.set_cookie(self.cookie_name, self.cookie, httponly=True, samesite="strict")
                response.headers["Cache-Control"] = "no-store"
                response.headers["Referrer-Policy"] = "no-referrer"
                await response(scope, receive, send)
                return
            await self._deny(scope, receive, send)
            return

        cookies = SimpleCookie()
        try:
            cookies.load(headers.get("cookie", ""))
        except CookieError:
            await self._deny(scope, receive, send)
            return
        value = cookies.get(self.cookie_name)
        if value is None or not secrets.compare_digest(value.value, self.cookie):
            await self._deny(scope, receive, send)
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _deny(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
        else:
            await JSONResponse({"message": "Desktop session required"}, status_code=403)(
                scope, receive, send
            )


def attach_frontend(app: Any, frontend: Path) -> None:
    """The desktop build must contain a complete, current frontend bundle."""
    if not (frontend / "index.html").is_file():
        raise RuntimeError("Desktop frontend bundle is missing")
    app.mount("/", FrontendFiles(directory=str(frontend), html=True), name="frontend")
