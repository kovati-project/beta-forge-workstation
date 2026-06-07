# GHC Task: Phase 15 — Linux Distro Product Specification
**Brief ID:** P15-001  
**Source doc:** `/plan/steps/15-distro-product-spec.md`  
**Write feedback to:** `/plan/ghc-feedback/phase15-distro-product-spec.md`

---

## Context

Phases 01–14 represent a fully operational, hardened AI workstation stack. Phase 15 productizes that work into a bootable Linux distribution — an opinionated, self-provisioning AI appliance OS targeting teams and organizations that need private on-premises inference without the 6–12 month integration burden of assembling this stack themselves.

This phase is **planning and specification work**, not deployment work. There is no server to SSH into and no Docker container to start. The deliverables are documents and pipeline skeletons that define how the distro will be built.

---

## Scope

Create:
1. **`distro/PRODUCT_SPEC.md`** — full product specification: problem, tiers, architecture, hardware targets, differentiation, open questions
2. **`distro/FIRST_BOOT_WIZARD.md`** — specification for the first-boot wizard: hardware probe, profile selector, stack provisioner, network wizard, and validation suite
3. **`distro/ISO_BUILD_PIPELINE.md`** — specification and skeleton for the GitHub Actions ISO build pipeline
4. **`distro/HARDWARE_COMPAT.md`** — hardware compatibility matrix: validated tier, community tier, not targeted
5. **`distro/GTM.md`** — go-to-market plan: Community → Professional → Enterprise launch phases, pricing model, open questions

**Not in scope:** Actual ISO build implementation (requires dedicated repository and 3–6 months), naming decision (open question flagged for user), legal/pricing decisions (flagged as open questions).

---

## File 1 — `distro/PRODUCT_SPEC.md`

Full product specification. Use the source doc as the foundation — expand each section with concrete detail. Include:

**Product Identity:**
- Product class: AI Inference Appliance OS — bootable Linux distribution
- Base: Ubuntu 26.04 LTS, HWE kernel
- Business model: Open Core (Apache 2.0 Community, proprietary Enterprise modules)
- Primary claim: "From bare ISO to fully operational multi-GPU AI stack in under 60 minutes"

**Three-tier model** (Community / Professional / Enterprise) with feature matrix table:

| Feature | Community | Professional | Enterprise |
| ------- | --------- | ------------ | ---------- |
| Full stack (all phases) | ✓ | ✓ | ✓ |
| Apache 2.0 license | ✓ | ✓ | — |
| Community support | ✓ | ✓ | ✓ |
| Priority security patches (72hr SLO) | — | ✓ | ✓ |
| Stack compatibility matrix | — | ✓ | ✓ |
| Email support (48hr SLO) | — | ✓ | ✓ |
| Validated upgrade paths | — | ✓ | ✓ |
| FIPS 140-2 kernel profile | — | — | ✓ |
| CIS Benchmark Level 1 hardened defaults | — | — | ✓ |
| LDAP/Active Directory via Authentik | — | — | ✓ |
| Air-gap ISO (offline model registry) | — | — | ✓ |
| Dedicated support engineer | — | — | ✓ |
| Custom SLA (4hr critical) | — | — | ✓ |
| Private build pipeline | — | — | ✓ |

**Technical architecture:** Four layers (Base, Provisioning, Stack, Loadout Manager as systemd service). The Loadout Manager is elevated from a Docker container to a first-class systemd service in the distro — it owns GPU resource allocation at the OS level.

**Phase-to-distro mapping table** — map each of the 14 build plan phases to its distro component. Use the table from the source doc.

**Update architecture:** Quarterly validated stack snapshots (pinned image digests + kernel + driver + CUDA), SHA256-signed manifests, atomic apply with pre-update LVM/Btrfs snapshot, rollback procedure.

---

## File 2 — `distro/FIRST_BOOT_WIZARD.md`

Specification for the interactive first-boot experience. This runs on first login after ISO installation.

**Five-stage wizard:**

### Stage 1 — Hardware Probe
Automatically detect and report:
- GPU count, model, VRAM per GPU
- NVLink bridge topology (`nvidia-smi topo -m`)
- Total system RAM
- NVMe capacity and mount points
- Network interfaces and speeds

Output: a JSON hardware profile written to `/etc/ai-workstation/hardware.json`

```json
{
  "gpus": [
    {"index": 0, "model": "RTX A5500", "vram_gb": 24, "bus": "0000:21:00.0"},
    ...
  ],
  "nvlink_pairs": [[0, 3], [1, 2]],
  "total_vram_gb": 96,
  "ram_gb": 512,
  "nvme_tb": 4.0
}
```

### Stage 2 — Profile Selector
Map detected hardware to recommended loadout profile:

| Hardware | Recommended Profile | Default Compose Config |
| -------- | ------------------- | ---------------------- |
| 1× GPU, <24GB | `inference-small` | Ollama only |
| 2× GPU, NVLink | `inference-pair-a` | Ollama + vLLM TP=2 |
| 4× GPU, 2× NVLink | `inference-pair-a` + `image-studio` | Full stack |
| 4× GPU, full mesh | All profiles | Full stack |

Present options to user: accept recommendation or choose manually.

### Stage 3 — Stack Provisioner
Pull pinned container images for the selected profile. Show progress per image. Estimated times:
- Minimal (inference-small): ~5 min on 1Gbps
- Standard (inference + UI): ~15 min
- Full (all phases): ~30 min

For air-gap ISO: images pre-loaded, no download needed.

### Stage 4 — Network Wizard
Configure:
- Primary interface IP (static recommended: `10.10.10.2/24`)
- Jumpbox/gateway IP
- Optional: WireGuard keypair generation for Phase 01

Write netplan config to `/etc/netplan/99-ai-workstation.yaml`.

### Stage 5 — First-Boot Validation Suite
Run smoke tests against all provisioned services:
- All containers running
- GPU visible in all inference containers
- Ollama responds to `/v1/models`
- Open WebUI HTTP 200
- Loadout Manager `/health` returns GPU data

Print pass/fail report. On failure: offer to re-run provisioner for failed services.

---

## File 3 — `distro/ISO_BUILD_PIPELINE.md`

GitHub Actions pipeline specification for building the ISO. This is a specification + skeleton, not a working implementation.

**Pipeline overview:**
```
Trigger: push to main, or manual with version tag
    │
    ├─ [Job 1] Validate stack manifests
    │    └─ Verify all pinned image digests resolve
    │
    ├─ [Job 2] Build ISO
    │    ├─ ubuntu-image / live-build base
    │    ├─ Apply preseed (autoinstall YAML)
    │    ├─ Post-install hooks:
    │    │   ├─ NVIDIA driver install script
    │    │   ├─ Docker + compose plugin
    │    │   ├─ Loadout Manager systemd service install
    │    │   ├─ First-boot wizard install
    │    │   └─ UFW + auditd baseline
    │    ├─ Optional: pre-pull container images (air-gap variant, +50-80GB)
    │    └─ GPG sign the ISO
    │
    ├─ [Job 3] SHA256 checksum + release artifact upload
    │
    └─ [Job 4] Publish release notes
```

**Key files in the distro repo (skeleton paths):**
```
distro-repo/
├── .github/workflows/build-iso.yml
├── autoinstall/
│   └── user-data.yml        # Ubuntu autoinstall preseed
├── hooks/
│   ├── 01-nvidia.sh         # Driver install
│   ├── 02-docker.sh         # Docker + compose
│   ├── 03-loadout.sh        # Loadout Manager systemd service
│   ├── 04-firstboot.sh      # First-boot wizard
│   └── 05-hardening.sh      # UFW + auditd baseline
├── manifests/
│   └── stack-snapshot.json  # Pinned image digests for this release
└── scripts/
    └── first-boot-wizard.sh
```

**`stack-snapshot.json` format:**
```json
{
  "snapshot": "2026-Q2",
  "ubuntu_version": "26.04",
  "nvidia_driver": "595.71.05",
  "cuda": "13.3",
  "images": {
    "ollama": "ollama/ollama@sha256:abc123...",
    "vllm": "vllm/vllm-openai@sha256:def456...",
    "open-webui": "ghcr.io/open-webui/open-webui@sha256:...",
    "...": "..."
  }
}
```

Every release pins all container images by digest — not by tag. This guarantees reproducibility and enables air-gap installs.

---

## File 4 — `distro/HARDWARE_COMPAT.md`

Hardware compatibility matrix with three tiers.

**Validated Tier** (tested, SLA-backed for Enterprise):

| Class | Models | Notes |
| ----- | ------ | ----- |
| Threadripper Pro WRX80 | 5955WX, 5975WX, 5995WX | This build plan's hardware |
| Threadripper Pro WRX90 | 7970WX, 7980WX | TRX50 platform |
| EPYC Workstation | 9354P, 9554P (single socket) | Genoa platform |
| GPU | A5500, A6000 ada, RTX 4090, H100 PCIe | NVLink-capable preferred |
| NVLink | 2-way bridge, 4-way bridge | Full mesh validated |

**Community Tier** (best-effort, community-reported):
- Intel Xeon W workstations (W3-2400, W5-3400 series)
- Consumer Ryzen / Intel builds with 1–2 GPU configs
- Cloud bare-metal: Hetzner AX162, Lambda A100, CoreWeave

**Not Targeted (v1.0):**
- AMD GPUs — ROCm support deferred to v1.1+
- ARM / Apple Silicon — architecture gap
- Virtual machines — no GPU passthrough support in v1.0
- Multi-node clusters — single-node only in v1.0

**Contributor guidelines section:** how to submit a new hardware report, what data to collect (`nvidia-smi topo -m`, `lspci`, benchmark results), template for compatibility report PRs.

---

## File 5 — `distro/GTM.md`

Go-to-market plan covering the three launch phases.

**Phase 1 — Community Launch:**
- Open GitHub repository under new org (name TBD)
- First public ISO release with checksums and GPG signature
- Documentation site (Docusaurus or MkDocs) — not this project plan, distro-specific
- Announcement channels: HackerNews, Reddit r/LocalLLaMA, r/homelab, Twitter/X
- Goal: 500 GitHub stars, 50 ISO downloads in first month, hardware compat reports from 10+ machines
- Key metric: time-to-first-inference from bare metal (target: <60 min)

**Phase 2 — Professional Tier:**
- Stripe license key integration
- Stack compatibility matrix published behind login wall
- Email support queue (Freshdesk or similar)
- Pricing: $499–$999/node/year (benchmark: Proxmox Enterprise ~€200/node/yr, TrueNAS Enterprise custom)
- Goal: 50 paying Professional customers within 6 months of community launch

**Phase 3 — Enterprise:**
- Direct outreach to MSPs and defense contractors
- Feature set complete: FIPS, LDAP, air-gap ISO, custom SLA
- Design partner program: 3–5 orgs get early access for case study rights
- Sales motion: POC → pilot → site license
- Goal: first enterprise contract within 12 months of community launch

**Open Questions** (flag prominently — these block launch):
- [ ] **Product name** — must be chosen before public launch; domain availability matters; consider: descriptive vs. brandable
- [ ] **Legal entity** — LLC vs. C-Corp; C-Corp if VC is a future path; LLC for bootstrap/revenue focus
- [ ] **Licensing** — Apache 2.0 community core, proprietary Enterprise modules; confirm with counsel before any code is committed under a license
- [ ] **ROCm timeline** — AMD GPU market growing; community pressure likely; plan for v1.1
- [ ] **Pricing validation** — run pricing survey with 20+ target customers before locking; $499–$999/node/yr is a hypothesis
- [ ] **Cloud image roadmap** — same ISO targeting Hetzner AX, Lambda, CoreWeave bare-metal is a natural extension with low incremental effort

---

## Constraints

1. **No executable code in this phase** — all deliverables are documents. The ISO pipeline skeleton is specification text and directory tree diagrams, not working GitHub Actions YAML.

2. **Product name is an open question** — do not invent a name. All documents use the placeholder `[PRODUCT NAME]` where the name would appear.

3. **Pricing in `GTM.md` is a hypothesis** — mark clearly as "suggested starting point, requires validation." Do not present it as decided.

4. **Phase 01 gap affects distro spec** — the distro spec assumes Phase 01 (Caddy + WireGuard) is fully implemented (it IS in scope for the distro, even though it's tabled for the personal workstation). Document this clearly: the distro ships with Caddy + WireGuard as the jumpbox companion service; the personal workstation build tabled it as nice-to-have.

5. **`FIRST_BOOT_WIZARD.md` is a spec, not code** — describe what the wizard does and what data it produces; pseudocode is acceptable for complex logic. The actual wizard implementation is out of scope.

---

## Feedback Template

Write to `/plan/ghc-feedback/phase15-distro-product-spec.md`:

```markdown
# GHC Feedback: Phase 15 — Distro Product Spec
**Brief:** P15-001 | **Status:** Complete / Partial / Blocked

## Files Created
- [ ] distro/PRODUCT_SPEC.md
- [ ] distro/FIRST_BOOT_WIZARD.md
- [ ] distro/ISO_BUILD_PIPELINE.md
- [ ] distro/HARDWARE_COMPAT.md
- [ ] distro/GTM.md

## Deviations from Brief
| Item | Plan | Actual | Reason |

## Notes
```
