"""
TASK-026 / issue #16 — training-vs-inference incompatibility gate.

Key question: is `incompatible_with` ENFORCED by the backend, or only exposed as
data in GET /loadouts (for the UI to grey cards out)? Answer from these tests:
it is only data. Every "must be refused" test below is xfail(strict=True) with
BUG-1; the data-quality tests carry BUG-2.

The VRAM gate is made irrelevant here (all GPUs fully free) so that any refusal
could only come from a compatibility check.
"""

import pytest


def is_4xx(resp):
    return 400 <= resp.status_code < 500


def incompatible_pairs(profiles, direction="target_lists_active"):
    """(active, target) pairs the data says must not be combined."""
    pairs = []
    for a, pa in profiles.items():
        for t, pt in profiles.items():
            if a == t:
                continue
            target_lists_active = a in pt.get("incompatible_with", [])
            active_lists_target = t in pa.get("incompatible_with", [])
            if direction == "target_lists_active" and target_lists_active:
                pairs.append((a, t))
            elif direction == "either" and (target_lists_active or active_lists_target):
                pairs.append((a, t))
    return pairs


# ── The listing exposes the data (this part works) ───────────────────────────

def test_listing_exposes_incompatible_with_from_yaml(lm):
    body = lm.client.get("/loadouts").json()
    assert set(body) == set(lm.profiles)
    for name, p in lm.profiles.items():
        assert body[name]["incompatible_with"] == p.get("incompatible_with", [])
        assert body[name]["compatible_with"] == p.get("compatible_with", [])


def test_listing_marks_only_the_active_profile(lm):
    lm.make_active("training-unsloth")
    body = lm.client.get("/loadouts").json()
    assert [n for n, p in body.items() if p["active"]] == ["training-unsloth"]


# ── ...but nothing enforces it ───────────────────────────────────────────────

@pytest.mark.xfail(
    strict=True,
    reason="BUG-1: incompatible_with is never consulted by POST /activate; the "
           "only 'enforcement' is the UI disabling the card (ProfileCard.jsx). "
           "A direct API call, curl, or a schedule entry sails through.")
@pytest.mark.parametrize("active,target", [
    ("inference-4gpu", "training-lora-text"),      # inference -> training
    ("training-lora-text", "inference-4gpu"),      # training  -> inference
    ("inference-pair-a", "training-unsloth"),      # shared GPU0/GPU3
    ("training-unsloth", "inference-pair-a"),
    ("dual-stack", "training-lora-image"),
    ("training-lora-image", "inference-pair-b"),   # shared GPU1/GPU2
])
def test_incompatible_activation_is_refused_and_starts_nothing(lm, active, target):
    lm.make_active(active)
    r = lm.activate(target)
    assert is_4xx(r), f"{target} was accepted while {active} is active"
    assert lm.docker.calls == []
    assert lm.state["active_profile"] == active


@pytest.mark.xfail(
    strict=True,
    reason="BUG-1: sweep over every (active,target) pair that the YAML declares "
           "incompatible (target.incompatible_with contains active, the direction "
           "the UI uses). None are refused by the API.")
def test_every_declared_incompatible_pair_is_refused(lm):
    pairs = incompatible_pairs(lm.profiles, "target_lists_active")
    assert len(pairs) > 40, "sanity: data should declare dozens of pairs"
    accepted = []
    for active, target in pairs:
        lm.docker.calls.clear()
        lm.make_active(active)
        if not is_4xx(lm.activate(target)):
            accepted.append((active, target))
    assert accepted == [], f"{len(accepted)}/{len(pairs)} incompatible pairs accepted"


@pytest.mark.xfail(
    strict=True,
    reason="BUG-2: incompatible_with is declared one-way for 8 pairs. Neither the "
           "UI nor any future gate that reads only the target's list would stop "
           "inference-small being activated over training-unsloth (both own "
           "GPU0+GPU3) although unsloth lists inference-small.")
def test_reverse_direction_of_an_asymmetric_pair_is_also_refused(lm):
    lm.make_active("training-unsloth")
    r = lm.activate("inference-small")
    assert is_4xx(r)
    assert lm.docker.starts == []


# ── Compatible combinations and same-profile activation ─────────────────────

@pytest.mark.parametrize("active,target", [
    ("inference-small", "training-lora-image"),   # GPU0/3 vs GPU1/2, listed by neither
    ("training-lora-image", "inference-small"),
    ("training-unsloth", "inference-pair-b"),     # GPU0/3 vs GPU1/2, listed by neither
    ("inference-small", "image-studio"),          # declared compatible_with
])
def test_compatible_combination_is_accepted(lm, active, target):
    # Must keep passing once a gate exists: these are NOT declared incompatible
    # in either direction (checked by the next test).
    assert target not in lm.profiles[active].get("incompatible_with", [])
    lm.make_active(active)
    r = lm.activate(target)
    assert r.status_code == 200
    assert lm.state["active_profile"] == target


def test_compat_fixture_pairs_really_are_undeclared(lm):
    p = lm.profiles
    assert "inference-small" not in p["training-lora-image"].get("incompatible_with", [])
    assert "training-lora-image" not in p["inference-small"].get("incompatible_with", [])
    assert "inference-pair-b" not in p["training-unsloth"].get("incompatible_with", [])
    assert "training-unsloth" not in p["inference-pair-b"].get("incompatible_with", [])


def test_activating_the_already_active_profile_restarts_it(lm):
    """
    Characterisation. Re-activating the active profile is neither refused nor a
    no-op: it tears the stacks down and brings the same profile back up. That is
    a restart, which is a defensible reading of 'same profile'. (The VRAM gate
    can still wrongly refuse it — see BUG-4 in test_vram_gate.py.)
    """
    lm.make_active("inference-small")
    r = lm.activate("inference-small")
    assert r.status_code == 200
    assert len(lm.docker.downs) == 3
    assert len(lm.docker.starts) == 1
    assert lm.state["active_profile"] == "inference-small"


def test_no_profile_lists_itself_as_incompatible(lm):
    for name, p in lm.profiles.items():
        assert name not in p.get("incompatible_with", []), name


def test_incompatible_with_references_only_known_profiles(lm):
    known = set(lm.profiles)
    for name, p in lm.profiles.items():
        for key in ("incompatible_with", "compatible_with"):
            assert set(p.get(key, [])) <= known, (name, key)


@pytest.mark.xfail(
    strict=True,
    reason="BUG-2: 8 incompatible_with declarations have no mirror entry "
           "(e.g. training-unsloth lists inference-small, inference-small lists "
           "nothing). Fix the YAML or have the gate use the symmetric closure.")
def test_incompatible_with_is_symmetric(lm):
    asym = [(a, b) for a, b in incompatible_pairs(lm.profiles, "either")
            if not (a in lm.profiles[b].get("incompatible_with", [])
                    and b in lm.profiles[a].get("incompatible_with", []))]
    assert asym == []


@pytest.mark.xfail(
    strict=True,
    reason="BUG-2: inference-small and image-studio are mutually compatible_with "
           "yet both claim exclusive GPU0. Exclusive means no sharing.")
def test_compatible_with_pairs_do_not_share_exclusive_gpus(lm):
    clashes = []
    for a, pa in lm.profiles.items():
        for b in pa.get("compatible_with", []):
            shared = set(pa["exclusive_gpus"]) & set(lm.profiles[b]["exclusive_gpus"])
            if shared:
                clashes.append((a, b, sorted(shared)))
    assert clashes == []


def test_compatible_with_cannot_be_honoured_because_every_switch_tears_down(lm):
    """
    Semantic finding, passes today: a switch always runs `down` on all three
    managed stacks, so 'compatible_with: can run simultaneously' (plan step 06)
    is unrealisable through /activate. Activating image-studio over inference-small
    stops inference-small; the two never co-exist.
    """
    lm.make_active("inference-small")
    assert lm.activate("image-studio").status_code == 200
    downs_before_up = [c for c in lm.docker.downs if c.seq < lm.docker.starts[0].seq]
    assert {f for c in downs_before_up for f in c.compose_files} == {
        "compose.inference.yml", "compose.training.yml", "compose.studio.yml"}
    assert lm.state["running_services"] == lm.profiles["image-studio"]["services"]
