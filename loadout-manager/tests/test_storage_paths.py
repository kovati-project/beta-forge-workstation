"""
/api/storage/{list,preview,file} and /storage/detail?type=filesystem must stay
inside DATA_DIR.

``DATA_DIR / path`` is not a confinement: an absolute ``path`` replaces the
base (``/compose/.env`` returned every secret in docker/.env) and ``..`` climbs
out of it (``DELETE`` ran rmtree on whatever it pointed at).
"""

import os

import pytest


@pytest.fixture
def data(api, monkeypatch, tmp_path):
    from api import storage

    root = tmp_path / "srv-data"
    (root / "datasets" / "text").mkdir(parents=True)
    (root / "datasets" / "text" / "a.jsonl").write_text('{"x": 1}\n{"x": 2}\n')
    (root / "models" / "vllm").mkdir(parents=True)
    (tmp_path / "outside.env").write_text("SECRET=hunter2\n")
    monkeypatch.setattr(storage, "DATA_DIR", root)
    return root


def test_preview_inside_data_works(api, data):
    r = api.client.get("/api/storage/preview", params={"path": "datasets/text/a.jsonl", "n": 1})
    assert r.status_code == 200 and r.json()["lines"] == ['{"x": 1}']
    # absolute paths under DATA_DIR are what the UI sends
    r = api.client.get("/api/storage/preview", params={"path": str(data / "datasets/text/a.jsonl")})
    assert r.status_code == 200


@pytest.mark.parametrize("path", ["/compose/.env", "../outside.env", "datasets/../../outside.env"])
def test_preview_outside_data_is_refused(api, data, path):
    if path.startswith("/compose"):
        path = str(data.parent / "outside.env")       # an absolute path outside DATA_DIR
    r = api.client.get("/api/storage/preview", params={"path": path})
    assert r.status_code == 400
    assert "hunter2" not in r.text


def test_preview_through_a_symlink_out_of_data_is_refused(api, data):
    os.symlink(data.parent / "outside.env", data / "datasets" / "link.env")
    r = api.client.get("/api/storage/preview", params={"path": "datasets/link.env"})
    assert r.status_code == 400 and "hunter2" not in r.text


def test_list_outside_data_is_refused(api, data):
    assert api.client.get("/api/storage/list", params={"path": ".."}).status_code == 400
    assert api.client.get("/api/storage/list", params={"path": "datasets"}).status_code == 200


def test_missing_file_is_404_not_500(api, data):
    assert api.client.get("/api/storage/preview", params={"path": "nope.txt"}).status_code == 404


def test_delete_outside_data_is_refused(api, data):
    victim = data.parent / "outside.env"
    r = api.client.delete("/api/storage/file", params={"path": str(victim)})
    assert r.status_code == 400 and victim.exists()


def test_delete_refuses_top_level_data_dirs(api, data):
    r = api.client.delete("/api/storage/file", params={"path": "models"})
    assert r.status_code == 400 and (data / "models" / "vllm").is_dir()
    r = api.client.delete("/api/storage/file", params={"path": ""})
    assert r.status_code == 400


def test_delete_symlink_removes_link_not_target(api, data):
    os.symlink(data / "datasets" / "text", data / "models" / "vllm" / "current")
    r = api.client.delete("/api/storage/file", params={"path": "models/vllm/current"})
    assert r.status_code == 200
    assert not (data / "models" / "vllm" / "current").is_symlink()
    assert (data / "datasets" / "text" / "a.jsonl").exists()


def test_delete_inside_data_works(api, data):
    r = api.client.delete("/api/storage/file", params={"path": "datasets/text/a.jsonl"})
    assert r.status_code == 200 and not (data / "datasets/text/a.jsonl").exists()


def test_filesystem_detail_outside_data_is_refused(api, data):
    r = api.client.get("/api/storage/detail", params={"type": "filesystem", "name": "../"})
    assert r.status_code == 400
