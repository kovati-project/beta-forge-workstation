# Phase 01 — Jumpbox & Networking
[← Project Plan](../PROJECT_PLAN.md) | [Next: Host Baseline →](02-host-baseline.md)

---

## Objective
Establish the only external entry point into the workstation via the jumpbox. All 10GbE traffic routes through here. The 1GbE interface on the workstation remains reserved for BMC/IPMI out-of-band management only.

---

## Architecture

```
Internet / LAN
      │
      ▼
Jumpbox (Ryzen 5800/5600)
  ├── 1GbE  →  LAN / client machines
  ├── 10GbE →  Workstation (AI services)
  └── Caddy (reverse proxy + TLS termination)
        ├── /         → Open WebUI        :3000
        ├── /api/     → Loadout Manager   :8800
        ├── /n8n/     → n8n               :5678
        ├── /grafana/ → Grafana           :3001
        └── /lab/     → JupyterLab        :8888

Workstation (M12SWA-TF)
  ├── 10GbE  →  AI services (all Docker)
  ├── 1GbE   →  BMC/IPMI only (isolated VLAN recommended)
  └── BMC    →  Out-of-band management (separate physical port)
```

---

## Prerequisites
- Jumpbox running Ubuntu 26.04 LTS
- 10GbE NIC confirmed on both jumpbox and workstation
- Physical cable connecting the two machines (direct or via managed switch)
- Static IPs assigned on the 10GbE segment

---

## Step 1 — Configure 10GbE Interface on Jumpbox

```bash
# Identify the 10GbE interface
ip link show
lshw -class network | grep -A5 "10G\|10000"

# Edit netplan config
sudo nano /etc/netplan/01-10gbe.yaml
```

```yaml
network:
  version: 2
  ethernets:
    enp5s0:                    # replace with your 10GbE interface name
      addresses:
        - 10.10.10.1/30        # jumpbox side of the 10GbE link
      mtu: 9000                # enable jumbo frames
      optional: true
```

```bash
sudo netplan apply
ping -M do -s 8972 10.10.10.2  # verify jumbo frames to workstation
```

---

## Step 2 — Configure 10GbE Interface on Workstation

```bash
sudo nano /etc/netplan/01-10gbe.yaml
```

```yaml
network:
  version: 2
  ethernets:
    enp2s0f0:                  # replace with your 10GbE interface name
      addresses:
        - 10.10.10.2/30        # workstation side
      mtu: 9000
      optional: true
```

```bash
sudo netplan apply
# Verify throughput
iperf3 -s &                    # on workstation
iperf3 -c 10.10.10.2 -t 30 -P 4  # on jumpbox — expect 9+ Gbps
```

---

## Step 3 — Install Caddy on Jumpbox

Caddy handles TLS termination (including local CA certs), reverse proxy, and basic auth. No separate cert management needed.

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

---

## Step 4 — Configure Caddy

```bash
sudo nano /etc/caddy/Caddyfile
```

```caddy
# Replace ai.local with your internal hostname or IP
# For internal-only: use a local CA or self-signed via Caddy's PKI

{
    local_certs
    log {
        level INFO
    }
}

ai.local {
    tls internal

    # Basic auth — replace with proper IdP later (Phase 13)
    basicauth /* {
        kasem $2a$14$HASHED_PASSWORD_HERE
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

    # Default: Open WebUI
    handle {
        reverse_proxy 10.10.10.2:3000
    }
}
```

```bash
# Generate basic auth hash
caddy hash-password --plaintext 'your-password-here'
# Paste the output into the Caddyfile above

sudo systemctl enable --now caddy
sudo systemctl status caddy
```

---

## Step 5 — Optional: WireGuard for Remote Access

If you need access from outside the local network:

```bash
sudo apt install wireguard
wg genkey | tee /etc/wireguard/privatekey | wg pubkey > /etc/wireguard/publickey

sudo nano /etc/wireguard/wg0.conf
```

```ini
[Interface]
Address = 10.20.0.1/24
ListenPort = 51820
PrivateKey = <jumpbox-private-key>

[Peer]
# Your remote client
PublicKey = <client-public-key>
AllowedIPs = 10.20.0.2/32
```

```bash
sudo systemctl enable --now wg-quick@wg0
# Open UDP 51820 on your router/firewall
```

---

## Step 6 — BMC / IPMI Lockdown

The workstation 1GbE port and BMC should be on an isolated management VLAN or at minimum not exposed to general LAN.

```bash
# Access BMC web UI (default: DHCP or 192.168.0.x)
# Change default credentials immediately
# Disable IPMI-over-LAN if not needed
# Enable SOL (Serial Over LAN) for headless recovery

# From jumpbox, verify BMC access is only reachable via management network
ipmitool -I lanplus -H <bmc-ip> -U admin -P <password> chassis status
```

---

## Validation Checklist

- [ ] 10GbE link up on both sides, jumbo frames confirmed
- [ ] iperf3 shows 9+ Gbps between jumpbox and workstation
- [ ] Caddy running, serving `https://ai.local` with internal TLS
- [ ] Basic auth protecting all routes
- [ ] Reverse proxy routes confirmed for each backend (will 502 until services start — expected)
- [ ] BMC accessible only from management interface
- [ ] WireGuard tunnel operational (if remote access needed)

---

## Notes
- The workstation should have **no open ports to the general LAN** — all traffic enters via Caddy on the jumpbox
- Add `10.10.10.2 ai.local` to `/etc/hosts` on any client machines
- WebSocket support is automatic in Caddy — required for Open WebUI and JupyterLab
- Revisit auth in Phase 13 to replace basic auth with a proper IdP (Authentik or Authelia)
