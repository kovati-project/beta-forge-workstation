# KOVATI OS — Component Spec 12
## Distro Productization
*ISO build · tier enforcement · appliance mode · branding · update mechanism · air-gap*

---

## 1. Purpose

This spec covers the Phase 15 work: converting the 15-phase workstation build into a bootable Linux distribution product. The UI and backend are largely complete by this point; this phase adds the ISO packaging, tiered licensing enforcement, appliance deployment tooling, and branding system around them.

KOVATI OS is an **Open Core** product. The Community tier is fully functional and free. Professional and Enterprise tiers add managed features enforced by a license key.

---

## 2. Product Tiers

### Tier Definitions

| Tier | Price | Target | License Mechanism |
|------|-------|--------|-------------------|
| Community | Free (MIT for core, proprietary for UI shell) | Individual researchers, hobbyists | No key required |
| Professional | ~$499–$999 /node /year | AI/ML teams, startups | License key, annual renewal |
| Enterprise | Custom contract | MSPs, defense/gov, air-gap | Signed license bundle + support SLA |

### Feature Matrix

| Feature | Community | Professional | Enterprise |
|---------|-----------|-------------|------------|
| All 30 services | ✓ | ✓ | ✓ |
| Full UI | ✓ | ✓ | ✓ |
| First-boot wizard | ✓ | ✓ | ✓ |
| Loadout switching | ✓ | ✓ | ✓ |
| Training workflows | ✓ | ✓ | ✓ |
| Community support | Forum | — | — |
| Validated upgrade paths | — | ✓ | ✓ |
| Loadout profile library | — | ✓ | ✓ |
| Stack compatibility matrix | — | ✓ | ✓ |
| Appliance mode | — | — | ✓ |
| LDAP/AD integration (Authentik) | — | — | ✓ |
| FIPS kernel profile | — | — | ✓ |
| Air-gap mode (offline image cache) | — | — | ✓ |
| Custom ISO builder | — | — | ✓ |
| Commercial support SLA | — | — | ✓ |

---

## 3. License Enforcement

### License Key Format

```
KOVATI-{TIER}-{NODE_ID}-{EXPIRY}-{HMAC_SIGNATURE}
```

- `TIER`: `PRO` or `ENT`
- `NODE_ID`: SHA256 of `/etc/machine-id` (first 8 chars) — ties license to this machine
- `EXPIRY`: YYYYMMDD
- `HMAC_SIGNATURE`: HMAC-SHA256 of `TIER:NODE_ID:EXPIRY` using private signing key

### License Validation

```python
# api/license.py
import hmac, hashlib, datetime

SIGNING_KEY = os.getenv("KOVATI_LICENSE_SIGNING_KEY")  # Not shipped, held by vendor

def validate_license(key: str) -> dict:
    parts = key.split("-")
    if len(parts) != 5:
        return {"valid": False, "tier": "community"}

    _, tier, node_id, expiry, sig = parts

    # Verify node binding
    machine_id = _get_machine_id()  # SHA256 /etc/machine-id [:8]
    if node_id != machine_id:
        return {"valid": False, "reason": "node_mismatch"}

    # Verify expiry
    if datetime.date.today() > datetime.date.fromisoformat(f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:]}"):
        return {"valid": False, "reason": "expired", "tier": tier.lower()}

    # Verify HMAC
    expected = hmac.new(SIGNING_KEY.encode(), f"{tier}:{node_id}:{expiry}".encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected):
        return {"valid": False, "reason": "invalid_signature"}

    return {"valid": True, "tier": tier.lower(), "expires": expiry}
```

License stored in `/etc/kovati-os/license.key`. Validated on boot and cached for 24h. No network license check required (works air-gap).

### UI Enforcement

```python
# config.py
LICENSE = validate_license(Path("/etc/kovati-os/license.key").read_text())
TIER = LICENSE.get("tier", "community")

FEATURE_FLAGS = {
    "validated_upgrades": TIER in ("professional", "enterprise"),
    "appliance_mode": TIER == "enterprise",
    "fips_mode": TIER == "enterprise",
    "air_gap": TIER == "enterprise",
    "profile_library": TIER in ("professional", "enterprise"),
}
```

FastAPI endpoint:
```
GET /api/license  → {tier, valid, expires, features}
```

Frontend reads this on mount and stores in AppContext. Feature-gated UI elements check `features.validated_upgrades` etc.

### Upgrade Path Lock (Professional)

In Professional tier, the "Update All Services" button in Settings is replaced by:

```
Update to validated stack snapshot:
  v1.2.1 (released 2026-07-01)  [Release notes]  [Install]
  
  Community users: arbitrary docker pull
  Professional: pinned, regression-tested snapshots only
```

Validated snapshots are a JSON manifest hosted on `updates.kovatios.io` (or air-gap equivalent).

---

## 4. ISO Build System

### Base OS

Ubuntu 26.04 LTS Server (minimal, no desktop environment, no snap). Customized with:

- NVIDIA driver 575+ (pre-installed, pinned)
- Docker Engine 27+ (pre-installed, daemon configured)
- NVIDIA Container Toolkit (pre-installed)
- Python 3.12 + pip (for Loadout Manager FastAPI)
- Node.js 22 LTS (for UI build, removed post-build from final ISO)
- `wg-quick` (WireGuard)
- `caddy` (reverse proxy)

### Build Toolchain

```
ubuntu-26.04-server-amd64.iso
    │
    └─ cubic (custom Ubuntu ISO creator) or live-build
       │
       ├── Pre-install packages (apt)
       ├── Copy ai-workstation-project/ → /opt/kovati-os/
       ├── Install Python deps (pip install -r requirements.txt)
       ├── Build React frontend (npm run build)
       ├── Configure systemd services (see section 5)
       ├── Install NVIDIA drivers (offline deb package included)
       └── Write /etc/kovati-os/distro-info.json
```

### ISO Variants

| ISO | Contents | Size |
|-----|---------|------|
| `kovatios-1.0-base.iso` | OS + drivers + stack (no model weights) | ~8 GB |
| `kovatios-1.0-full.iso` | Base + Qwen2.5-7B + SDXL weights pre-cached | ~40 GB |
| `kovatios-1.0-airgap.iso` | Full + all container images embedded | ~120 GB |

Air-gap ISO includes all Docker images as `tar.gz` files in `/opt/kovati-os/images/`, loaded via `docker load` during first-boot provisioning step.

---

## 5. systemd Service Configuration

```ini
# /etc/systemd/system/kovati-os.service
[Unit]
Description=KOVATI OS Control Plane
After=docker.service network-online.target nvidia-persistenced.service
Requires=docker.service

[Service]
Type=simple
User=kovatios
WorkingDirectory=/opt/kovati-os/loadout-manager
Environment=KOVATI_OS_MODE=workstation
EnvironmentFile=/opt/kovati-os/docker/.env
ExecStart=/usr/bin/uvicorn main:app --host 0.0.0.0 --port 8800 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Additional services:

```ini
# kovati-os-first-boot.service — runs wizard on first boot, then disables itself
[Unit]
Description=KOVATI OS First Boot Setup
After=kovati-os.service
ConditionPathExists=!/data/.kovati-setup-complete

[Service]
Type=oneshot
ExecStart=/opt/kovati-os/scripts/first-boot-trigger.sh
# Sets DISPLAY_SETUP=true env var → UI shows /setup on first access

[Install]
WantedBy=multi-user.target
```

---

## 6. Appliance Mode

Enterprise deployments use appliance mode for managed environments.

### Activation

Set during ISO build or post-deploy:
```bash
echo "KOVATI_OS_MODE=appliance" >> /etc/kovati-os/environment
systemctl restart kovati-os
```

Or via `POST /api/network {mode: "appliance"}` — requires admin role.

### Behavior Changes in Appliance Mode

**Settings panel:**
- Secret rotation: hidden
- Network edit: hidden
- Stack update: locked to validated snapshots
- Rollback: hidden
- Re-run wizard: hidden

**First-boot wizard:**
- After completion, wizard is permanently locked (cannot be re-run without `rm /data/.kovati-setup-complete` on the server)
- All wizard steps are pre-configured from a deployment manifest (`/etc/kovati-os/appliance-config.json`)

**Auth:**
- Authentik SSO is mandatory — the `kovati-os.service` will not serve the UI without Authentik running
- No local login bypass (the current dev mode `SKIP_AUTH=true` env var is ignored in appliance mode)

**Updates:**
- Only validated stack snapshots from `updates.kovatios.io`
- No arbitrary `docker pull` allowed

### Appliance Deployment Manifest

MSPs pre-configure appliances with:

```json
{
  "product_name": "AcmeCorp AI Box",
  "jumpbox_ip": "10.20.0.1",
  "wireguard_server": "vpn.acmecorp.com:51820",
  "authentik_ldap_server": "ldap://corp.acmecorp.com",
  "initial_profile": "inference-pair-a",
  "restricted_services": ["axolotl", "kohya_ss"],
  "update_channel": "stable"
}
```

The first-boot wizard reads this file and auto-fills all steps, requiring only confirmation from the operator.

---

## 7. Branding System

All user-facing product name references are controlled by environment variables:

```bash
KOVATI_OS_PRODUCT_NAME="KOVATI OS"        # Main product name
KOVATI_OS_PRODUCT_SHORT="NOS"             # Abbreviated (logo mark)
KOVATI_OS_VENDOR_NAME="Kovati LLC"        # Company name (footer, support links)
KOVATI_OS_SUPPORT_URL="https://..."       # Support link in UI
KOVATI_OS_DOCS_URL="https://..."          # Docs link in UI
```

The React frontend fetches `GET /api/branding` on mount and populates a `BrandContext`. No hardcoded product strings exist in the frontend source.

```js
// context/BrandContext.jsx
const BrandContext = createContext({
  productName: 'KOVATI OS',
  productShort: 'NOS',
  vendorName: '',
  supportUrl: '',
  docsUrl: '',
});
```

Enterprise customers with a custom ISO can set their own branding (white-label use case).

---

## 8. Air-Gap Mode

When `KOVATI_AIR_GAP=true`:

- First-boot provisioning (Step 5) skips `docker pull` and instead calls `docker load` on cached image tarballs in `/opt/kovati-os/images/`
- The validated update mechanism fetches from a local mirror URL (`KOVATI_UPDATE_MIRROR_URL`) instead of `updates.kovatios.io`
- License validation does not require any outbound connection
- WireGuard setup uses a local key exchange mechanism

**Image cache format:**
```
/opt/kovati-os/images/
├── manifest.json          ← lists image name, tag, filename, sha256
├── postgres-16.tar.gz
├── minio-latest.tar.gz
├── vllm-pair-a-v0.9.1.tar.gz
├── ...
```

**Load script:**
```bash
#!/bin/bash
for img in /opt/kovati-os/images/*.tar.gz; do
    docker load -i "$img"
done
```

---

## 9. FIPS Kernel Profile (Enterprise)

For deployments requiring FIPS 140-3 compliance:

```bash
# Applied during ISO build for Enterprise FIPS ISO variant
apt install linux-fips ubuntu-fips
fips-mode-setup --enable
```

Consequences:
- Some cryptographic algorithms in Docker and Python may need re-configuration
- WireGuard uses ChaCha20 — compatible with FIPS 140-3 in Ubuntu 22.04+
- PostgreSQL TLS must use FIPS-approved cipher suites only
- The `docker/.env` generator uses `openssl rand` instead of Python `secrets` module for FIPS compliance

A separate ISO build target `kovatios-1.0-enterprise-fips.iso` is produced for this configuration.

---

## 10. Release & Update Channel

### Validated Stack Snapshot Format

```json
{
  "version": "1.2.1",
  "released": "2026-07-01",
  "channel": "stable",
  "min_kovati_os_version": "1.0.0",
  "images": {
    "vllm-pair-a": {
      "image": "vllm/vllm-openai:v0.9.2",
      "digest": "sha256:abc123...",
      "changelog": "CUDA 12.5 support, 15% throughput improvement"
    },
    "ollama": {
      "image": "ollama/ollama:0.7.0",
      "digest": "sha256:def456...",
      "changelog": "Tool calling improvements"
    }
  },
  "signature": "base64-encoded HMAC of above JSON"
}
```

Snapshots are signed with the same vendor key used for license validation.

The FastAPI backend verifies the signature before applying any snapshot update.

### Release Channels

| Channel | Audience | Frequency |
|---------|---------|-----------|
| `stable` | Professional / Enterprise | Monthly |
| `lts` | Enterprise air-gap | Quarterly |
| `community` | Community self-managed | Anytime via `docker pull` |

---

## 11. Custom ISO Builder (Enterprise)

An Enterprise-only feature: a web UI wizard for building custom ISOs with pre-configured:

- Branding (product name, logo)
- Appliance manifest (network, auth, initial profile)
- Pre-cached model weights selection
- License key embedded
- Air-gap image cache inclusion

This runs as a separate service (`kovati-iso-builder`) and is out of scope for the initial v1.0 release — documented here as a Phase 16 item.

---

## 12. Build Automation

```yaml
# .github/workflows/iso-build.yml (or self-hosted Gitea)
name: KOVATI OS ISO Build

on:
  push:
    tags: ['v*']

jobs:
  build-base:
    runs-on: self-hosted-builder  # Machine with Docker + cubic
    steps:
      - Build React frontend
      - Run test suite
      - Build base ISO (kovatios-{version}-base.iso)
      - Generate SHA256 checksum
      - Sign with vendor key
      - Upload to release storage

  build-airgap:
    needs: build-base
    steps:
      - Pull all container images
      - Export to tar.gz
      - Embed in ISO
      - Build airgap ISO
```
