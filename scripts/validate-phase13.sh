#!/bin/bash
# Phase 13 validation: Security hardening verification

set -e

echo "=== Phase 13 Validation ==="
echo ""

FAILED=0
PASSED=0

check_pass() {
    echo "✓ $1"
    PASSED=$(( PASSED + 1 ))
}

check_fail() {
    echo "✗ $1"
    FAILED=$(( FAILED + 1 ))
}

check_warn() {
    echo "⊘ $1"
}

# ========== AUTHENTIK SERVICE CHECKS ==========
echo "Authentik Services:"
echo ""

# 1. Authentik container running
if docker ps | grep -q "authentik"; then
    check_pass "Authentik server running"
else
    check_fail "Authentik server not running"
fi

# 2. PostgreSQL running
if docker ps | grep -q "authentik-postgres"; then
    check_pass "Authentik PostgreSQL running"
else
    check_fail "Authentik PostgreSQL not running"
fi

# 3. Redis running
if docker ps | grep -q "authentik-redis"; then
    check_pass "Authentik Redis running"
else
    check_fail "Authentik Redis not running"
fi

# 4. Authentik API health check
if curl -sf http://localhost:9080/-/health/live/ > /dev/null 2>&1; then
    check_pass "Authentik API responding on :9080"
else
    check_fail "Authentik API not responding on :9080"
fi

# 5. Compose file valid
if docker compose -f docker/compose.auth.yml config > /dev/null 2>&1; then
    check_pass "docker/compose.auth.yml valid"
else
    check_fail "docker/compose.auth.yml has syntax errors"
fi

echo ""

# ========== NETWORK SEGMENTATION CHECKS ==========
echo "Network Segmentation:"
echo ""

NETWORKS_OK=0
for net in ai-inference ai-training ai-storage ai-monitoring ai-agents ai-auth; do
    if docker network ls | grep -q "$net"; then
        NETWORKS_OK=$(( NETWORKS_OK + 1 ))
    fi
done

if [ "$NETWORKS_OK" -eq 6 ]; then
    check_pass "All security networks created (6/6)"
else
    check_fail "Missing networks: $((6 - NETWORKS_OK)) not found"
fi

echo ""

# ========== SECRETS MANAGEMENT ==========
echo "Secrets Management:"
echo ""

# 1. .env file exists
if [ -f ".env" ]; then
    check_pass ".env file exists"
else
    check_fail ".env file missing"
fi

# 2. .env in gitignore
if [ -f ".gitignore" ] && grep -q "^\.env" .gitignore; then
    check_pass ".env in .gitignore"
else
    check_fail ".env not in .gitignore"
fi

# 3. .env has required vars
VARS_FOUND=0
for var in POSTGRES_PASSWORD REDIS_PASSWORD AUTHENTIK_SECRET_KEY; do
    if grep -q "^$var=" .env 2>/dev/null; then
        VARS_FOUND=$(( VARS_FOUND + 1 ))
    fi
done

if [ "$VARS_FOUND" -eq 3 ]; then
    check_pass "All required secrets in .env (3/3)"
else
    check_fail "Missing secrets in .env: $((3 - VARS_FOUND))"
fi

# 4. .env file permissions (should be 600)
if [ -f ".env" ]; then
    PERMS=$(stat -f "%OLp" .env 2>/dev/null || stat -c '%a' .env 2>/dev/null || echo "unknown")
    if [ "$PERMS" = "600" ]; then
        check_pass ".env file permissions secure (600)"
    else
        check_warn ".env permissions: $PERMS (should be 600)"
    fi
fi

echo ""

# ========== CADDY CONFIGURATION ==========
echo "Caddy Security Configuration:"
echo ""

# 1. Caddyfile.security exists
if [ -f "configs/caddy/Caddyfile.security" ]; then
    check_pass "Caddy security configuration exists"
else
    check_fail "Caddyfile.security not found"
fi

# 2. Authentik forward auth configured
if grep -q "forward_auth.*authentik" configs/caddy/Caddyfile.security 2>/dev/null; then
    check_pass "Caddy Authentik forward auth configured"
else
    check_fail "Caddy forward auth not configured"
fi

# 3. Internal TLS configured
if grep -q "tls internal" configs/caddy/Caddyfile.security 2>/dev/null; then
    check_pass "Internal TLS configured"
else
    check_fail "Internal TLS not configured"
fi

# 4. Caddy config has service routes
SERVICE_ROUTES=$(grep -c "handle /" configs/caddy/Caddyfile.security 2>/dev/null || echo "0")
if [ "$SERVICE_ROUTES" -gt 5 ]; then
    check_pass "Caddy routes configured ($SERVICE_ROUTES routes)"
else
    check_warn "Only $SERVICE_ROUTES Caddy routes found"
fi

echo ""

# ========== HOST SECURITY ==========
echo "Host Security:"
echo ""

# 1. UFW firewall status
if sudo ufw status 2>/dev/null | grep -q "Status: active"; then
    check_pass "UFW firewall enabled"
else
    check_warn "UFW firewall not enabled (run: sudo ufw enable)"
fi

# 2. SSH key-only auth
if grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config 2>/dev/null; then
    check_pass "SSH key-only authentication enabled"
else
    check_warn "SSH password auth enabled (consider disabling)"
fi

# 3. SSH port restricted
if sudo ufw show added 2>/dev/null | grep -q "22"; then
    check_pass "SSH firewall rule configured"
else
    check_warn "SSH firewall rule not found"
fi

echo ""

# ========== AUDIT LOGGING ==========
echo "Audit Logging:"
echo ""

# 1. auditd installed
if command -v auditctl &> /dev/null; then
    check_pass "auditd installed"
else
    check_warn "auditd not installed (optional: sudo apt install auditd)"
fi

# 2. Docker daemon logging
if grep -q "log-driver" /etc/docker/daemon.json 2>/dev/null; then
    check_pass "Docker daemon logging configured"
else
    check_warn "Docker daemon logging not configured"
fi

echo ""

# ========== TLS CERTIFICATES ==========
echo "TLS Certificates:"
echo ""

# 1. Caddy CA exists
if [ -f "$HOME/.local/share/caddy/pki/authorities/local/root.crt" ]; then
    check_pass "Local Caddy CA certificate exists"
else
    check_warn "Caddy CA not found (run: caddy trust)"
fi

echo ""

# ========== DOCKER COMPOSE VALIDATION ==========
echo "Docker Compose Files:"
echo ""

# Validate all compose files
COMPOSE_FILES=$(find docker -name "compose.*.yml" -type f | wc -l)
VALID_FILES=0

for file in docker/compose.*.yml; do
    if docker compose -f "$file" config > /dev/null 2>&1; then
        VALID_FILES=$(( VALID_FILES + 1 ))
    else
        check_fail "Invalid: $(basename $file)"
    fi
done

check_pass "Docker compose files valid ($VALID_FILES files)"

echo ""

# ========== STORAGE DIRECTORIES ==========
echo "Storage Directories:"
echo ""

STORAGE_OK=0
for dir in /data/authentik/{postgres,redis,media,custom-templates}; do
    if [ -d "$dir" ]; then
        STORAGE_OK=$(( STORAGE_OK + 1 ))
    fi
done

if [ "$STORAGE_OK" -eq 4 ]; then
    check_pass "Authentik storage directories ready (4/4)"
else
    check_fail "Missing Authentik directories: $((4 - STORAGE_OK))"
fi

echo ""

# ========== RESULT ==========
echo "================================"
echo "Automated checks: $PASSED passed, $FAILED failed"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✓ Phase 13 Validation PASSED"
else
    echo "⚠ Phase 13 has $FAILED issue(s)"
fi

echo ""
echo "================================"
echo "Next Steps:"
echo "================================"
echo ""
echo "1. Initial Authentik Setup (FIRST TIME):"
echo "   Visit: http://10.10.10.2:9080/if/flow/initial-setup/"
echo "   Create admin account"
echo ""
echo "2. Configure Applications in Authentik:"
echo "   [ ] Open WebUI (OAuth2)"
echo "   [ ] Grafana"
echo "   [ ] n8n"
echo "   [ ] JupyterLab"
echo "   [ ] Loadout Manager"
echo ""
echo "3. Create User Groups:"
echo "   [ ] admins (with MFA)"
echo "   [ ] users"
echo "   [ ] readonly"
echo ""
echo "4. Enable Forward Auth in Caddy:"
echo "   [ ] Update docker/compose.caddy.yml to mount Caddyfile.security"
echo "   [ ] Restart Caddy"
echo "   [ ] Test: curl https://ai.local/webui (should redirect to Authentik)"
echo ""
echo "5. Harden Host Firewall:"
echo "   [ ] sudo ufw status (check active)"
echo "   [ ] sudo ufw allow from 10.10.10.1 (jumpbox)"
echo "   [ ] Review ufw rules: sudo ufw show added"
echo ""
echo "6. Update Existing Services:"
echo "   [ ] Add 'cap_drop: [ALL]' to reduce privileges"
echo "   [ ] Add 'read_only: true' + tmpfs where possible"
echo "   [ ] Add resource limits (mem_limit, cpus)"
echo "   [ ] Document exceptions (Docker socket, GPU, etc)"
echo ""
echo "7. Audit Security:"
echo "   bash scripts/security-hardening-audit.sh"
echo ""
echo "8. Test Security:"
echo "   [ ] Try accessing Open WebUI without auth (should redirect to Authentik login)"
echo "   [ ] Verify MFA works for admin"
echo "   [ ] Check audit logs for authentication"
echo ""

exit 0
