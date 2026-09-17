from fastapi.testclient import TestClient

from app.main import app, frontend_origins_from_env


def test_frontend_origins_default_to_local_development(monkeypatch) -> None:
    monkeypatch.delenv("FRONTEND_ORIGINS", raising=False)

    assert frontend_origins_from_env() == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_frontend_origins_are_trimmed_and_deduplicated(monkeypatch) -> None:
    monkeypatch.setenv(
        "FRONTEND_ORIGINS",
        " https://proofpick.example, http://localhost:3000,https://proofpick.example ",
    )

    assert frontend_origins_from_env() == [
        "https://proofpick.example",
        "http://localhost:3000",
    ]


def test_local_frontend_preflight_is_allowed() -> None:
    response = TestClient(app).options(
        "/api/analyses",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unlisted_frontend_origin_is_not_allowed() -> None:
    response = TestClient(app).options(
        "/api/analyses",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
