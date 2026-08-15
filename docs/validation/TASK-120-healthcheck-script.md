# TASK-120 — Run and validate the healthcheck script

**Issue:** #44
**Result: RAN — script works; 6 checks fail, and the deployment it checks is stale.**

## Where the code actually lives

The issue's path (`~/ai-workstation`) does not exist. There are **three** copies of
this repo on the box:

| Path | Git state |
| --- | --- |
| `/srv/src/src/beta-workstation` | commit `9ffd774`, 2026-06-29 — the deployed copy |
| `/home/kasemo/beta-workstation` | unreadable (dubious ownership under this account) |
| `/home/kasemo/ai-workstation-project` | not a git repository |

## The finding that matters most

**The deployed copy is behind `main`.** `/srv/src/src/beta-workstation` sits at
`9ffd774` (2026-06-29). Commits made after it on `main`:

- `f486145` — fix(security): remove hardcoded MinIO password from scripts
- `39990e4` — fix(security): rotate hardcoded SearXNG secret_key
- `490ff5d` — docs: Authentik + Caddy debug handoff notes
- `a48ef70` — docs: add AGPLv3 LICENSE

So **both security rotations are absent from the running deployment.** #66 is marked
closed and the fix is real, but it is not on this box. That also explains why the
`mc` alias `local` still fails with Access Denied — the rotation happened in the repo
and never reached the host.

Three divergent copies with no clear canonical also makes "is this fixed on the box?"
unanswerable without checking each. Worth resolving independently of this task.

## Healthcheck results

The script runs cleanly and its checks are meaningful. Captured output:

| Group | Result |
| --- | --- |
| Infrastructure | Docker daemon, Docker compose — pass |
| Storage | MinIO, Qdrant, PostgreSQL (+container) pass; **MinIO Console fails** (HTTP 200, expected 403) |
| Monitoring | Prometheus, Grafana, Node Exporter, DCGM pass; **cAdvisor fails** (HTTP 307, expected 200) |
| Auth & Gateway | Authentik PostgreSQL, Redis pass; **Authentik fails** (HTTP 302, expected 200) |
| GPU orchestration | Loadout Manager pass |
| Inference | Ollama, vLLM Pair A (GPU 0+3), ComfyUI, Open WebUI, SearXNG — all pass |
| Training | Kohya not running (expected — no training profile active); **Label Studio** (302) and **JupyterLab** (302) fail |

## Assessing the failures

Four of the six are almost certainly **wrong expectations rather than broken
services**:

- **Authentik 302** — an unauthenticated request to an IdP redirecting to a login
  flow is correct behaviour. Expecting 200 is wrong.
- **Label Studio 302**, **JupyterLab 302** — same shape: both redirect to a login
  page when unauthenticated.
- **cAdvisor 307** — cAdvisor redirects `/` to `/containers/`. Normal.
- **MinIO Console 200 where 403 was expected** — the inverse: the script expects the
  console to be locked down and it is answering. Worth a look, though a console
  login page returning 200 is also unremarkable.

The script does not follow redirects or accept redirect codes as healthy, so any
service that gates behind auth is reported as failing. That is a defect in the
healthcheck, not in the estate.

## Not captured

The tail of the output — Voice, Agentic and the summary block — was not retrieved;
SSH to the host is intermittent and dropped mid-run twice. The captured portion runs
from Infrastructure through Training Services.

## Verdict

The script works and is useful. Recommend it treat 3xx as healthy for auth-gated
services, otherwise it will keep reporting four false failures. The stale deployment
is the more urgent finding.
