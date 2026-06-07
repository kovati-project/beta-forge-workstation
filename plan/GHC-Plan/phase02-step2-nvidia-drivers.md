# GHC Task: Phase 02 – Step 2 — NVIDIA Driver Installation
**Brief ID:** P02S2-001
**Source doc:** `/plan/steps/02-host-baseline.md` (Step 2 + Step 3)
**Write feedback to:** `/plan/ghc-feedback/phase02-step2-nvidia-drivers.md`

---

## Context

Phase 02 builds the host driver baseline on the Ubuntu 26.04 workstation (10.10.10.2).
**Step 1 (Base OS Hardening) is tabled** — assume a stock Ubuntu 26.04 LTS Server install with
physical/BMC console access and the 10GbE link from Phase 01 in place.

This brief covers:
- **Step 2:** NVIDIA driver installation (driver-560, nouveau blacklist, CUDA repo)
- **Step 3:** GPU persistence mode as a systemd service

Do not assume SSH or interactive access — output deploy-ready files only.

Hardware target:
- 4× NVIDIA RTX A5500 (24 GB each, 96 GB total)
- NVLink pairs: GPU0↔GPU3 (pair A), GPU1↔GPU2 (pair B)
- Driver target: nvidia-driver-560 (minimum for full A5500 NVLink under CUDA 12.4)

---

## Your Job

Create the following files exactly as specified.

---

### 1. `configs/drivers/install-nvidia.sh`

Shell script to run as the local user (with sudo) on the workstation.
Covers nouveau blacklist, CUDA keyring repo, driver install, and reboot prompt.
Must be idempotent — safe to re-run.

### 2. `configs/drivers/nvidia-persistence.service`

Systemd unit file for GPU persistence mode.
Enable with: `sudo systemctl enable --now nvidia-persistence.service`

### 3. `configs/drivers/verify-drivers.sh`

Post-reboot verification script.
Checks: driver version, 4 GPUs visible, NVLink link count per GPU, topo matrix.
Exits 0 on pass, 1 on any failure.

---

## Constraints

- Driver version: **nvidia-driver-560** (do not use a different version)
- CUDA keyring package: `cuda-keyring_1.1-1_all.deb`
- CUDA repo URL: `https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2604/x86_64/`
- Do not install CUDA toolkit in this step (that is Step 4)
- Do not install Docker in this step (that is Step 5)
- NVLink threshold for validation: 4 active links per GPU at 14.062 GB/s

---

## Done When

- [ ] `configs/drivers/install-nvidia.sh` exists and is valid bash
- [ ] `configs/drivers/nvidia-persistence.service` exists and is a valid systemd unit
- [ ] `configs/drivers/verify-drivers.sh` exists and exits 0/1 correctly
- [ ] Feedback written to `/plan/ghc-feedback/phase02-step2-nvidia-drivers.md`

---

## Return

Report:
- Files created
- Any constraints that were ambiguous
- Anything the user must manually adjust before running (e.g., if the script has hardcoded values that depend on the live system)
