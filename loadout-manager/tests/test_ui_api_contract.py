"""
Every /api/... URL the React UI calls must be served by a backend route.

URLs are scraped from ui/src (string and template literals); ``${...}`` becomes a
placeholder segment. Matching is by path only (the UI's HTTP method is not
parsed), so this catches missing and renamed endpoints, not wrong verbs.

This replaces the old test_step*.py scripts, which only checked that hand-listed
routes existed on each router.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
UI_SRC = REPO / "ui" / "src"
URL = re.compile(r"""['"`](/api/[^'"`?\s]*)""")

# Template URLs whose variables pick a route rather than an id.
EXPAND = {
    "/api/services/x/x": ["/api/services/x/start", "/api/services/x/stop"],
}

# UI calls with no backend route today (UI-1). Remove an entry when the
# endpoint is added; strict xfail fails the run until you do.
MISSING = {
    "/api/mcp/x/test":           "backend has POST /api/mcp/test (name in body)",
    "/api/network/routes/x":     "no route-exposure endpoint",
    "/api/platform/setup":       "no /api/platform router",
    "/api/storage/buckets/x":    "only GET /api/storage/buckets exists",
    "/api/storage/upload":       "no upload endpoint; Datasets upload cannot work",
    "/api/vectors/collections/x": "only GET /api/vectors/collections exists",
    "/api/vectors/re-embed":     "no re-embed endpoint",
}


def _ui_paths():
    paths = {}
    for f in sorted(UI_SRC.rglob("*.js*")):
        for m in URL.finditer(f.read_text(encoding="utf-8")):
            p = re.sub(r"\$\{[^}]*\}", "x", m.group(1)).rstrip("/")
            paths.setdefault(p, f.relative_to(REPO).as_posix())
    return paths


UI_PATHS = _ui_paths()


def _params():
    for path, source in sorted(UI_PATHS.items()):
        marks = []
        if path in MISSING:
            marks.append(pytest.mark.xfail(
                strict=True, reason=f"UI-1: {source} calls {path}; {MISSING[path]}"))
        yield pytest.param(path, id=path, marks=marks)


@pytest.fixture(scope="module")
def api_routes(main_module):
    # The OpenAPI schema, not app.routes: newer FastAPI wraps included routers
    # lazily, so walking app.routes does not see them.
    paths = [p for p in main_module.app.openapi()["paths"] if p.startswith("/api")]
    return [re.compile("[^/]+".join(map(re.escape, re.split(r"\{[^}]+\}", p))) + "$")
            for p in paths]


def test_ui_source_was_scanned():
    assert len(UI_PATHS) > 50, "URL scrape found almost nothing; did ui/src move?"


def test_missing_list_is_not_stale():
    assert set(MISSING) <= set(UI_PATHS), set(MISSING) - set(UI_PATHS)


@pytest.mark.parametrize("path", _params())
def test_ui_call_has_a_backend_route(path, api_routes):
    for concrete in EXPAND.get(path, [path]):
        assert any(r.match(concrete) for r in api_routes), concrete
