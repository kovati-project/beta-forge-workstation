# Phase 13 — Security Hardening
[← Voice I/O](12-voice-io.md) | [Next: Operations Runbook →](14-operations-runbook.md)

---

## Objective
Harden the full stack for production use: replace basic auth with a proper IdP, enforce mTLS between services where practical, lock down the BMC, segment the network, audit Docker configurations, and establish secrets management.

---

## Threat Model

Given the workstation's role:
- **External perimeter:** Jumpbox is the only ingress; workstation has no direct external exposure
- **Internal threats:** Misconfigured services exposing APIs without auth; over-privileged containers
- **Data risks:** Model weights, training data, and checkpoints are high-value; API keys and credentials in compose files
- **BMC risk:** Out-of-band management port is a full hardware takeover if compromised

---

## Step 1 — Replace Basic Auth with Authentik

Authentik is a self-hosted IdP providing SSO, MFA, OAuth2/OIDC, and LDAP. Replaces Caddy's basic auth with proper identity management.

```bash
# Download Authentik docker-compose
wget -O ~/ai-workstation/docker/compose.auth.yml \
  https://goauthentik.io/docker-compose.yml

# Generate secrets
echo "PG_PASS=$(openssl rand -base64 36 | tr -d '\n')" > .env
echo "AUTHENTIK_SECRET_KEY=$(openssl rand -base64 60 | tr -d '\n')" >> .env

docker compose -f ~/ai-workstation/docker/compose.auth.yml \
  --env-file .env up -d

# Access at http://10.10.10.2:9000/if/flow/initial-setup/
# Create admin account, then configure:
```

**Configure Authentik applications:**
1. Applications → Create → Open WebUI
   - Launch URL: `https://ai.local`
   - Provider: OAuth2/OIDC
2. Repeat for Grafana, n8n, JupyterLab, Loadout Manager
3. Create groups: `admins`, `users`, `readonly`
4. Enable MFA: TOTP required for admin group

**Update Caddy to use Authentik forward auth:**

```caddy
ai.local {
    tls internal

    # Forward auth to Authentik
    forward_auth authentik:9000 {
        uri /outpost.goauthentik.io/auth/caddy
        copy_headers X-Authentik-Username X-Authentik-Groups X-Authentik-Email
        trusted_proxies private_ranges
    }

    handle /webui/* {
        uri strip_prefix /webui
        reverse_proxy 10.10.10.2:3000
    }
    # ... rest of routes
}
```

---

## Step 2 — Secrets Management

Replace all hardcoded credentials in compose files with Docker secrets or a vault:

```bash
# Option A: Docker secrets (simplest)
echo "changeme-strong-password" | docker secret create minio_password -
echo "change-this-secret" | docker secret create webui_secret_key -
echo "change-this-random-key" | docker secret create n8n_encryption_key -

# Reference in compose files:
# environment:
#   - MINIO_ROOT_PASSWORD_FILE=/run/secrets/minio_password
# secrets:
#   - minio_password

# Option B: HashiCorp Vault (more complex, more powerful)
docker run -d \
  --name vault \
  --cap-add=IPC_LOCK \
  -p 8200:8200 \
  -e 'VAULT_DEV_ROOT_TOKEN_ID=root-token' \
  hashicorp/vault:latest

# Access at http://10.10.10.2:8200
# Store all service credentials, API keys, and tokens here
# Applications retrieve secrets at runtime via Vault API
```

---

## Step 3 — Network Segmentation

```bash
# Create isolated Docker networks per service tier
docker network create --driver bridge ai-inference    # inference services
docker network create --driver bridge ai-training     # training services
docker network create --driver bridge ai-storage      # storage services
docker network create --driver bridge ai-monitoring   # metrics services
docker network create --driver bridge ai-agents       # agentic services

# Rule: services only on networks they need
# e.g., Label Studio only on ai-training
#       Grafana on ai-monitoring (read access to other nets)
#       Open WebUI on ai-inference + ai-storage (needs both)
```

Update compose files to assign networks:

```yaml
services:
  open-webui:
    networks:
      - ai-inference
      - ai-storage
  
  ollama:
    networks:
      - ai-inference

  qdrant:
    networks:
      - ai-storage

networks:
  ai-inference:
    external: true
  ai-storage:
    external: true
```

---

## Step 4 — Docker Security Hardening

Audit all compose files for these issues:

```bash
# Run Docker Bench Security
docker run --rm --net host --pid host --userns host --cap-add audit_control \
  -e DOCKER_CONTENT_TRUST=$DOCKER_CONTENT_TRUST \
  -v /etc:/etc:ro \
  -v /usr/bin/containerd:/usr/bin/containerd:ro \
  -v /usr/bin/runc:/usr/bin/runc:ro \
  -v /usr/lib/systemd:/usr/lib/systemd:ro \
  -v /var/lib:/var/lib:ro \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  --label docker_bench_security \
  docker/docker-bench-security
```

**Fix list — apply to all compose files:**

```yaml
services:
  my-service:
    # Drop all capabilities, add only what's needed
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE    # only if binding to port <1024
    
    # Read-only root filesystem where possible
    read_only: true
    tmpfs:
      - /tmp
    
    # No privilege escalation
    security_opt:
      - no-new-privileges:true
    
    # Non-root user
    user: "1000:1000"
    
    # Resource limits
    mem_limit: 8g
    cpus: 4.0
```

**Exceptions (require elevated privileges):**
- DCGM exporter: needs `SYS_ADMIN`
- Loadout Manager: needs Docker socket
- OpenHands: needs Docker socket for sandboxes
- cAdvisor: needs `privileged: true`

Document each exception explicitly in compose comments.

---

## Step 5 — BMC Hardening (M12SWA-TF IPMI)

```bash
# Access BMC web UI at its management IP
# Supermicro default: admin / admin  ← change immediately

# Via ipmitool from jumpbox:
ipmitool -I lanplus -H <bmc-ip> -U admin -P admin user set password 1 <new-password>

# Disable IPMI cipher suite 0 (no-auth vulnerability)
ipmitool -I lanplus -H <bmc-ip> -U admin -P <password> \
  raw 0x06 0x40 0x01 0x01 0x00

# Enable only specific cipher suites (17 = AES-128-CBC with HMAC-SHA256)
# Disable unused BMC services in web UI:
#   - Disable Telnet
#   - Disable IKVM if not needed
#   - Enable only HTTPS for web UI (disable HTTP)
#   - Restrict IPMI LAN access to management VLAN IP range

# Set BMC to log all authentication events
ipmitool -I lanplus -H <bmc-ip> -U admin -P <password> \
  sel clear    # start fresh
```

**Network isolation for BMC:**
- BMC/IPMI port should be on a dedicated management VLAN
- Only the jumpbox (or a dedicated management host) should route to the BMC network
- Never expose BMC to the general LAN or internet

---

## Step 6 — Host Firewall

```bash
# UFW on workstation
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow from jumpbox only (10.10.10.1)
sudo ufw allow from 10.10.10.1 to any port 3000  # Open WebUI
sudo ufw allow from 10.10.10.1 to any port 8800  # Loadout Manager
sudo ufw allow from 10.10.10.1 to any port 11434 # Ollama
sudo ufw allow from 10.10.10.1 to any port 8000  # vLLM pair A
sudo ufw allow from 10.10.10.1 to any port 8001  # vLLM pair B
sudo ufw allow from 10.10.10.1 to any port 8002  # vLLM 4GPU
sudo ufw allow from 10.10.10.1 to any port 8188  # ComfyUI
sudo ufw allow from 10.10.10.1 to any port 5678  # n8n
sudo ufw allow from 10.10.10.1 to any port 3001  # Grafana
sudo ufw allow from 10.10.10.1 to any port 8888  # JupyterLab

# Management VLAN for BMC
sudo ufw allow from <mgmt-vlan-cidr> to any port 22  # SSH

# Enable
sudo ufw enable
sudo ufw status verbose
```

---

## Step 7 — Audit Logging

```bash
# Enable Docker daemon logging
sudo tee -a /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "5",
    "labels": "service,version"
  }
}
EOF

# Enable auditd for system-level events
sudo apt install -y auditd
sudo auditctl -w /var/run/docker.sock -p rwa -k docker_socket
sudo auditctl -w /data/models -p r -k model_access
sudo auditctl -w /etc/docker -p rwa -k docker_config

# Forward logs to a SIEM if available (Graylog, Splunk, Elastic)
# For local audit: ausearch -k docker_socket
```

---

## Step 8 — TLS for Internal Services

Even within the internal network, encrypt service-to-service traffic:

```bash
# Generate local CA and certs with Caddy PKI
# Caddy automatically creates a local CA when `tls internal` is used
# Export the CA cert for clients:
caddy trust

# For Docker inter-service TLS (optional, higher security):
# Use Caddy as a local CA, issue certs to each service,
# configure mutual TLS between high-value service pairs
# (e.g., Loadout Manager ↔ Docker daemon)
```

---

## Validation Checklist

- [ ] Authentik running, SSO working for Open WebUI
- [ ] MFA enforced for admin accounts
- [ ] All hardcoded passwords removed from compose files, replaced with secrets
- [ ] Docker Bench Security score improved (address all HIGH findings)
- [ ] Network segmentation applied — services only on their required networks
- [ ] BMC password changed from default, HTTP disabled, cipher 0 disabled
- [ ] Host UFW enabled, only jumpbox IP can reach service ports
- [ ] Auditd logging Docker socket access
- [ ] No service running as root unless explicitly documented
- [ ] `docker ps --format "{{.Names}}: {{.Status}}"` — all services healthy

---

## Notes
- Security is a process, not a state — revisit this phase quarterly
- The Docker socket mounts on Loadout Manager and OpenHands are inherently privileged; accept this risk consciously or implement a Docker socket proxy (Tecnativa/docker-socket-proxy) to restrict allowed API calls
- Authentik's forward auth adds ~5-10ms per request — negligible for this workload
- Keep the BMC on a completely separate physical network segment if possible; if your managed switch supports it, put the BMC port in its own VLAN with no routing to the AI service network
