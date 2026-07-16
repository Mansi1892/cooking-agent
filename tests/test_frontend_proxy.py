from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

import api as api_module


def test_root_path_is_proxied_to_frontend(monkeypatch):
    def fake_proxy(request, path):
        return PlainTextResponse("frontend-rendered")

    monkeypatch.setattr(api_module, "proxy_frontend_request", fake_proxy)

    client = TestClient(api_module.app)
    response = client.get("/")

    assert response.status_code == 200
    assert response.text == "frontend-rendered"


def test_api_health_alias_is_available():
    client = TestClient(api_module.app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
