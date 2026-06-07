# GHC Task: Phase 01 — Jumpbox & Networking
**Brief ID:** P01-001
**Source doc:** `/plan/steps/01-jumpbox-networking.md`
**Write feedback to:** `/plan/ghc-feedback/phase01-jumpbox-networking.md`

---

## Context

This is the first phase of a 15-phase AI workstation build. You are creating all
configuration files for the jumpbox (Ryzen machine) and workstation (Threadripper machine)
network layer. These files live in the project repo and are deployed manually to the
target machines by the user. Do not assume SSH access — output files only.

**Network topology:**
```
Internet / LAN → Jumpbox (10.10.10.1) → [10GbE direct link] → Workstation (10.10.10.2)
```

The jumpbox is the ONLY external entry point. The workstation has no direct LAN exposure.

---

## Your Job

Create the following files exactly as specified. Do not add features not listed here.

---

### 1. `configs/network/jumpbox-10gbe.yaml`

Netplan config for the jumpbox 10GbE interface.

```yaml
network:
  version: 2
  ethernets:
    enp5s0:                        # placeholder — user must replace with actual interface name
      addresses:
        - 10.10.10.1/30
      mtu: 9000
      optional: true
```

---

### 2. `configs/network/workstation-10gbe.yaml`

Netplan config for the workstation 10GbE interface.

```yaml
network:
  version: 2
  ethernets:
    enp2s0f0:                      # placeholder — user must replace with actual interface name
      addresses:
        - 10.10.10.2/30
      mtu: 9000
      optional: true
```

---

### 3. `configs/caddy/Caddyfile`

Reverse proxy config for Caddy on the jumpbox. Routes all traffic to workstation services.
Uses internal TLS (Caddy's local CA). Basic auth is a Phase 13 placeholder — flag it in feedback.

```caddy
{
    local_certs
    log {
        level INFO
    }
}

ai.local {
    tls internal

    # Basic auth — PLACEHOLDER. Replace with Authentik forward auth in Phase 13.
    basicauth /* {
        kasem $2a$14$REPLACE_WITH_OUTPUT_OF_caddy_hash-password
    }

    # Open WebUI — primary chat UI
    handle /webui/* {
        uri strip_prefix /webui
        reverse_proxy 10.10.10.2:3000
    }

    # Loadout Manager API
    handle /loadout/* {
        uri strip_prefix /loadout
        reverse_proxy 10.10.10.2:8800
    }

    # Grafana monitoring
    handle /grafana/* {
        reverse_proxy 10.10.10.2:3001
    }

    # n8n workflows
    handle /n8n/* {
        reverse_proxy 10.10.10.2:5678
    }

    # JupyterLab
    handle /lab/* {
        reverse_proxy 10.10.10.2:8888
    }

    # ComfyUI
    handle /comfy/* {
        uri strip_prefix /comfy
        reverse_proxy 10.10.10.2:8188
    }

    # vLLM pair A (for Continue.dev / API clients)
    handle /vllm-a/* {
        uri strip_prefix /vllm-a
        reverse_proxy 10.10.10.2:8000
    }

    # vLLM pair B
    handle /vllm-b/* {
        uri strip_prefix /vllm-b
        reverse_proxy 10.10.10.2:8001
    }

    # Ollama API
    handle /ollama/* {
        uri strip_prefix /ollama
        reverse_proxy 10.10.10.2:11434
    }

    # Default: Open WebUI
    handle {
        reverse_proxy 10.10.10.2:3000
    }
}
```

---

### 4. `configs/wireguard/wg0.conf`

WireGuard config template for the jumpbox. Values in `< >` must be filled in by the user.

```ini
[Interface]
Address = 10.20.0.1/24
ListenPort = 51820
PrivateKey = <jumpbox-private-key — generate with: wg genkey>

[Peer]
# Remote client (laptop, phone, etc.)
PublicKey = <client-public-key>
AllowedIPs = 10.20.0.2/32
```

---

### 5. `scripts/deploy-jumpbox-network.sh`

Deployment script the user runs ON the jumpbox to apply the network and Caddy configs.
This script is idempotent — safe to run multiple times.

```bash
#!/usr/bin/env bash
# Deploy Phase 01 networking configs to the jumpbox.
# Run this script ON the jumpbox as a user with sudo.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Phase 01: Jumpbox Network + Caddy Deploy ==="

# ── 1. Netplan ────────────────────────────────────────────────────────────────
echo "[1/4] Installing netplan config..."
echo "  ⚠  Edit $REPO_ROOT/configs/network/jumpbox-10gbe.yaml"
echo "     Replace 'enp5s0' with your actual 10GbE interface name (check: ip link show)"
read -rp "  Interface name confirmed? (y/N): " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted. Edit the yaml first."; exit 1; }

sudo cp "$REPO_ROOT/configs/network/jumpbox-10gbe.yaml" /etc/netplan/01-10gbe.yaml
sudo chmod 600 /etc/netplan/01-10gbe.yaml
sudo netplan apply
echo "  ✓ Netplan applied"

# ── 2. Caddy install ──────────────────────────────────────────────────────────
echo "[2/4] Installing Caddy..."
if ! command -v caddy &>/dev/null; then
    sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        | sudo tee /etc/apt/sources.list.d/caddy-stable.list
    sudo apt update && sudo apt install -y caddy
    echo "  ✓ Caddy installed"
else
    echo "  ✓ Caddy already installed ($(caddy version))"
fi

# ── 3. Caddy password hash ────────────────────────────────────────────────────
echo "[3/4] Generate basic auth password hash..."
echo "  Run this command and paste the output into configs/caddy/Caddyfile"
echo "  replacing the REPLACE_WITH_OUTPUT_OF_caddy_hash-password placeholder:"
echo ""
echo "    caddy hash-password --plaintext 'your-chosen-password'"
echo ""
read -rp "  Caddyfile updated with hash? (y/N): " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted. Update Caddyfile first."; exit 1; }

# ── 4. Caddy config deploy ────────────────────────────────────────────────────
echo "[4/4] Deploying Caddyfile..."
sudo cp "$REPO_ROOT/configs/caddy/Caddyfile" /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl enable --now caddy
sudo systemctl reload caddy
echo "  ✓ Caddy running"

echo ""
echo "=== Phase 01 deploy complete ==="
echo ""
echo "Next manual steps:"
echo "  1. Apply workstation netplan: copy configs/network/workstation-10gbe.yaml"
echo "     to /etc/netplan/01-10gbe.yaml ON the workstation, then: sudo netplan apply"
echo "  2. Verify link: ping 10.10.10.2 from jumpbox"
echo "  3. Verify jumbo frames: ping -M do -s 8972 10.10.10.2"
echo "  4. Verify throughput: iperf3 -s on workstation, iperf3 -c 10.10.10.2 -t 30 -P 4 on jumpbox"
echo "  5. Add to /etc/hosts on client machines: 10.10.10.1  ai.local"
echo "  6. (Optional) Deploy WireGuard: configs/wireguard/wg0.conf"
```

---

### 6. `scripts/validate-phase01.sh`

Validation script the user runs from the jumpbox after deploying. Checks all Phase 01
success criteria.

```bash
#!/usr/bin/env bash
# Run ON the jumpbox after deploy-jumpbox-network.sh completes.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0

check() {
    local desc="$1"; shift
    if eval "$@" &>/dev/null; then
        echo -e "${GREEN}✓${NC} $desc"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $desc"
        ((FAIL++))
    fi
}

warn() {
    echo -e "${YELLOW}?${NC} $1 — check manually"
}

echo "=== Phase 01 Validation ==="
echo ""

check "Caddy is running"           "systemctl is-active --quiet caddy"
check "Caddy config is valid"      "caddy validate --config /etc/caddy/Caddyfile 2>/dev/null"
check "10GbE interface has IP"     "ip addr show | grep -q '10.10.10.1'"
check "Netplan config installed"   "test -f /etc/netplan/01-10gbe.yaml"
check "Workstation reachable"      "ping -c2 -W2 10.10.10.2"
check "Jumbo frames work"          "ping -M do -s 8972 -c1 -W3 10.10.10.2"

warn "iperf3 throughput ≥ 9 Gbps — run: iperf3 -c 10.10.10.2 -t 10 -P 4"
warn "https://ai.local resolves — add 10.10.10.1 to /etc/hosts on client"
warn "BMC accessible only from management interface — verify manually"
warn "Basic auth hash replaced in Caddyfile — verify no placeholder remains"

echo ""
echo "Result: ${PASS} passed, ${FAIL} failed"
[[ $FAIL -eq 0 ]] && echo -e "${GREEN}Phase 01 READY${NC}" || echo -e "${RED}Phase 01 NOT READY — fix failures above${NC}"
exit $FAIL
```

---

## Constraints

- **Do not invent interface names.** `enp5s0` and `enp2s0f0` are placeholders — the deploy script prompts the user to confirm.
- **Do not hardcode a real password hash.** The Caddyfile placeholder must remain as `REPLACE_WITH_OUTPUT_OF_caddy_hash-password` in the file you create.
- **Whisper is on port 9099**, not 9000. Do not add a Caddy route for Whisper at 9000.
- **Do not create a Caddy route for MinIO** — MinIO console (9001) is internal only, not proxied.
- All files go under the project root (`d:\src\ai-workstation-project\` on Windows, will be deployed to Linux).

---

## Done When

- [ ] `configs/network/jumpbox-10gbe.yaml` created
- [ ] `configs/network/workstation-10gbe.yaml` created
- [ ] `configs/caddy/Caddyfile` created with all routes from the ports table
- [ ] `configs/wireguard/wg0.conf` created
- [ ] `scripts/deploy-jumpbox-network.sh` created and marked executable (chmod note in feedback)
- [ ] `scripts/validate-phase01.sh` created
- [ ] No real secrets or password hashes in any file
- [ ] All files use Unix line endings (LF)

---

## Return to Claude

In your feedback file, include:
1. List of all files created with their paths
2. Any lines you deviated from the spec and why
3. Flag: does the Caddyfile placeholder string remain exactly as specified?
4. Flag: are there any routes missing from the ports table you think should be added?
5. Any blockers or questions before Phase 02 can start
