# Feedback: P02S2-001 — NVIDIA Driver Installation
**Status:** DONE

---

## What Was Done

- Created `plan/GHC-Plan/phase02-step2-nvidia-drivers.md` (brief)
- Created `configs/drivers/install-nvidia.sh` (driver installation script)
- Created `configs/drivers/nvidia-persistence.service` (systemd unit)
- Created `configs/drivers/verify-drivers.sh` (post-reboot validation)

**Step 1 (Base OS Hardening) was tabled per user instruction.**

---

## Files Created

| File | Purpose |
|------|---------|
| `configs/drivers/install-nvidia.sh` | Installs nouveau blacklist, CUDA keyring repo, nvidia-driver-560, copies persistence service |
| `configs/drivers/nvidia-persistence.service` | Systemd unit enabling `nvidia-smi -pm 1` at boot |
| `configs/drivers/verify-drivers.sh` | Post-reboot checks: driver version, GPU count, NVLink link count, topology, persistence mode |

---

## Deploy Instructions

Copy all three files to the workstation (e.g., via SCP through the jumpbox or USB):

```bash
scp configs/drivers/* user@10.10.10.2:~/drivers/
```

Then on the workstation console:

```bash
cd ~/drivers
chmod +x install-nvidia.sh verify-drivers.sh
bash install-nvidia.sh
# → reboot when prompted
bash verify-drivers.sh
```

---

## Checklist

- [x] `configs/drivers/install-nvidia.sh` exists and is valid bash
- [x] `configs/drivers/nvidia-persistence.service` exists and is a valid systemd unit
- [x] `configs/drivers/verify-drivers.sh` exists and exits 0/1 based on check results
- [x] Feedback written

---

## Constraints Met

- Driver locked to **nvidia-driver-560** ✓
- CUDA keyring URL uses `cuda-keyring_1.1-1_all.deb` from the canonical repo ✓
- CUDA toolkit not installed (reserved for Step 4) ✓
- Docker not installed (reserved for Step 5) ✓
- NVLink pairs GPU0↔GPU3 (pair A) and GPU1↔GPU2 (pair B) encoded in verifier ✓

---

## Notes for Next Step

- No system-specific values need adjustment before running — the script detects state and skips already-done steps.
- `verify-drivers.sh` topology check uses a broad NVLink pattern match since `nvidia-smi topo -m` output formatting can vary by driver version. If the topology check reports false positives, the NVLink link count check (step 5) is the authoritative signal.
- **Step 1 (Base OS Hardening) remains tabled.** Recommend completing it before production use, particularly `unattended-upgrades` configuration.
- Next: **Step 4 — CUDA Toolkit** (`cuda-toolkit-12-4`) and **Step 5 — Docker with NVIDIA Container Runtime**.
