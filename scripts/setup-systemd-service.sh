#!/bin/bash
# Phase 14 — Operations Runbook: Systemd Service Setup
# Sets up auto-start and auto-stop of AI Workstation services
# Run once as root to enable auto-start on boot
# Usage: sudo bash scripts/setup-systemd-service.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_step() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "This script must be run as root (use: sudo bash setup-systemd-service.sh)"
    exit 1
fi

log_step "=== Setting up Systemd Services for AI Workstation ==="
echo ""

# Determine paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
USER_NAME="${SUDO_USER:-$(whoami)}"
USER_HOME=$(eval echo ~$USER_NAME)

log_step "Project directory: $PROJECT_DIR"
log_step "User: $USER_NAME ($USER_HOME)"
log_step "Starting scripts location: $PROJECT_DIR/scripts"
echo ""

# Verify required scripts exist
if [ ! -f "$PROJECT_DIR/scripts/start-all.sh" ]; then
    log_error "start-all.sh not found at $PROJECT_DIR/scripts/"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/scripts/healthcheck.sh" ]; then
    log_error "healthcheck.sh not found at $PROJECT_DIR/scripts/"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/scripts/backup.sh" ]; then
    log_error "backup.sh not found at $PROJECT_DIR/scripts/"
    exit 1
fi

log_step "All scripts found"
echo ""

# Create systemd service for startup
log_step "Creating systemd service: ai-workstation.service"

cat > /etc/systemd/system/ai-workstation.service <<EOF
[Unit]
Description=AI Workstation Services
After=docker.service network-online.target
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/scripts/start-all.sh
ExecStop=docker compose -f $PROJECT_DIR/docker/compose.webui.yml \\
                        -f $PROJECT_DIR/docker/compose.agentic.yml \\
                        -f $PROJECT_DIR/docker/compose.codegen.yml \\
                        -f $PROJECT_DIR/docker/compose.voice.yml \\
                        -f $PROJECT_DIR/docker/compose.training.yml \\
                        -f $PROJECT_DIR/docker/compose.inference.yml \\
                        -f $PROJECT_DIR/docker/compose.loadout.yml \\
                        -f $PROJECT_DIR/docker/compose.auth.yml \\
                        -f $PROJECT_DIR/docker/compose.monitoring.yml \\
                        -f $PROJECT_DIR/docker/compose.storage.yml down
TimeoutStartSec=600
TimeoutStopSec=120
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

chmod 644 /etc/systemd/system/ai-workstation.service
log_step "✓ Service created: /etc/systemd/system/ai-workstation.service"
echo ""

# Create systemd timer for daily backups
log_step "Creating systemd timer: ai-workstation-backup.timer"

cat > /etc/systemd/system/ai-workstation-backup.service <<EOF
[Unit]
Description=AI Workstation Daily Backup
After=ai-workstation.service
Wants=network-online.target

[Service]
Type=oneshot
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/scripts/backup.sh
StandardOutput=journal
StandardError=journal
StandardInput=null

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/ai-workstation-backup.timer <<EOF
[Unit]
Description=Run AI Workstation Backup Daily at 2 AM
Requires=ai-workstation-backup.service
After=network-online.target

[Timer]
OnCalendar=daily
OnCalendar=*-*-* 02:00:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

chmod 644 /etc/systemd/system/ai-workstation-backup.service
chmod 644 /etc/systemd/system/ai-workstation-backup.timer
log_step "✓ Backup timer created"
echo ""

# Create health check timer (optional, every 6 hours)
log_step "Creating systemd timer: ai-workstation-healthcheck.timer"

cat > /etc/systemd/system/ai-workstation-healthcheck.service <<EOF
[Unit]
Description=AI Workstation Health Check
After=ai-workstation.service
Wants=network-online.target

[Service]
Type=oneshot
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/scripts/healthcheck.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/ai-workstation-healthcheck.timer <<EOF
[Unit]
Description=Run AI Workstation Health Check Every 6 Hours
Requires=ai-workstation-healthcheck.service
After=network-online.target

[Timer]
OnBootSec=5min
OnUnitActiveSec=6h
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

chmod 644 /etc/systemd/system/ai-workstation-healthcheck.service
chmod 644 /etc/systemd/system/ai-workstation-healthcheck.timer
log_step "✓ Health check timer created"
echo ""

# Reload systemd daemon
log_step "Reloading systemd daemon..."
systemctl daemon-reload

echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "Available commands:"
echo ""
echo "  Start services (manually):"
echo "    systemctl start ai-workstation"
echo ""
echo "  Enable auto-start on boot:"
echo "    systemctl enable ai-workstation"
echo ""
echo "  Disable auto-start on boot:"
echo "    systemctl disable ai-workstation"
echo ""
echo "  View status:"
echo "    systemctl status ai-workstation"
echo "    systemctl status ai-workstation-backup.timer"
echo "    systemctl status ai-workstation-healthcheck.timer"
echo ""
echo "  View logs:"
echo "    journalctl -u ai-workstation -f"
echo "    journalctl -u ai-workstation-backup.service"
echo ""
echo "  View timer schedules:"
echo "    systemctl list-timers --all"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Enable auto-start: sudo systemctl enable ai-workstation"
echo "2. Test startup: sudo systemctl start ai-workstation"
echo "3. Monitor: sudo journalctl -u ai-workstation -f"
echo ""
echo "Backup will run daily at 2 AM"
echo "Health check will run every 6 hours (starting 5 min after boot)"
echo ""
