# Phase 02 — Host Baseline

**Status: COMPLETE — deployed and validated on 2026-06-04**

**Actual values (deviations from plan were non-breaking):**

| Item | Planned | Actual |
|------|---------|--------|
| Driver | 560 | 595.71.05 |
| CUDA | 12.4 | 13.3 |
| OS | Ubuntu 26.04 | Ubuntu 26.04 |

---

## What Was Deployed

Phase 02 is fully live. This document is a reference for what's installed and how to verify it.

---

## Verify Current State

```bash
ssh kasemo@10.10.10.2

# GPU inventory
nvidia-smi

# Expected: 4× RTX A5500, Driver 595.71.05, CUDA 13.3

# NVLink topology
nvidia-smi topo -m
# Expected: NV4 on GPU0↔GPU3 and GPU1↔GPU2

# NVLink per-GPU link status
nvidia-smi nvlink --status -i 0
nvidia-smi nvlink --status -i 3
# Expected: 4 active links per GPU at 14.062 GB/s

# GPU persistence mode
sudo systemctl status nvidia-persistence.service
# Expected: active (running)

# Docker GPU access
docker run --rm --gpus all nvidia/cuda:13.3.0-base-ubuntu26.04 nvidia-smi
# Expected: all 4 GPUs visible inside container

# CUDA compiler
nvcc --version
# Expected: release 13.3
```

---

## Confirmed System State

```
GPU0: NVIDIA RTX A5500 @ 0000:21:00.0  (NVLink ↔ GPU3)
GPU1: NVIDIA RTX A5500 @ 0000:22:00.0  (NVLink ↔ GPU2)
GPU2: NVIDIA RTX A5500 @ 0000:41:00.0  (NVLink ↔ GPU1)
GPU3: NVIDIA RTX A5500 @ 0000:43:00.0  (NVLink ↔ GPU0)
Total VRAM: 96 GB
```

```
NVLink topology:
        GPU0    GPU1    GPU2    GPU3
GPU0     X      PHB     NODE    NV4
GPU1    PHB      X      NV4     NODE
GPU2    NODE    NV4      X      PHB
GPU3    NV4     NODE    PHB      X
```

---

## Network Interfaces

| Interface | IP | Role |
|-----------|----|------|
| eno1 | 10.10.10.2 | 10GbE — primary (SSH, Docker API, inference) |
| eth0 | 192.168.1.103 | 1GbE — management/console |
| docker0 | 172.17.0.1 | Container bridge |

---

## Key Config Files (On Workstation)

| File | Purpose |
|------|---------|
| `/etc/modprobe.d/blacklist-nouveau.conf` | Nouveau driver blacklist |
| `/etc/docker/daemon.json` | Docker default runtime = nvidia, log rotation |
| `/etc/systemd/system/nvidia-persistence.service` | Persistence mode on boot |
| `~/.bashrc` | CUDA PATH and LD_LIBRARY_PATH exports |

---

## If Re-deploying from Scratch

Phase 02 cannot be run via deploy scripts — it requires console access and a reboot. Follow [plan/steps/02-host-baseline.md](../steps/02-host-baseline.md) manually.

Critical ordering:
1. Blacklist nouveau before installing driver
2. Reboot after driver install before anything else
3. Install NVIDIA Container Toolkit after Docker
4. Configure `/etc/docker/daemon.json` then restart Docker

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| `nvidia-smi` not found | Driver not installed — check `/var/log/apt/history.log` |
| Only some GPUs visible | Check PCIe slot seating; run `lspci \| grep NVIDIA` |
| NVLink shows inactive links | Check physical bridge installation; run `nvidia-smi nvlink --errorcounters -i 0` |
| Docker GPU access fails | Run `nvidia-ctk runtime configure --runtime=docker && systemctl restart docker` |
| Persistence mode not surviving reboot | `systemctl enable nvidia-persistence.service` |
