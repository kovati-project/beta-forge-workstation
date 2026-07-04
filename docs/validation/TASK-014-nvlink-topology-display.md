# TASK-014 — NVLink topology display

**Issue:** #9
**Result: PASS (with a downstream caveat)** — the component exists, is wired in, and
its bridge pairing matches the hardware. No enhancement request needed.

## The original framing was stale

`NVLinkTopology` is not missing. `ui/src/components/NVLinkTopology.jsx` is a complete
SVG component and is rendered from the **Loadout** page (`ui/src/pages/Loadout.jsx:1,12`),
not the Dashboard — which is why it read as absent.

## Pairing verified against hardware

The component hardcodes its bridge pairs (`NVLinkTopology.jsx:22-23`):

```js
const bridgeA = [gpuMap[0], gpuMap[3]]; // GPU 0 and 3
const bridgeB = [gpuMap[1], gpuMap[2]]; // GPU 1 and 2
```

`nvidia-smi topo -m` on the host:

```
      GPU0  GPU1  GPU2  GPU3
GPU0   X    PHB   NODE  NV4
GPU1  PHB    X    NV4   NODE
GPU2  NODE  NV4    X    PHB
GPU3  NV4   NODE  PHB    X
```

`NV4` (4 NVLink connections) appears exactly between GPU0↔GPU3 and GPU1↔GPU2. The
hardcoded pairing is correct, and it matches the `inference-pair-a` (GPU0+GPU3) and
`inference-pair-b` (GPU1+GPU2) assignments in `profiles.yaml`.

All four GPUs sit on NUMA node 0 with CPU affinity 0-31; the non-bridged paths are
PHB or NODE, as expected for same-node PCIe.

## Caveat — bridges always render idle

Active-bridge highlighting keys off VRAM (`NVLinkTopology.jsx:56-66`):

```js
const activeGpu = bridgeGpus.find((g) => g && g.vram_used_gb > 1);
```

`/status` currently returns `gpus: []` (see #5), so `gpuMap` is empty, every bridge
evaluates as idle, and the component takes its skeleton branch
(`NVLinkTopology.jsx:9`). Bridge A is in fact loaded (~23 GB on GPU0, ~22 GB on GPU3)
and should be drawing as active.

## Verdict

The display itself is correct and needs no work. Its liveness is gated on #5.
