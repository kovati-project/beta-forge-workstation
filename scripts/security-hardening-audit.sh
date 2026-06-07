#!/bin/bash
# Security hardening audit for Phase 13
# Checks Docker configurations, network segmentation, secrets management

set -e

echo "=== Phase 13 Security Audit ==="
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

# ========== DOCKER SECURITY CHECKS ==========
echo "Docker Security Checks:"
echo ""

# 1. Check for containers running as root
ROOT_CONTAINERS=$(docker ps --format "{{.Names}} {{.ID}}" | while read name id; do
    user=$(docker inspect --format='{{.Config.User}}' "$id" 2>/dev/null || echo "")
    [ -z "$user" ] && echo "$name"
done | wc -l)

if [ "$ROOT_CONTAINERS" -eq 0 ]; then
    check_pass "No containers running as root (or explicitly set non-root)"
else
    check_warn "$ROOT_CONTAINERS container(s) may be running as root"
fi

# 2. Check for privileged containers
PRIV_CONTAINERS=$(docker ps --format "{{.Names}}" --filter "label=privileged" 2>/dev/null | wc -l)
echo "Privileged containers (should be documented): $PRIV_CONTAINERS"

# 3. Check for read-only root filesystems in compose files
RO_COUNT=$(grep -r "read_only: true" docker/ 2>/dev/null | wc -l)
if [ "$RO_COUNT" -gt 5 ]; then
    check_pass "Read-only root filesystems configured ($RO_COUNT services)"
else
    check_warn "Only $RO_COUNT services have read-only root filesystem"
fi

# 4. Check for hardcoded passwords/secrets in compose files
SECRET_PATTERNS=$(grep -r "password.*changeme\|secret.*changeme\|PASSWORD=\|API_KEY=" docker/ 2>/dev/null | wc -l)
if [ "$SECRET_PATTERNS" -eq 0 ]; then
    check_pass "No obvious hardcoded secrets in compose files"
else
    check_fail "$SECRET_PATTERNS potential hardcoded secrets found (should use Docker secrets or env)"
fi

# 5. Check for volume mounts with excessive permissions
RW_ROOT=$(grep -r "rw\|/data:rw\|/:/data" docker/ 2>/dev/null | grep -v "ro" | wc -l)
if [ "$RW_ROOT" -lt 3 ]; then
    check_pass "Volume permissions reasonable (only $RW_ROOT excessive RW mounts)"
else
    check_warn "$RW_ROOT services have broad RW volume access"
fi

# 6. Check capability drops
CAP_DROP=$(grep -r "cap_drop:" docker/ 2>/dev/null | grep -c "ALL" || true)
if [ "$CAP_DROP" -gt 5 ]; then
    check_pass "Most services drop all capabilities"
else
    check_warn "Only $CAP_DROP services drop ALL capabilities"
fi

# 7. Check for no-new-privileges
NO_NEW=$(grep -r "no-new-privileges:true" docker/ 2>/dev/null | wc -l)
if [ "$NO_NEW" -gt 5 ]; then
    check_pass "no-new-privileges enabled on $NO_NEW services"
else
    check_warn "Only $NO_NEW services have no-new-privileges"
fi

echo ""
echo "Docker Security Checks: $PASSED passed, $FAILED failed"
echo ""

# ========== NETWORK SEGMENTATION CHECKS ==========
echo "Network Segmentation:"
echo ""

# Check if networks exist
for net in ai-inference ai-training ai-storage ai-monitoring ai-agents ai-auth; do
    if docker network ls | grep -q "$net"; then
        check_pass "Network '$net' exists"
    else
        check_warn "Network '$net' not found"
    fi
done

echo ""

# ========== SECRETS MANAGEMENT CHECKS ==========
echo "Secrets Management:"
echo ""

# Check for Docker secrets
DOCKER_SECRETS=$(docker secret ls 2>/dev/null | tail -n +2 | wc -l)
if [ "$DOCKER_SECRETS" -gt 0 ]; then
    check_pass "Docker secrets configured ($DOCKER_SECRETS secret(s))"
else
    check_warn "No Docker secrets found (use: echo 'secret' | docker secret create name -)"
fi

# Check for .env files (should exist for auth services)
if [ -f ".env" ]; then
    check_pass ".env file exists (should NOT be in git)"
else
    check_warn ".env file missing (needed for Authentik POSTGRES_PASSWORD, etc)"
fi

# Check .env is gitignored
if [ -f ".gitignore" ] && grep -q "\.env" .gitignore; then
    check_pass ".env is gitignored"
else
    check_warn ".env not in .gitignore (secrets at risk!)"
fi

echo ""

# ========== HOST-LEVEL SECURITY ==========
echo "Host Firewall & BMC:"
echo ""

# Check if UFW is enabled
if sudo ufw status | grep -q "Status: active"; then
    check_pass "UFW firewall enabled"
else
    check_warn "UFW firewall not enabled (sudo ufw enable)"
fi

# Check SSH key-only auth
if grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config 2>/dev/null; then
    check_pass "SSH key-only auth configured"
else
    check_warn "SSH password auth still enabled (consider disabling)"
fi

echo ""

# ========== AUTHENTIK SERVICE CHECKS ==========
echo "Authentik Identity Provider:"
echo ""

# Check if Authentik is running
if docker ps | grep -q authentik; then
    check_pass "Authentik service running"
else
    check_fail "Authentik service not running"
fi

# Check Authentik database
if docker ps | grep -q "authentik-postgres"; then
    check_pass "Authentik PostgreSQL running"
else
    check_fail "Authentik PostgreSQL not running"
fi

# Check Authentik Redis
if docker ps | grep -q "authentik-redis"; then
    check_pass "Authentik Redis running"
else
    check_fail "Authentik Redis not running"
fi

# Check Authentik API responding
if curl -sf http://localhost:9080/-/health/live/ > /dev/null 2>&1; then
    check_pass "Authentik API responding on :9080"
else
    check_warn "Authentik API not responding on :9080 (might be initializing)"
fi

echo ""

# ========== CADDY CONFIGURATION ==========
echo "Caddy TLS & Forward Auth:"
echo ""

# Check if Caddy config exists
if [ -f "configs/caddy/Caddyfile.security" ]; then
    check_pass "Caddy security configuration file exists"
else
    check_warn "Caddy security configuration not found"
fi

# Check for Authentik forward_auth in Caddy config
if grep -q "forward_auth.*authentik" configs/caddy/Caddyfile.security 2>/dev/null; then
    check_pass "Caddy configured with Authentik forward auth"
else
    check_warn "Caddy forward auth not configured"
fi

# Check for internal TLS
if grep -q "tls internal" configs/caddy/Caddyfile.security 2>/dev/null; then
    check_pass "Internal TLS enabled in Caddy"
else
    check_warn "Internal TLS might not be enabled"
fi

echo ""

# ========== AUDIT LOGGING ==========
echo "Audit Logging:"
echo ""

# Check if auditd is installed
if command -v auditctl &> /dev/null; then
    check_pass "auditd installed"
else
    check_warn "auditd not installed (sudo apt install auditd)"
fi

# Check Docker daemon logging config
if grep -q "log-driver" /etc/docker/daemon.json 2>/dev/null; then
    check_pass "Docker daemon logging configured"
else
    check_warn "Docker daemon logging not configured"
fi

echo ""

# ========== TLS CERTIFICATES ==========
echo "TLS Certificates:"
echo ""

# Check if Caddy root CA exists (created by `caddy trust`)
if [ -f "$HOME/.local/share/caddy/pki/authorities/local/root.crt" ]; then
    check_pass "Local Caddy CA certificate exists"
else
    check_warn "Local Caddy CA not found (run: caddy trust)"
fi

echo ""

# ========== VALIDATION SUMMARY ==========
echo "================================"
echo "Automated checks: $PASSED passed, $FAILED failed"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✓ Phase 13 Security Audit PASSED"
    echo ""
    echo "Next: Run manual checks (see below)"
else
    echo "⚠ Phase 13 has $FAILED issue(s) to address"
    echo ""
    echo "Top priorities:"
    echo "  1. Remove hardcoded secrets, use Docker secrets or .env"
    echo "  2. Create and enable network segmentation"
    echo "  3. Enable UFW firewall and restrict jumpbox access"
    echo "  4. Audit and drop unnecessary Linux capabilities"
fi

echo ""
echo "================================"
echo "Manual Security Checklist:"
echo "================================"
echo ""
echo "[ ] Authentik Initial Setup:"
echo "    1. Visit http://10.10.10.2:9000/if/flow/initial-setup/"
echo "    2. Create admin account"
echo "    3. Log in with admin credentials"
echo ""
echo "[ ] Configure Authentik Applications:"
echo "    1. Open WebUI (OAuth2/OIDC)"
echo "    2. Grafana"
echo "    3. n8n"
echo "    4. JupyterLab"
echo "    5. Loadout Manager"
echo ""
echo "[ ] Set up MFA in Authentik:"
echo "    1. Admin → Groups → admins → edit"
echo "    2. Enable TOTP MFA policy"
echo "    3. Test with admin account"
echo ""
echo "[ ] Create user groups:"
echo "    1. admins (can edit policies, manage users)"
echo "    2. users (can access inference/training)"
echo "    3. readonly (can access monitoring only)"
echo ""
echo "[ ] Firewall Configuration:"
echo "    1. sudo ufw status (should be active)"
echo "    2. sudo ufw allow from 10.10.10.1 (jumpbox)"
echo "    3. Verify only required ports accessible from jumpbox"
echo ""
echo "[ ] BMC Hardening:"
echo "    1. Change BMC password: ipmitool -I lanplus -H <bmc-ip> -U admin -P admin user set password 1 <new-pass>"
echo "    2. Verify HTTPS-only in BMC web UI"
echo "    3. Restrict BMC access to management VLAN"
echo ""
echo "[ ] Secrets Rotation:"
echo "    1. Change all default passwords (MinIO, PostgreSQL, Redis, etc)"
echo "    2. Rotate API keys"
echo "    3. Verify old credentials revoked"
echo ""
echo "[ ] Test Forward Auth:"
echo "    1. Visit https://ai.local/webui"
echo "    2. Should redirect to Authentik login"
echo "    3. Log in with created user"
echo "    4. Should redirect back to Open WebUI"
echo ""
echo "[ ] Audit Logging:"
echo "    1. Check Docker logs: docker logs <container>"
echo "    2. Monitor auditd: sudo ausearch -k docker_socket"
echo "    3. Review any authentication failures in Authentik logs"
echo ""
echo "[ ] Compliance Check:"
echo "    1. Review all services for need-to-have privileges"
echo "    2. Document exceptions (Docker socket, GPU access)"
echo "    3. Ensure least-privilege principle applied"
echo ""

exit 0
