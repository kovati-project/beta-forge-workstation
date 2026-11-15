"""
api/admin.py user + group endpoints against a faked Authentik (#54).

Authentik's HTTP API is replaced by an in-memory fake served through
``httpx.MockTransport``; nothing leaves the process. The fake models only what
admin.py relies on (core/users, core/groups, add_user/remove_user, paginated
listings), so these tests prove the request flow, not that a live Authentik
release accepts it. That still needs checking on the host (see the PR).
"""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]

ADMIN_PK = "11111111-1111-1111-1111-111111111111"
DEV_PK = "22222222-2222-2222-2222-222222222222"
USER_PK = "33333333-3333-3333-3333-333333333333"


class FakeAuthentik:
    """Just enough of /api/v3/core/{users,groups}/ for admin.py."""

    def __init__(self):
        self.groups = {
            ADMIN_PK: {"pk": ADMIN_PK, "name": "Administrator", "is_superuser": False, "parent_name": None},
            DEV_PK: {"pk": DEV_PK, "name": "Developer", "is_superuser": False, "parent_name": None},
            USER_PK: {"pk": USER_PK, "name": "User", "is_superuser": False, "parent_name": None},
        }
        self.users = {}
        self.next_pk = 7
        self.calls = []            # (method, path)
        self.page_size = 100
        self.include_groups_obj = True
        self.fail = {}             # (method, path regex) -> status

    def add_user(self, username, groups=()):
        pk = self.next_pk
        self.next_pk += 1
        self.users[pk] = {"pk": pk, "username": username, "email": f"{username}@x", "name": username,
                          "is_active": True, "groups": list(groups)}
        return pk

    def _user_out(self, u):
        out = dict(u)
        if self.include_groups_obj:
            out["groups_obj"] = [dict(self.groups[g]) for g in u["groups"]]
        return out

    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]

    def handler(self, request: httpx.Request) -> httpx.Response:
        method, path = request.method, request.url.path
        self.calls.append((method, path))
        if request.headers.get("authorization") != "Bearer test-token":
            return httpx.Response(403)
        for (m, rx), status in self.fail.items():
            if m == method and re.fullmatch(rx, path):
                return httpx.Response(status, json={"detail": "injected"})
        body = json.loads(request.content) if request.content else {}

        if path == "/api/v3/core/groups/" and method == "GET":
            assert request.url.params.get("include_users") == "false"
            items = sorted(self.groups.values(), key=lambda g: g["name"])
            page = int(request.url.params.get("page", 1))
            chunk = items[(page - 1) * self.page_size: page * self.page_size]
            more = page * self.page_size < len(items)
            return httpx.Response(200, json={
                "pagination": {"count": len(items), "current": page, "next": page + 1 if more else 0},
                "results": chunk})

        m = re.fullmatch(r"/api/v3/core/groups/([^/]+)/(add_user|remove_user)/", path)
        if m and method == "POST":
            gpk, action = m.groups()
            user = self.users.get(body.get("pk"))
            if gpk not in self.groups or user is None:
                return httpx.Response(404)
            if action == "add_user" and gpk not in user["groups"]:
                user["groups"].append(gpk)
            if action == "remove_user" and gpk in user["groups"]:
                user["groups"].remove(gpk)
            return httpx.Response(204)

        if path == "/api/v3/core/users/" and method == "GET":
            users = [self._user_out(u) for u in self.users.values()]
            return httpx.Response(200, json={"pagination": {"count": len(users)}, "results": users})

        if path == "/api/v3/core/users/" and method == "POST":
            pk = self.add_user(body["username"], body.get("groups", []))
            self.users[pk].update(email=body["email"], name=body["name"])
            return httpx.Response(201, json=self._user_out(self.users[pk]))

        m = re.fullmatch(r"/api/v3/core/users/(\d+)/(set_password/)?", path)
        if m:
            user = self.users.get(int(m.group(1)))
            if user is None:
                return httpx.Response(404)
            if m.group(2) and method == "POST":
                return httpx.Response(204)
            if method == "GET":
                return httpx.Response(200, json=self._user_out(user))
            if method == "PATCH":
                user.update(body)
                return httpx.Response(200, json=self._user_out(user))
        return httpx.Response(404, json={"detail": f"fake has no {method} {path}"})


@pytest.fixture
def ak(lm, monkeypatch):
    """The FastAPI client plus a FakeAuthentik wired into api.admin."""
    from api import admin

    fake = FakeAuthentik()
    transport = httpx.MockTransport(fake.handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        return real_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr(admin, "httpx", SimpleNamespace(AsyncClient=client_factory))
    monkeypatch.setattr(admin, "AUTHENTIK_URL", "http://authentik.test")
    monkeypatch.setattr(admin, "AUTHENTIK_TOKEN", "test-token")
    return SimpleNamespace(client=lm.client, fake=fake, admin=admin)


# ── GET /api/admin/groups ────────────────────────────────────────────────────

def test_list_groups(ak):
    r = ak.client.get("/api/admin/groups")
    assert r.status_code == 200
    body = r.json()
    assert [g["name"] for g in body["groups"]] == ["Administrator", "Developer", "User"]
    assert body["count"] == 3
    assert set(body["groups"][0]) == {"pk", "name", "is_superuser", "parent_name"}


def test_list_groups_follows_pagination(ak):
    ak.fake.page_size = 2
    r = ak.client.get("/api/admin/groups")
    assert [g["name"] for g in r.json()["groups"]] == ["Administrator", "Developer", "User"]
    assert ak.fake.calls.count(("GET", "/api/v3/core/groups/")) == 2


def test_list_groups_without_token(ak, monkeypatch):
    monkeypatch.setattr(ak.admin, "AUTHENTIK_TOKEN", "")
    r = ak.client.get("/api/admin/groups")
    assert r.status_code == 200
    assert r.json()["groups"] == []
    assert ak.fake.calls == []


def test_list_groups_authentik_error_is_502(ak):
    ak.fake.fail[("GET", "/api/v3/core/groups/")] = 500
    assert ak.client.get("/api/admin/groups").status_code == 502


# ── users carry their groups ─────────────────────────────────────────────────

def test_list_users_includes_group_names(ak):
    ak.fake.add_user("alice", [DEV_PK, ADMIN_PK])
    ak.fake.add_user("bob")
    users = {u["username"]: u for u in ak.client.get("/api/admin/users").json()["users"]}
    assert users["alice"]["group_names"] == ["Administrator", "Developer"]
    assert users["bob"]["group_names"] == []
    assert sorted(users["alice"]["groups"]) == sorted([DEV_PK, ADMIN_PK])


def test_group_names_fall_back_to_group_lookup_without_groups_obj(ak):
    ak.fake.include_groups_obj = False
    ak.fake.add_user("alice", [USER_PK])
    users = ak.client.get("/api/admin/users").json()["users"]
    assert users[0]["group_names"] == ["User"]


def test_get_user(ak):
    pk = ak.fake.add_user("alice", [DEV_PK])
    r = ak.client.get(f"/api/admin/users/{pk}")
    assert r.status_code == 200
    assert r.json()["username"] == "alice"
    assert r.json()["group_names"] == ["Developer"]


def test_get_unknown_user_is_404(ak):
    assert ak.client.get("/api/admin/users/999").status_code == 404


# ── create with groups ───────────────────────────────────────────────────────

def test_create_user_with_groups_by_name_and_pk(ak):
    r = ak.client.post("/api/admin/users", json={
        "username": "carol", "email": "carol@x", "password": "pw-long-enough",
        "groups": ["Developer", USER_PK]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["group_names"] == ["Developer", "User"]
    assert sorted(ak.fake.users[body["pk"]]["groups"]) == sorted([DEV_PK, USER_PK])
    assert ("POST", f"/api/v3/core/groups/{DEV_PK}/add_user/") in ak.fake.calls
    assert ("POST", f"/api/v3/core/groups/{USER_PK}/add_user/") in ak.fake.calls


def test_create_user_without_groups_makes_no_group_calls(ak):
    r = ak.client.post("/api/admin/users", json={
        "username": "dave", "email": "dave@x", "password": "pw-long-enough"})
    assert r.status_code == 200
    assert r.json()["group_names"] == []
    assert not [c for c in ak.fake.calls if "/groups/" in c[1]]


def test_create_user_with_unknown_group_creates_nothing(ak):
    r = ak.client.post("/api/admin/users", json={
        "username": "eve", "email": "eve@x", "password": "pw-long-enough",
        "groups": ["Developer", "Wizards"]})
    assert r.status_code == 400
    assert "Wizards" in r.json()["detail"]
    assert ak.fake.users == {}
    assert ak.fake.writes() == []


def test_create_user_group_failure_is_reported(ak):
    ak.fake.fail[("POST", r"/api/v3/core/groups/.+/add_user/")] = 403
    r = ak.client.post("/api/admin/users", json={
        "username": "frank", "email": "frank@x", "password": "pw-long-enough",
        "groups": ["Developer"]})
    assert r.status_code == 502
    assert "group assignment failed" in r.json()["detail"]


# ── update group membership ──────────────────────────────────────────────────

def test_update_groups_adds_and_removes(ak):
    pk = ak.fake.add_user("alice", [USER_PK, DEV_PK])
    r = ak.client.patch(f"/api/admin/users/{pk}", json={"groups": ["Administrator", "Developer"]})
    assert r.status_code == 200, r.text
    assert r.json()["group_names"] == ["Administrator", "Developer"]
    assert sorted(ak.fake.users[pk]["groups"]) == sorted([ADMIN_PK, DEV_PK])
    assert ak.fake.writes() == [
        ("POST", f"/api/v3/core/groups/{ADMIN_PK}/add_user/"),
        ("POST", f"/api/v3/core/groups/{USER_PK}/remove_user/"),
    ]


def test_update_groups_empty_list_removes_all(ak):
    pk = ak.fake.add_user("alice", [USER_PK, DEV_PK])
    r = ak.client.patch(f"/api/admin/users/{pk}", json={"groups": []})
    assert r.status_code == 200
    assert r.json()["group_names"] == []
    assert ak.fake.users[pk]["groups"] == []


def test_update_groups_unchanged_makes_no_writes(ak):
    pk = ak.fake.add_user("alice", [DEV_PK])
    r = ak.client.patch(f"/api/admin/users/{pk}", json={"groups": ["Developer"]})
    assert r.status_code == 200
    assert ak.fake.writes() == []


def test_update_fields_and_groups_together(ak):
    pk = ak.fake.add_user("alice")
    r = ak.client.patch(f"/api/admin/users/{pk}", json={"email": "new@x", "groups": ["User"]})
    assert r.status_code == 200
    assert r.json()["email"] == "new@x"
    assert r.json()["group_names"] == ["User"]
    assert ("PATCH", f"/api/v3/core/users/{pk}/") in ak.fake.calls


def test_update_without_groups_leaves_membership(ak):
    pk = ak.fake.add_user("alice", [DEV_PK])
    r = ak.client.patch(f"/api/admin/users/{pk}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["group_names"] == ["Developer"]
    assert not [c for c in ak.fake.calls if "/groups/" in c[1]]


def test_update_unknown_group_changes_nothing(ak):
    pk = ak.fake.add_user("alice", [DEV_PK])
    r = ak.client.patch(f"/api/admin/users/{pk}", json={"email": "new@x", "groups": ["Nope"]})
    assert r.status_code == 400
    assert ak.fake.writes() == []
    assert ak.fake.users[pk]["email"] == "alice@x"


def test_update_with_no_fields_is_400(ak):
    pk = ak.fake.add_user("alice")
    assert ak.client.patch(f"/api/admin/users/{pk}", json={}).status_code == 400


def test_update_unknown_user_is_404(ak):
    assert ak.client.patch("/api/admin/users/999", json={"groups": ["User"]}).status_code == 404


# ── bootstrap: the RBAC blueprint ────────────────────────────────────────────

def test_rbac_blueprint_defines_the_three_roles():
    bp = yaml.safe_load((REPO / "configs/authentik/blueprints/kovati-rbac-groups.yaml").read_text(encoding="utf-8"))
    assert bp["version"] == 1
    entries = bp["entries"]
    assert {e["identifiers"]["name"] for e in entries} == {"Administrator", "Developer", "User"}
    for e in entries:
        assert e["model"] == "authentik_core.group"
        # created == create-if-missing; never overwrites edits made in Authentik.
        assert e["state"] == "created"
        assert e["attrs"]["is_superuser"] is False


def test_blueprint_dir_is_mounted_into_authentik():
    compose = yaml.safe_load((REPO / "docker/compose.auth.yml").read_text(encoding="utf-8"))
    mount = "../configs/authentik/blueprints:/blueprints/custom:ro"
    for svc in ("authentik", "authentik-worker"):
        assert mount in compose["services"][svc]["volumes"], svc


def test_token_falls_back_to_docker_env(monkeypatch, tmp_path):
    """A token saved on the Settings page (docker/.env) applies without a restart."""
    from api import admin
    env_file = tmp_path / ".env"
    env_file.write_text("AUTHENTIK_TOKEN=from-dotenv\n")
    monkeypatch.setattr(admin, "AUTHENTIK_TOKEN", "")
    monkeypatch.setenv("ENV_FILE", str(env_file))
    assert admin._token() == "from-dotenv"
    assert admin._auth_headers() == {"Authorization": "Bearer from-dotenv"}

    monkeypatch.setattr(admin, "AUTHENTIK_TOKEN", "from-environment")
    assert admin._token() == "from-environment"
