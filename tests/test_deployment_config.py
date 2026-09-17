import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_railway_config_uses_injected_port_and_health_check() -> None:
    config = json.loads((ROOT / "backend" / "railway.json").read_text())

    assert config["build"]["builder"] == "RAILPACK"
    assert config["deploy"]["startCommand"] == (
        "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    )
    assert config["deploy"]["healthcheckPath"] == "/health"
