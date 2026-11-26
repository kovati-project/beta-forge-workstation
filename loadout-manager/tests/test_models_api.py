"""
/api/models/* — Hugging Face search, discovery of models already on disk, and
registering one into the vLLM model directory.

The Hub is never contacted: httpx.AsyncClient is swapped for one on a
MockTransport. Filesystem roots are tmp_path. What this can NOT prove: the live
Hub's response shape (checked against https://huggingface.co/api/models by hand),
or that the vLLM containers resolve a registered symlink (needs the compose
mounts on a real host).
"""

import os
from pathlib import Path

import httpx
import pytest

HF_SAMPLE = [
    {"id": "Qwen/Qwen2.5-7B-Instruct", "modelId": "Qwen/Qwen2.5-7B-Instruct",
     "downloads": 900, "likes": 50, "pipeline_tag": "text-generation",
     "tags": ["transformers", "safetensors"], "lastModified": "2025-01-01T00:00:00.000Z",
     "gated": False, "private": False},
    {"id": "bartowski/Qwen2.5-7B-Instruct-GGUF", "downloads": 300, "likes": 9,
     "pipeline_tag": "text-generation", "tags": ["gguf"], "gated": "manual"},
    {"downloads": 1},  # no id: dropped
]


@pytest.fixture
def models_api(api, monkeypatch, tmp_path):
    from api import models
    root = tmp_path / "data"
    monkeypatch.setattr(models, "MODELS_ROOT", root / "models")
    monkeypatch.setattr(models, "CHECKPOINTS_ROOT", root / "checkpoints")
    monkeypatch.setattr(models, "VLLM_MODEL_DIR", root / "models" / "vllm")
    monkeypatch.setattr(models, "ENV_FILE", api.env_file)
    for k in ("HF_TOKEN", "HUGGINGFACE_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    api.models = models
    api.root = root
    return api


@pytest.fixture
def hub(models_api, monkeypatch):
    """Route the endpoint's outbound httpx calls to a handler the test sets."""
    seen = []
    state = {"handler": lambda req: httpx.Response(200, json=HF_SAMPLE)}

    def handler(request):
        seen.append(request)
        return state["handler"](request)

    real = httpx.AsyncClient
    monkeypatch.setattr(models_api.models.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return state, seen


# ── HF search ────────────────────────────────────────────────────────────────

def test_search_proxies_the_hub_and_trims_results(models_api, hub):
    _, seen = hub
    r = models_api.client.get("/api/models/hf/search",
                              params={"q": "qwen", "task": "text-generation", "limit": 5})
    assert r.status_code == 200, r.text
    body = r.json()

    req = seen[0]
    assert req.url.host == "huggingface.co" and req.url.path == "/api/models"
    assert req.url.params["search"] == "qwen"
    assert req.url.params["filter"] == "text-generation"
    assert req.url.params["sort"] == "downloads"
    assert req.url.params["limit"] == "5"
    assert "authorization" not in req.headers

    assert body["count"] == 2
    first, gguf = body["results"]
    assert first["id"] == first["repo_id"] == "Qwen/Qwen2.5-7B-Instruct"
    assert set(first) >= {"id", "downloads", "likes", "pipeline_tag", "tags",
                          "lastModified", "gated"}
    assert first["gated"] is False and first["gguf"] is False
    assert first["suggested_name"] == "qwen2.5-7b-instruct"
    assert gguf["gated"] is True and gguf["gguf"] is True
    assert "private" not in first


def test_search_limit_is_clamped(models_api, hub):
    _, seen = hub
    models_api.client.get("/api/models/hf/search", params={"q": "x", "limit": 500})
    assert seen[0].url.params["limit"] == "50"


def test_search_by_task_alone(models_api, hub):
    _, seen = hub
    r = models_api.client.get("/api/models/hf/search",
                              params={"task": "automatic-speech-recognition"})
    assert r.status_code == 200
    assert "search" not in seen[0].url.params


def test_search_needs_query_or_task(models_api, hub):
    r = models_api.client.get("/api/models/hf/search", params={"q": "  "})
    assert r.status_code == 400


def test_search_sends_token_from_env_file(models_api, hub):
    _, seen = hub
    models_api.env_file.write_text("HUGGINGFACE_TOKEN=hf_fromdotenv\n")
    models_api.client.get("/api/models/hf/search", params={"q": "llama"})
    assert seen[0].headers["authorization"] == "Bearer hf_fromdotenv"


def test_search_env_var_token_wins(models_api, hub, monkeypatch):
    _, seen = hub
    models_api.env_file.write_text("HUGGINGFACE_TOKEN=hf_fromdotenv\n")
    monkeypatch.setenv("HF_TOKEN", "hf_fromenv")
    models_api.client.get("/api/models/hf/search", params={"q": "llama"})
    assert seen[0].headers["authorization"] == "Bearer hf_fromenv"


def test_search_network_error_is_502(models_api, hub):
    state, _ = hub

    def boom(request):
        raise httpx.ConnectError("no route to host", request=request)
    state["handler"] = boom
    r = models_api.client.get("/api/models/hf/search", params={"q": "qwen"})
    assert r.status_code == 502
    assert "unreachable" in r.json()["detail"]


def test_search_upstream_error_is_502(models_api, hub):
    state, _ = hub
    state["handler"] = lambda req: httpx.Response(500, text="oops")
    r = models_api.client.get("/api/models/hf/search", params={"q": "qwen"})
    assert r.status_code == 502
    assert "HTTP 500" in r.json()["detail"]


def test_search_timeout_is_504(models_api, hub):
    state, _ = hub

    def slow(request):
        raise httpx.ReadTimeout("slow", request=request)
    state["handler"] = slow
    r = models_api.client.get("/api/models/hf/search", params={"q": "qwen"})
    assert r.status_code == 504


# ── local discovery ──────────────────────────────────────────────────────────

def _touch(path: Path, size: int = 10):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def _layout(root: Path):
    m, c = root / "models", root / "checkpoints"
    _touch(m / "custom" / "my-llm" / "config.json")
    _touch(m / "custom" / "my-llm" / "model.safetensors", 1000)
    _touch(m / "gguf" / "tiny" / "tiny-q4.gguf")
    _touch(m / "comfyui" / "checkpoints" / "sdxl.safetensors")
    _touch(m / "whisper" / "README.md")                      # not a model
    _touch(m / "vllm" / "qwen" / "config.json")              # listed by /vllm/local
    _touch(m / "hf-cache" / "hub" / "x" / "config.json")     # cache: skipped
    _touch(c / "axolotl" / "run1" / "adapter_config.json")
    _touch(c / "axolotl" / "run1" / "checkpoint-500" / "adapter_config.json")
    _touch(c / "unsloth" / "merged" / "config.json")


def test_local_discovery(models_api):
    _layout(models_api.root)
    r = models_api.client.get("/api/models/local")
    assert r.status_code == 200
    by_name = {m["name"]: m for m in r.json()["models"]}

    assert set(by_name) == {"custom-my-llm", "gguf-tiny", "comfyui-checkpoints",
                            "axolotl-run1", "unsloth-merged"}
    assert by_name["custom-my-llm"]["format"] == "hf"
    assert by_name["custom-my-llm"]["registerable"] is True
    assert by_name["gguf-tiny"]["format"] == "gguf"
    assert by_name["comfyui-checkpoints"]["format"] == "safetensors"
    assert by_name["axolotl-run1"]["format"] == "adapter"
    assert by_name["axolotl-run1"]["registerable"] is False
    assert by_name["unsloth-merged"]["root"] == str(models_api.root / "checkpoints")
    assert by_name["unsloth-merged"]["registered_as"] is None


def test_local_discovery_with_missing_roots(models_api):
    r = models_api.client.get("/api/models/local")
    assert r.status_code == 200 and r.json()["models"] == []


def test_rescan_sees_models_added_out_of_band(models_api):
    assert models_api.client.get("/api/models/local").json()["models"] == []
    _touch(models_api.root / "checkpoints" / "manual" / "config.json")
    names = [m["name"] for m in models_api.client.get("/api/models/local").json()["models"]]
    assert names == ["manual"]


# ── register ─────────────────────────────────────────────────────────────────

def _can_symlink(tmp_path):
    try:
        (tmp_path / "_probe").symlink_to(tmp_path, target_is_directory=True)
        return True
    except OSError:
        return False


@pytest.fixture
def symlinks(tmp_path):
    if not _can_symlink(tmp_path):
        pytest.skip("this OS/user cannot create symlinks")


def test_register_links_checkpoint_into_vllm_dir(models_api, symlinks):
    _layout(models_api.root)
    src = models_api.root / "checkpoints" / "unsloth" / "merged"
    r = models_api.client.post("/api/models/local/register",
                               json={"path": str(src), "name": "my-finetune"})
    assert r.status_code == 200, r.text

    link = models_api.models.VLLM_MODEL_DIR / "my-finetune"
    assert link.is_symlink() and Path(os.readlink(link)).is_absolute()
    assert link.resolve() == src.resolve()

    vllm = models_api.client.get("/api/models/vllm/local").json()
    entry = {m["name"]: m for m in vllm["models"]}["my-finetune"]
    assert entry["registered_from"] == str(src.resolve())

    local = {m["name"]: m for m in models_api.client.get("/api/models/local").json()["models"]}
    assert local["unsloth-merged"]["registered_as"] == "my-finetune"

    r = models_api.client.post("/api/models/vllm/activate",
                               json={"slot": "pair-a", "model": "my-finetune"})
    assert r.status_code == 200, r.text
    assert (models_api.models.VLLM_MODEL_DIR / "current").resolve() == src.resolve()


@pytest.mark.parametrize("rel,name,code", [
    ("checkpoints/axolotl/run1", "x", 400),     # adapter, not HF format
    ("models/whisper", "x", 400),               # not a model
    ("models/vllm/qwen", "x", 400),             # already in the vLLM dir
    ("checkpoints/nope", "x", 404),
    ("checkpoints/unsloth/merged", "../evil", 400),
    ("checkpoints/unsloth/merged", "current", 400),  # a slot link name
    ("checkpoints/unsloth/merged", "qwen", 409),     # taken
])
def test_register_rejects(models_api, rel, name, code):
    _layout(models_api.root)
    r = models_api.client.post("/api/models/local/register",
                               json={"path": str(models_api.root / rel), "name": name})
    assert r.status_code == code, r.text


def test_register_rejects_paths_outside_the_roots(models_api, tmp_path):
    _layout(models_api.root)
    outside = tmp_path / "elsewhere"
    _touch(outside / "config.json")
    r = models_api.client.post("/api/models/local/register",
                               json={"path": str(outside), "name": "x"})
    assert r.status_code == 400
