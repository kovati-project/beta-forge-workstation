# Runbook: enable the host firewall (UFW)

**Script:** `scripts/setup-ufw.sh`  
**Tracks:** TASK-071 / issue #33 (UFW was never enabled; every listening port was reachable from the LAN)  
**Applies to:** the workstation host (`adapress`), run as root

## Read first

1. **Docker bypasses UFW.** Ports published by Docker (`ports: "3000:8080"`) are
   DNAT'd and traverse `FORWARD`/`DOCKER-USER`, not UFW's `INPUT` rules. Almost
   every service on this host is a container. Plain `ufw allow` / `ufw deny` rules
   do **not** restrict them. Use `--docker-user` (below) or the exposure remains.
2. **There is no default management network.** You must say where you administer
   the host from. The `10.10.10.0/24` network in older docs does not exist on this
   host (it is on `192.168.1.0/24`, see TASK-070).
3. **The script has not been run against the live workstation** (it was developed
   and tested offline against stubs). Treat the first `--apply` as a change window:
   keep a second SSH session and, if possible, console/BMC access open.

## Prerequisites

- `ufw` installed (`sudo apt install ufw`); the script will not install it.
- You know the source CIDR(s) you manage the host from, e.g. `192.168.1.0/24` or a
  single admin host `192.168.1.50`.
- If you run over SSH, run from a host **inside** those CIDRs. The script prints
  your client IP and refuses `--apply` if it is outside (override:
  `--allow-client-outside-mgmt`).

## Procedure

```bash
# 0. Read-only snapshot of the current state
sudo scripts/setup-ufw.sh --status

# 1. Dry run (default). Prints every ufw command; changes nothing; no root needed.
scripts/setup-ufw.sh --allow-from 192.168.1.0/24 --docker-user

# 2. Review: management CIDRs, detected SSH port, the port list, the
#    DOCKER-USER block. Edit PORT_TABLE in the script if a port is wrong.

# 3. Apply (second SSH session open!)
sudo scripts/setup-ufw.sh --allow-from 192.168.1.0/24 --docker-user --apply

# 4. Verify
sudo ufw status verbose
sudo iptables -S DOCKER-USER
sudo iptables -S ufw-mgmt-docker
sudo scripts/setup-ufw.sh --status
```

Multiple networks: repeat `--allow-from`, or `UFW_MGMT_CIDRS=192.168.1.0/24,192.168.2.50`.

### What `--apply` does, in order

1. Allows SSH (port detected from the session, `sshd -T`, config files and live
   listeners; fallback 22) from each management CIDR, **then confirms the rule is
   present and stops if it cannot**.
2. Allows the Docker bridge subnets (`172.16.0.0/12`, override with
   `UFW_DOCKER_SUBNETS`, disable with `--no-docker-subnets`) so containers can
   still reach host-published ports through the host IP (Caddy, Prometheus, Open
   WebUI to Ollama, ...). Without this those paths break under default-deny.
3. Allows each service port in `PORT_TABLE` from the management CIDRs.
4. `ufw default deny incoming` / `ufw default allow outgoing`.
5. With `--docker-user`: backs up `/etc/ufw/after.rules` to
   `after.rules.bak-<timestamp>` and adds/replaces a delimited block
   (`# BEGIN/END BETA-WORKSTATION UFW-DOCKER`) that hooks `DOCKER-USER`. New
   connections to published ports are dropped unless they come from a management
   CIDR or a Docker subnet, matched on the host port (`--ctorigdstport`).
6. `ufw --force enable` (or `ufw reload` if already active and the block changed).

Re-running is safe: existing rules are skipped and the after.rules block is
replaced in place (no backup is taken when nothing changes).

### Editing the port list

`PORT_TABLE` at the top of `scripts/setup-ufw.sh`: one line per service,
`GROUP PORT PROTO SCOPE LABEL`. Commented lines are off by default (PostgreSQL,
exporters, MCP servers, SearXNG): containers still reach them via the Docker-subnet
rule, the LAN cannot. Port 5201 was seen listening in TASK-071 but is defined in no
compose file here; identify it before allowing it. After editing, re-run with
`--apply`; rules for entries you removed are **not** deleted automatically
(`sudo ufw status numbered`, then `sudo ufw delete <n>`; they carry the comment
`beta-ws: <label>`).

## Verify from outside

From a machine **outside** the management CIDRs:

```bash
curl --max-time 5 http://<workstation-ip>:3000/   # must time out
```

From a machine inside them it must answer. Also check a container-to-host path
that previously worked (e.g. Open WebUI reaching Ollama) and the Prometheus targets.

## Rollback

Fastest, restores the pre-change posture (UFW off; the DOCKER-USER block is only
loaded while UFW is enabled):

```bash
sudo ufw disable
# If published ports still seem blocked, check for a leftover jump and clear it
# (an empty DOCKER-USER chain simply returns, Docker keeps working):
sudo iptables -S DOCKER-USER
sudo iptables -F DOCKER-USER
```

Remove only the Docker block (keep UFW on for host processes):

```bash
ls /etc/ufw/after.rules.bak-*
sudo cp -p /etc/ufw/after.rules.bak-<timestamp> /etc/ufw/after.rules   # restore backup
# or strip just the managed block:
sudo sed -i '/^# BEGIN BETA-WORKSTATION UFW-DOCKER/,/^# END BETA-WORKSTATION UFW-DOCKER/d' /etc/ufw/after.rules
sudo ufw reload
sudo iptables -S DOCKER-USER      # duplicates of the jump are harmless; a Docker restart clears them
```

Remove all rules and reset to defaults (destructive; UFW is left disabled):

```bash
sudo ufw --force reset
```

If locked out of SSH: use the console/BMC, then `sudo ufw disable`.

## Known limits / not verified

- IPv4 only. Docker does not publish IPv6 by default and the DOCKER-USER block does
  not touch `ip6tables`.
- The DOCKER-USER block follows the ufw-docker pattern but was **not exercised
  against a live Docker + UFW stack**. After `ufw reload` the jump into
  `ufw-mgmt-docker` may appear more than once in `DOCKER-USER`; this is harmless.
  The script syntax-checks the block with `iptables-restore --test` before writing it.
- Docker custom `default-address-pools` outside `172.16.0.0/12` (e.g. `10.x`,
  `192.168.x`) need `UFW_DOCKER_SUBNETS` set accordingly, or container-to-host
  traffic will be blocked.
- Allowing the Docker subnets lets any container reach any host port, including SSH.
  Containers are already trusted on this host (several mount the Docker socket),
  so this is a conscious trade-off rather than a new exposure; use
  `--no-docker-subnets` and per-port rules if you want it tighter.
- **SSH password authentication is still enabled** (TASK-071). It is out of scope
  here; restricting SSH to the management CIDRs narrows who can try, it does not
  replace key-only auth.
- BMC/IPMI hardening, Authentik/Caddy fixes (#50) and the `10.10.10.2`
  replacement (#51) are separate work.
