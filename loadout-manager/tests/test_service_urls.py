"""
Service URLs used by loadout-manager from inside its container.

Inside the container "localhost" is the container itself, so every backend it
calls (Qdrant, Langfuse, Prometheus, MinIO, Postgres) must be addressed by
container name on the shared ai-workstation network. Found live on 2026-11-14:
GET /api/vectors/collections and /api/traces both failed with "All connection
attempts failed" while Qdrant answered on the Docker network.

Not proven here: that the containers share a network on the host (compose).
"""

import httpx
import pytest


def _no_localhost(value: str) -> bool:
    return "localhost" not in value and "127.0.0.1" not in value


def test_service_url_defaults_do_not_point_at_the_container_itself(lm, monkeypatch):
    import config
    for name in ("PROMETHEUS_URL", "LANGFUSE_URL", "MINIO_ENDPOINT",
                 "QDRANT_URL", "POSTGRES_HOST", "AUTHENTIK_URL",
                 "VLLM_PAIR_A_URL", "VLLM_PAIR_B_URL", "VLLM_4GPU_URL",
                 "VLLM_EMBED_URL"):
        monkeypatch.delenv(name, raising=False)
        assert _no_localhost(getattr(config, name)), f"{name}={getattr(config, name)}"


def test_api_modules_use_the_shared_service_urls(lm):
    import config
    from api import auth, metrics, models, storage, traces, vectors
    assert vectors.QDRANT_URL == storage.QDRANT_URL == config.QDRANT_URL
    assert traces.LANGFUSE_URL == config.LANGFUSE_URL
    assert metrics.PROMETHEUS_URL == config.PROMETHEUS_URL
    assert auth.AUTHENTIK_URL == config.AUTHENTIK_URL
    assert models.VLLM_URLS == config.VLLM_URLS
    assert all(_no_localhost(u) for u in models.VLLM_URLS.values())


def _config_urls(env: dict) -> dict:
    """Import config.py fresh in a child process, so reloads cannot leak into other tests."""
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path
    lm_dir = Path(__file__).resolve().parents[1]
    clean = {k: v for k, v in os.environ.items() if not k.startswith("VLLM_")}
    clean.update(env)
    out = subprocess.run(
        [sys.executable, "-c",
         "import json, sys; sys.path.insert(0, sys.argv[1]); import config; "
         "print(json.dumps(config.VLLM_URLS))", str(lm_dir)],
        env=clean, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_vllm_urls_use_container_names_and_internal_port():
    """Containers all listen on 8000 inside ai-workstation; 8001-8003 are host ports."""
    assert _config_urls({}) == {
        "vllm-pair-a": "http://vllm-pair-a:8000",
        "vllm-pair-b": "http://vllm-pair-b:8000",
        "vllm-4gpu": "http://vllm-4gpu:8000",
        "vllm-embed": "http://vllm-embed:8000",
    }


def test_vllm_urls_can_be_overridden_from_the_environment():
    urls = _config_urls({"VLLM_4GPU_URL": "http://elsewhere:9"})
    assert urls["vllm-4gpu"] == "http://elsewhere:9"
    assert urls["vllm-pair-a"] == "http://vllm-pair-a:8000"


def _mock_client(monkeypatch, module, handler):
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", factory)


def test_vector_collections_are_fetched_from_qdrant(lm, monkeypatch):
    from api import vectors
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json={"result": {"collections": [{"name": "docs"}]},
                                         "status": "ok"})

    _mock_client(monkeypatch, vectors, handler)
    resp = lm.client.get("/api/vectors/collections")
    assert resp.status_code == 200, resp.text
    assert resp.json()["result"]["collections"] == [{"name": "docs"}]
    assert seen == [f"{vectors.QDRANT_URL}/collections"]


def test_vector_collections_report_qdrant_errors(lm, monkeypatch):
    from api import vectors
    _mock_client(monkeypatch, vectors, lambda request: httpx.Response(500, text="boom"))
    resp = lm.client.get("/api/vectors/collections")
    assert resp.status_code == 503
    assert "Qdrant unavailable" in resp.json()["detail"]


def test_credentials_come_from_docker_env_when_not_in_environment(lm, monkeypatch, tmp_path):
    from api import storage
    env_file = tmp_path / ".env"
    env_file.write_text("MINIO_ROOT_PASSWORD=from-dotenv\n")
    monkeypatch.setenv("ENV_FILE", str(env_file))
    monkeypatch.delenv("MINIO_SECRET_KEY", raising=False)
    assert storage._credential("MINIO_SECRET_KEY", "MINIO_ROOT_PASSWORD") == "from-dotenv"

    monkeypatch.setenv("MINIO_SECRET_KEY", "explicit")
    assert storage._credential("MINIO_SECRET_KEY", "MINIO_ROOT_PASSWORD") == "explicit"


@pytest.mark.parametrize("missing", ["no-file", "no-key"])
def test_credentials_fall_back_to_default(lm, monkeypatch, tmp_path, missing):
    from api import storage
    env_file = tmp_path / ".env"
    if missing == "no-key":
        env_file.write_text("OTHER=1\n")
    monkeypatch.setenv("ENV_FILE", str(env_file))
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    assert storage._credential("POSTGRES_PASSWORD", "POSTGRES_ADMIN_PASSWORD", "dflt") == "dflt"
