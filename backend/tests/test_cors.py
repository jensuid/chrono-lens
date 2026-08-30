"""Regression tests for the CORS posture of the analysis service.

The packaged app's webview serves the frontend from the `tauri://localhost`
(origin `tauri://localhost` on macOS/WKWebView, `https://tauri.localhost` on
Windows/WebView2). If those origins are not allowed, every fetch from the
shipped app fails with WKWebView's generic "Load failed".
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


WEBVIEW_ORIGINS = [
    "tauri://localhost",
    "https://tauri.localhost",
    "http://tauri.localhost",
]

DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


@pytest.mark.parametrize("origin", WEBVIEW_ORIGINS)
def test_webview_origin_allowed_on_get(client: TestClient, origin: str) -> None:
    response = client.get("/api/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize("origin", WEBVIEW_ORIGINS)
def test_webview_origin_allowed_on_preflight(client: TestClient, origin: str) -> None:
    response = client.options(
        "/api/datasets",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize("origin", DEV_ORIGINS)
def test_dev_origin_still_allowed(client: TestClient, origin: str) -> None:
    response = client.get("/api/health", headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_unknown_origin_gets_no_allow_header(client: TestClient) -> None:
    # Requests still succeed (no credentials involved), but the browser
    # would block reading the response.
    response = client.get(
        "/api/health", headers={"Origin": "https://evil.example.com"}
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
