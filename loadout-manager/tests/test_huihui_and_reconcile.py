"""inference-huihui-4gpu loadout, and adopting a stack that is already running.

Ported from the 2026-11-24 changes staged on Adapress (/home/claude/vllm-tune):
the huihui services exist in compose.inference.yml behind profile "huihui", and
loadout-manager must be able to select them. reconcile_state() keeps the
dashboard truthful when loadout-manager restarts while vLLM keeps running,
which is exactly what a redeploy of loadout-manager does.
"""
import subprocess

HUIHUI = "inference-huihui-4gpu"


def test_huihui_profile_starts_both_finetunes_and_embeddings(lm):
    r = lm.activate(HUIHUI)
    assert r.status_code == 200, r.text
    (up,) = lm.docker.starts
    assert up.compose_files == ["compose.inference.yml"]
    assert up.cmd[-3:] == ["vllm-huihui", "vllm-huihui-coder", "vllm-embed"]
    # The two finetunes sit behind compose profile "huihui". Naming them on
    # the `up` command line activates them (checked on Adapress's Compose
    # v5.2.0 with --dry-run), the same way vllm-pair-a/b are started.
    assert lm.state["active_profile"] == HUIHUI


def test_huihui_profile_is_mutually_exclusive_with_every_gpu_profile(lm):
    profs = lm.profiles
    for name, p in profs.items():
        if name in ("idle", HUIHUI):
            continue
        assert HUIHUI in p["incompatible_with"], name
        assert name in profs[HUIHUI]["incompatible_with"], name
    assert HUIHUI not in profs[HUIHUI]["incompatible_with"]
    assert profs["idle"].get("incompatible_with") in (None, [])


def test_huihui_services_are_known_to_the_service_maps(lm):
    import config
    for svc, gpus in (("vllm-huihui", [0, 3]), ("vllm-huihui-coder", [1, 2])):
        assert config.SERVICE_PROFILES[svc] == "huihui"
        assert config.GPU_ASSIGNMENT[svc] == gpus
        assert config.VLLM_URLS[svc] == f"http://{svc}:8000"
        assert "localhost" not in config.VLLM_URLS[svc]


def _ps(lm, names, rc=0):
    def rule(c):
        if c.cmd[:2] == ["docker", "ps"]:
            return subprocess.CompletedProcess(c.cmd, rc, "\n".join(names) + "\n", "")
    lm.docker.rules.append(rule)


def test_reconcile_adopts_running_default_stack(lm):
    _ps(lm, ["vllm-4gpu", "vllm-embed", "open-webui", "loadout-manager"])
    lm.main.reconcile_state()
    assert lm.state["active_profile"] == "inference-4gpu"
    assert lm.state["running_services"] == ["vllm-4gpu", "vllm-embed"]


def test_reconcile_adopts_huihui_stack(lm):
    _ps(lm, ["vllm-huihui", "vllm-huihui-coder", "vllm-embed"])
    lm.main.reconcile_state()
    assert lm.state["active_profile"] == HUIHUI


def test_reconcile_only_reads_docker(lm):
    """Restarting loadout-manager must never start or stop containers."""
    _ps(lm, ["vllm-4gpu", "vllm-embed"])
    lm.main.reconcile_state()
    assert lm.docker.starts == [] and lm.docker.downs == [] and lm.docker.pulls == []


def test_reconcile_leaves_partial_or_unknown_sets_alone(lm):
    _ps(lm, ["vllm-huihui", "open-webui"])
    lm.main.reconcile_state()
    assert lm.state["active_profile"] is None


def test_reconcile_ignores_a_failing_docker_ps(lm):
    _ps(lm, [], rc=1)
    lm.main.reconcile_state()
    assert lm.state["active_profile"] is None


def test_reconcile_never_overrides_a_recorded_profile(lm):
    lm.make_active("inference-pair-a")
    _ps(lm, ["vllm-4gpu", "vllm-embed"])
    lm.main.reconcile_state()
    assert lm.state["active_profile"] == "inference-pair-a"
