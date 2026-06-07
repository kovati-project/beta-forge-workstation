# Phase 15 — Linux Distro Product Specification
[← Operations Runbook](14-operations-runbook.md) | [↑ Project Plan](../PROJECT_PLAN.md)

---

## Executive Summary

**Product Name (working):** *TBD — recommend naming before public launch*
**Product Class:** AI Inference Appliance OS — bootable Linux distribution
**Business Model:** Open Core + Enterprise Support
**Base OS:** Ubuntu 26.04 LTS
**Primary Differentiator:** Production-grade, opinionated, multi-GPU AI stack that provisions itself — from bare ISO to fully operational inference, training, and observability platform in under 60 minutes.

This distro is the productized form of the Threadripper AI Workstation build plan. Every phase of that plan (Phases 1–14) becomes either a provisioned default, a first-boot wizard step, or an enterprise configuration option.

---

## Problem Statement

Standing up a serious local AI inference stack currently requires:

- Deep familiarity with NVIDIA driver/CUDA versioning and conflict resolution
- Manual integration of 10–15 independent open-source projects with incompatible release cadences
- Custom observability wiring (DCGM, Prometheus, Grafana)
- Security hardening with no established baseline for this stack
- Loadout/profile management built from scratch
- Typically 6–12 months of iteration before the stack is stable in production

**No commercially supported, bootable product solves this for on-premises multi-GPU hardware.** The gap between cloud-hosted inference APIs and self-managed bare-metal is wide and underserved.

---

## Target Markets

### Tier 1 — Primary (MVP Focus)
- **AI/ML engineering teams at mid-market companies** (50–2,000 employees) who need private inference for IP protection or compliance reasons
- **Managed Service Providers (MSPs)** standing up AI infrastructure for clients — need a repeatable, supportable baseline
- **Defense / Gov contractors** with air-gapped requirements and strict data sovereignty mandates

### Tier 2 — Secondary
- **Research labs and universities** with multi-GPU workstations and no dedicated MLOps staff
- **Healthcare and legal verticals** with strict data residency requirements
- **Serious individual practitioners** (the "prosumer" tier) — open community edition

### Tier 3 — Expansion
- **Cloud bare-metal providers** (Lambda Labs, CoreWeave, Hetzner AX series, OVHcloud) as pre-baked images — same ISO, different deployment target

---

## Product Tiers (Open Core Model)

### Community Edition — Free, Open Source (Apache 2.0)
- Full stack, all features
- Community forum support only
- Self-serve ISO download
- Standard update cadence (quarterly validated stack snapshots)
- No SLA

### Professional Edition — $X/node/year (TBD pricing)
- All Community features
- Priority security patches (72hr SLO)
- Validated upgrade paths with rollback documentation
- Access to stack compatibility matrix (tested GPU/driver/model combinations)
- Email support (48hr response SLO)
- Loadout profile library (curated, tested configurations)

### Enterprise Edition — Custom pricing / site license
- All Professional features
- FIPS 140-2 kernel profile
- CIS Benchmark Level 1 hardened default configuration
- LDAP/Active Directory integration for Authentik
- Air-gap / disconnected installation support (offline model registry mirror)
- Dedicated Slack channel + named support engineer
- Custom SLA (4hr critical, 24hr standard)
- Private build pipeline access (custom ISO with org-specific defaults baked in)
- License: commercial, not open source for enterprise-specific modules

---

## Technical Architecture

### Base Layer
```
Ubuntu 26.04 LTS
├── HWE Kernel (latest stable for newer Threadripper/EPYC support)
├── NVIDIA Driver — auto-selected via ubuntu-drivers based on detected GPU
├── CUDA Toolkit — pinned per validated stack snapshot
├── DKMS — for kernel update driver persistence
└── Minimal base — no desktop environment, no snap services
```

### Provisioning Layer (First Boot)
```
cloud-init / autoinstall
├── Hardware Probe — GPU count, VRAM, NVLink topology detection
├── Profile Selector — maps hardware to recommended loadout profile
├── Stack Provisioner — pulls pinned container images, configures compose
├── Network Wizard — jumpbox IP, WireGuard keypair generation
└── First-Boot Validation Suite — smoke tests all services before handoff
```

### Stack Layer (from Phases 1–14, now pre-integrated)
```
Inference
├── Ollama (text, single-GPU and tensor-parallel modes)
├── vLLM (tensor-parallel, TP=4 full mesh or dual TP=2 pairs)
├── ComfyUI (image generation)
└── InvokeAI (image generation, alternative)

Training
├── Kohya_ss
├── Axolotl
├── Unsloth
└── Label Studio

Agentic
├── n8n
├── Dify / LangFlow
└── MCP sidecar framework

Storage
├── MinIO (S3-compatible object store)
├── Qdrant (vector DB, primary)
└── Weaviate (vector DB, alternative)

UI / Access
├── Open WebUI
├── Continue.dev
└── Loadout Manager (FastAPI — first-class system service, not just a container)

Observability
├── Prometheus + Grafana
├── DCGM Exporter (GPU telemetry)
├── Langfuse (LLM observability)
└── Pre-built dashboards for all services

Auth / Security
├── Authentik (SSO, forward auth)
├── WireGuard (tunnel, jumpbox-side)
├── Nginx/Caddy (reverse proxy, jumpbox-side)
└── UFW + auditd baseline
```

### Loadout Manager (Elevated Role)
In the distro, the Loadout Manager is a **systemd service**, not merely a Docker Compose sidecar. It owns:
- Stack profile activation/deactivation
- GPU resource allocation across services
- VRAM budgeting and conflict prevention
- Health monitoring integration (feeds Prometheus)
- REST API + optional web UI for remote management

### Update Architecture
```
Stack Snapshot (quarterly)
├── Validated combination: Ubuntu kernel + NVIDIA driver + CUDA + all container image digests
├── SHA256-signed manifest
├── Atomic apply via script with automatic pre-update snapshot (LVM or Btrfs)
└── Rollback: revert to prior snapshot manifest, pull pinned images
```
Enterprise tier adds: pre-release access to next snapshot for testing, documented rollback runbook, migration scripts for breaking changes.

---

## ISO Build Pipeline

```
ubuntu-image / live-build
├── Base: ubuntu-server-minimal 26.04 LTS
├── Preseed: autoinstall YAML (LVM, disk layout, users)
├── Post-install hooks:
│   ├── NVIDIA driver installation
│   ├── Docker + compose plugin
│   ├── Stack container image pre-pull (offline install support)
│   ├── Loadout Manager service install
│   ├── First-boot wizard service install
│   └── Hardening baseline (UFW, auditd, sysctl tuning)
├── ISO signing (GPG)
└── CI: GitHub Actions → Artifact storage → checksum-verified release
```

Air-gap ISO variant: pre-pulls all container images into the ISO (significantly larger, ~50–80GB); no outbound internet required post-install.

---

## Hardware Compatibility Targets

### Validated Tier (tested, SLA-backed for Enterprise)
| Class | Example Hardware |
|---|---|
| Threadripper Pro / WRX80 | 5955WX, 5975WX, 5995WX |
| HEDT Threadripper / TRX50 | 7970X, 7980X |
| EPYC workstation | 9354P, 9554P single-socket |
| GPU | NVIDIA A5500, A6000, RTX 4090, H100 PCIe |
| NVLink | 2-way and 4-way bridge configurations |

### Community Tier (tested by community, best-effort)
- Intel Xeon W workstations
- Consumer Ryzen / Intel with 1–2 GPU configs
- Cloud bare-metal (Hetzner AX162, Lambda A100 nodes)

### Not Targeted (v1.0)
- AMD GPUs (ROCm support deferred — CUDA-first for stack compatibility)
- ARM / Apple Silicon
- Virtual machines (no GPU passthrough support in v1.0)

---

## Differentiation vs. Alternatives

| Product | Category | Gap vs. This Distro |
|---|---|---|
| TensorML / RunAI | Enterprise MLOps platform | Kubernetes-native, requires existing infra, expensive |
| Determined AI | ML training platform | Training-focused, not inference-first, no bootable ISO |
| Proxmox | Hypervisor | General-purpose, no AI stack, no GPU provisioning story |
| Plain Ubuntu + manual setup | DIY | 6–12 months of integration work, no support, no validated stack |
| Lambda Stack | NVIDIA driver + frameworks | No orchestration, no observability, no agentic layer |

**This distro is the only bootable, opinionated, multi-GPU AI appliance OS with commercial support.**

---

## Go-to-Market Sketch

### Phase 1 — Community Launch
- Open GitHub repository
- First public ISO release
- Documentation site (distro-specific, beyond this project plan)
- HackerNews / Reddit r/LocalLLaMA launch post
- Goal: community adoption, bug reports, hardware compatibility matrix from the wild

### Phase 2 — Professional Tier
- Stripe-based license key system
- Stack compatibility matrix published behind login
- Email support queue stood up
- Goal: first 50 paying Professional customers, validate pricing

### Phase 3 — Enterprise
- Sales motion: direct outreach to MSPs and defense contractors
- Enterprise feature set complete (FIPS, LDAP, air-gap ISO, custom SLA)
- Case study from early adopter (design partner program)
- Goal: first enterprise contract

---

## Open Questions / Decisions Needed

- [ ] **Product name** — must be chosen before public launch; domain availability matters
- [ ] **Legal entity** — LLC or C-Corp? C-Corp if VC is a future path; LLC for bootstrap
- [ ] **Licensing clarity** — Apache 2.0 for community, proprietary for enterprise modules; confirm with counsel
- [ ] **ROCm timeline** — AMD GPU market is growing; v1.1 or v2.0 priority?
- [ ] **NixOS edition** — revisit after v1.0 ships; architect config schema to be Nix-portable
- [ ] **Pricing** — Professional and Enterprise tiers TBD; comparable: Proxmox Enterprise ~€200/node/yr, TrueNAS Enterprise custom; suggest $499–$999/node/yr Professional as starting point
- [ ] **ARM / cloud image roadmap** — Hetzner, Lambda, CoreWeave bare-metal images are a natural expansion

---

## Relationship to Existing Project Plan

All Phases 1–14 of the Threadripper AI Workstation Build Plan directly map to distro components:

| Build Plan Phase | Distro Component |
|---|---|
| Phase 01 — Jumpbox & Networking | Companion Jumpbox ISO; Caddy + WireGuard pre-configured |
| Phase 02 — Host OS & Driver Baseline | ISO base layer; NVIDIA driver auto-selected; CUDA pinned |
| Phase 03 — Text Inference Stack | Pre-pulled Ollama + vLLM images; NVLink profiles pre-wired |
| Phase 04 — Image Inference Stack | ComfyUI optional install, selectable at first boot |
| Phase 05 — Primary UI (Open WebUI) | Pre-provisioned; RAG, image gen, and voice endpoints pre-configured |
| Phase 06 — Loadout Manager | First-class systemd service (not a container); owns GPU allocation |
| Phase 07 — Training & Fine-Tuning | Optional install, Professional+ tier; Kohya / Axolotl / Unsloth |
| Phase 08 — Agentic Workflows & MCP | Optional install, Professional+ tier; n8n + MCP sidecar framework |
| Phase 09 — Storage, Vector DB & RAG | Pre-provisioned; MinIO / Qdrant / Langfuse defaults |
| Phase 10 — Monitoring & Observability | Pre-wired; DCGM + Grafana dashboards pre-imported |
| Phase 11 — Code Generation | Continue.dev config template; OpenHands optional install |
| Phase 12 — Voice I/O | Whisper + Piper pre-configured; Open WebUI audio endpoints wired |
| Phase 13 — Security Hardening | CIS baseline at install; Authentik SSO pre-configured; UFW + auditd on |
| Phase 14 — Operations Runbook | Distro docs site + systemd service scripts + healthcheck CLI |

---

## Next Steps

1. **Name the product** — revisit with working candidates
2. **Register domain + GitHub org**
3. **Build ISO pipeline** — GitHub Actions, ubuntu-image, first bootable artifact
4. **First-boot wizard** — hardware probe + profile selector MVP
5. **Community site** — docs, download, forum (Discourse)
6. **Design partner outreach** — 3–5 orgs who get early access in exchange for feedback
