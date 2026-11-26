"""
How a switch invokes docker compose.

- Files come from api.secrets.COMPOSE_DIR (/compose in the container), not
  Path(__file__).parent.parent / "docker", which is /docker in the container.
- Teardown includes services behind compose profiles (--profile '*') and
  orphans, or vllm-pair-b, vllm-4gpu, axolotl, unsloth and invokeai survive it.
- A profile spanning two compose files is started one file at a time, so each
  container lands in the project that teardown later stops.
- Images are pulled before teardown, so the old profile keeps serving while
  they download and `up` does not time out on a pull.
"""

from pathlib import Path

import pytest


def _f_args(call):
    return [call.cmd[i + 1] for i, a in enumerate(call.cmd) if a == "-f"]


def test_compose_files_come_from_compose_dir(lm):
    from api import secrets as secrets_api
    lm.make_active("inference-pair-b")
    assert lm.activate("training-unsloth").status_code == 200
    for c in lm.docker.calls:
        for f in _f_args(c):
            assert Path(f).parent == secrets_api.COMPOSE_DIR, c
        assert "--env-file" in c.cmd, c


def test_teardown_includes_profiled_services_and_orphans(lm):
    lm.make_active("inference-4gpu")
    assert lm.client.post("/stop").status_code == 200
    assert len(lm.docker.downs) == 3
    for c in lm.docker.downs:
        i = c.cmd.index("--profile")
        assert c.cmd[i + 1] == "*"
        assert "--remove-orphans" in c.cmd


def test_multi_file_profile_starts_each_file_in_its_own_project(lm):
    lm.make_active("inference-pair-a")
    assert lm.activate("image-studio").status_code == 200, lm.state["last_error"]
    ups = lm.docker.starts
    assert [(c.compose_files, c.cmd[c.cmd.index("-d") + 1:]) for c in ups] == [
        (["compose.studio.yml"], ["comfyui", "rembg"]),
        (["compose.inference.yml"], ["vllm-pair-b"]),
    ]
    assert lm.state["running_services"] == lm.profiles["image-studio"]["services"]


def test_images_are_pulled_before_teardown(lm):
    lm.make_active("inference-pair-b")
    assert lm.activate("training-unsloth").status_code == 200
    (pull,) = lm.docker.pulls
    assert pull.compose_files == ["compose.training.yml"]
    assert pull.cmd[-1:] == ["unsloth"]
    assert all(pull.seq < d.seq for d in lm.docker.downs)


def test_failed_pull_does_not_block_the_switch(lm):
    lm.docker.fail("pull", rc=1, stderr="registry unreachable")
    lm.make_active("inference-pair-b")
    assert lm.activate("training-unsloth").status_code == 200
    assert lm.state["active_profile"] == "training-unsloth"
    assert lm.state["last_error"] is None


def test_second_file_failing_to_start_cleans_up(lm):
    def rule(c):
        if c.verb == "up" and c.compose_files == ["compose.inference.yml"]:
            import subprocess
            return subprocess.CompletedProcess(c.cmd, 1, "", "port already allocated")
    lm.docker.rules.append(rule)
    lm.make_active("inference-pair-a")
    lm.activate("image-studio")
    first_up = lm.docker.starts[0]
    assert [c for c in lm.docker.downs if c.seq > first_up.seq], "cleanup must run"
    assert lm.state["active_profile"] is None
    assert lm.state["last_error"]


def test_profile_naming_an_undefined_service_aborts_before_teardown(lm, monkeypatch):
    profiles = lm.main.load_profiles()
    profiles["training-unsloth"]["services"] = ["unsloth", "no-such-service"]
    monkeypatch.setattr(lm.main, "load_profiles", lambda: profiles)
    lm.make_active("inference-pair-b")
    lm.activate("training-unsloth")
    assert lm.docker.calls == []
    assert lm.state["active_profile"] == "inference-pair-b"
    assert lm.state["last_error"]
