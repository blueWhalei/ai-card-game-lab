"""The packaged app uses the same routes behind a local session boundary."""

from pathlib import Path

import pytest
from fastapi import FastAPI, WebSocket
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.desktop_host import DesktopSession, attach_frontend


def client_for(tmp_path: Path) -> TestClient:
    (tmp_path / "index.html").write_text("<main>CardLab</main>", encoding="utf-8")
    app = FastAPI()

    @app.get("/api/example")
    async def example() -> dict[str, bool]:
        return {"ok": True}

    @app.websocket("/api/socket")
    async def socket(ws: WebSocket) -> None:
        await ws.accept()
        await ws.send_text("ready")
        await ws.close()

    attach_frontend(app, tmp_path)
    return TestClient(
        DesktopSession(app, "http://127.0.0.1:12345", "launch-ticket"),
        base_url="http://127.0.0.1:12345",
    )


def test_session_and_history_routes(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        assert client.get("/api/example").status_code == 403
        assert client.get("/desktop-session/wrong").status_code == 403
        response = client.get("/desktop-session/launch-ticket", follow_redirects=False)
        assert response.status_code == 303
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/desktop-session/launch-ticket").status_code == 403
        assert client.get("/api/example").json() == {"ok": True}
        assert "CardLab" in client.get("/experiments/example").text
        assert client.get("/api/missing").status_code == 404
        assert client.get("/assets/missing.js").status_code == 404
        assert (
            client.get("/api/example", headers={"Origin": "https://untrusted.example"}).status_code
            == 403
        )
        assert client.get("/api/example", headers={"Host": "localhost:12345"}).status_code == 403


def test_websocket_requires_cookie_and_exact_origin(tmp_path: Path) -> None:
    with client_for(tmp_path) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "ws://127.0.0.1:12345/api/socket", headers={"Origin": "http://127.0.0.1:12345"}
            ):
                pass
        client.get("/desktop-session/launch-ticket")
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "ws://127.0.0.1:12345/api/socket", headers={"Origin": "https://untrusted.example"}
            ):
                pass
        with client.websocket_connect(
            "ws://127.0.0.1:12345/api/socket", headers={"Origin": "http://127.0.0.1:12345"}
        ) as ws:
            assert ws.receive_text() == "ready"


def test_missing_bundle_fails_explicitly(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="bundle is missing"):
        attach_frontend(FastAPI(), tmp_path)


def test_packaged_rules_use_explicit_resource_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.ai.prompt import _load_rules

    (tmp_path / "rules.md").write_text("Packaged rules", encoding="utf-8")
    monkeypatch.setenv("CARDLAB_RESOURCE_ROOT", str(tmp_path))
    assert _load_rules("rules.md") == "Packaged rules"
