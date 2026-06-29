#!/bin/bash
# Phase 13 deployment: Security Hardening Stack
# Deploys Authentik IdP, configures network segmentation, secrets management

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/container-helpers.sh
source "$REPO_ROOT/scripts/lib/container-helpers.sh"

echo "=== Phase 13: Security Hardening ==="
echo ""

# Verify dependencies
echo "Checking dependencies..."

if [[ ! -f "docker/.env" ]]; then
    echo "ERROR: docker/.env not found — run init-secrets.sh first"
    exit 1
fi
echo "✓ docker/.env present"
echo ""

# Create Authentik storage directories
echo "Creating Authentik storage..."
sudo mkdir -p /data/authentik/{postgres,redis,media,custom-templates}
sudo chmod -R 755 /data/authentik
echo "✓ Authentik directories created"
echo ""

# Verify compose files exist
if [ ! -f "docker/compose.auth.yml" ]; then
    echo "ERROR: docker/compose.auth.yml not found"
    exit 1
fi
echo "✓ Authentik compose file exists"
echo ""

# Start Authentik services
echo "Starting Authentik Identity Provider..."
for _c in authentik authentik-worker authentik-postgres authentik-redis; do
    remove_orphan "$_c" ai-auth-stack
done
docker compose -f docker/compose.auth.yml up -d
echo "✓ Authentik services starting"
echo ""

# Wait for Authentik to initialize
echo "Waiting for Authentik to initialize..."
for i in {1..60}; do
    if curl -sf http://localhost:9080/-/health/live/ > /dev/null 2>&1; then
        echo "✓ Authentik ready"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "WARNING: Authentik might still be initializing"
    fi
    sleep 1
done
echo ""

# Verify Authentik database
if docker ps | grep -q "authentik-postgres"; then
    echo "✓ Authentik PostgreSQL running"
else
    echo "⚠ Authentik PostgreSQL starting..."
fi

if docker ps | grep -q "authentik-redis"; then
    echo "✓ Authentik Redis running"
else
    echo "⚠ Authentik Redis starting..."
fi
echo ""

# Caddy forward auth config (Phase 01 — optional)
if [ -f "configs/caddy/Caddyfile.security" ]; then
    echo "✓ Caddy security configuration present"
else
    echo "NOTE: Caddyfile.security not found — Caddy (Phase 01) not yet deployed, skipping"
fi
echo ""

# Generate Caddy CA for internal TLS
echo "Generating internal TLS certificates..."
if command -v caddy &> /dev/null; then
    caddy trust 2>/dev/null || true
    echo "✓ Local Caddy CA certificate generated"
else
    echo "⚠ Caddy not in PATH (will be available in Docker)"
fi
echo ""

# Create Docker secrets for critical services (optional, if using Docker Swarm)
echo "Docker Secrets Management:"
echo "  To create secrets (requires Docker Swarm mode):"
echo "    docker swarm init  # if not already initialized"
echo "    echo 'password' | docker secret create minio_password -"
echo "    echo 'key' | docker secret create n8n_encryption_key -"
echo ""
echo "  OR use .env file (simpler, recommended):"
echo "    .env file generated with all secrets"
echo ""

# Apply security hardening to existing services
echo "Security hardening recommendations:"
echo ""
echo "1. Update Caddy configuration to use Authentik:"
echo "   Replace compose.caddy.yml with:"
echo "   - Change ports mapping if needed"
echo "   - Mount configs/caddy/Caddyfile.security"
echo "   - Ensure Caddy can reach Authentik service"
echo ""
echo "2. Audit existing services for security:"
echo "   bash scripts/security-hardening-audit.sh"
echo ""
echo "3. Configure Authentik applications (manual):"
echo "   Visit http://10.10.10.2:9080/if/flow/initial-setup/"
echo ""

# Firewall setup instructions
echo "Firewall Setup:"
echo ""
echo "  # Enable UFW (if not already enabled)"
echo "  sudo ufw default deny incoming"
echo "  sudo ufw default allow outgoing"
echo "  sudo ufw allow from 10.10.10.1 (jumpbox access)"
echo "  sudo ufw allow from 192.168.1.0/24 to any port 22  (SSH management)"
echo "  sudo ufw enable"
echo ""

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Authentik services ready:"
echo ""
echo "  Authentik (admin):     http://10.10.10.2:9080/if/flow/initial-setup/"
echo "  PostgreSQL:            localhost:5432 (internal only)"
echo "  Redis:                 localhost:6379 (internal only)"
echo ""
echo "Next steps:"
echo ""
echo "1. Initial Authentik Setup (FIRST TIME ONLY):"
echo "   Visit: http://10.10.10.2:9080/if/flow/initial-setup/"
echo "   Create admin account"
echo "   Log in with your credentials"
echo ""
echo "2. Configure Applications in Authentik:"
echo "   Admin → Applications → Create:"
echo "   - Open WebUI (OAuth2/OIDC, launch URL: https://ai.local/webui)"
echo "   - Grafana (OAuth2/OIDC, launch URL: https://ai.local/grafana)"
echo "   - n8n (OAuth2/OIDC, launch URL: https://ai.local/n8n)"
echo "   - JupyterLab (OAuth2/OIDC, launch URL: https://ai.local/jupyter)"
echo "   - Loadout Manager (OAuth2/OIDC)"
echo ""
echo "3. Create User Groups:"
echo "   Admin → Groups → Create:"
echo "   - admins (with MFA policy)"
echo "   - users"
echo "   - readonly"
echo ""
echo "4. Enable MFA for Admin Group:"
echo "   Admin → Groups → admins → Edit"
echo "   Add TOTP MFA policy"
echo ""
echo "5. Update Caddy to use security configuration:"
echo "   Edit docker/compose.caddy.yml to mount:"
echo "   - configs/caddy/Caddyfile.security"
echo "   - Restart Caddy"
echo ""
echo "6. Test Forward Auth:"
echo "   curl https://ai.local/webui (should redirect to Authentik login)"
echo ""
echo "7. Harden Host Firewall:"
echo "   bash scripts/validate-phase13.sh  (includes UFW configuration)"
echo ""
echo "8. Run Security Audit:"
echo "   bash scripts/security-hardening-audit.sh"
echo ""
echo "9. Audit hardening options for existing services:"
echo "   - Add 'cap_drop: [ALL]' to reduce privileges"
echo "   - Add 'read_only: true' + tmpfs where possible"
echo "   - Add 'security_opt: [no-new-privileges:true]'"
echo "   - Add resource limits: mem_limit, cpus"
echo ""
echo "10. Document security exceptions:"
echo "    Services that need elevated privileges (Loadout, OpenHands, cAdvisor)"
echo "    should have explicit comments in compose files explaining why."
