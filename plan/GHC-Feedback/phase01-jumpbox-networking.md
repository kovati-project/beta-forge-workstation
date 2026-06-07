# Feedback: P01-001 — Jumpbox & Networking
**Status:** TABLED (nice to have)  
**Date:** 2026-06-04

---

## Current State

The 10GbE link between jumpbox (10.10.10.1) and workstation (10.10.10.2) is **operational** — Phase 02 was completed successfully over this link, confirming basic connectivity works.

Direct SSH access to the workstation (`ssh kasemo@10.10.10.2`) is the current working access pattern.

---

## What Is Tabled

| Item | Status | Notes |
|------|--------|-------|
| Netplan config files | Tabled | 10GbE link already working; formal netplan config not required now |
| Caddy reverse proxy | Tabled | No external reverse proxy in place; services accessed directly by port |
| WireGuard VPN | Tabled | Remote access not currently required |
| Jumbo frames validation | Tabled | Link functional; MTU 9000 not yet verified |
| `scripts/deploy-jumpbox-network.sh` | Tabled | No deploy needed while access is direct |
| `scripts/validate-phase01.sh` | Tabled | Manual SSH sufficient for now |

---

## Why Tabled

Access pattern is direct SSH on the local network. The formal jumpbox/proxy layer (Caddy, WireGuard, subdomain routing) adds security and remote-access value but is not blocking any Phase 03–12 work. The workstation is not internet-exposed.

Phase 13 (Security Hardening) is the natural home for formalizing the network perimeter. The Caddy config from the Phase 01 brief can be picked up then.

---

## Recommendation

Revisit before any of the following:
- Exposing services to devices outside the local network
- Adding team members who need access
- Beginning Phase 13 (Security Hardening)
