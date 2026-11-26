#!/usr/bin/env bash
# install-backup-timer.sh: run scripts/backup.sh every night via systemd.
#
# Installs ai-workstation-backup.service + .timer and enables the timer. It
# does not run a backup now: the first run is at the next scheduled time
# (or right after boot if that time was missed while the host was off).
#
#   sudo bash scripts/install-backup-timer.sh            # install / update
#   sudo bash scripts/install-backup-timer.sh --remove   # disable and delete
#
# Environment:
#   BACKUP_ONCALENDAR  systemd calendar spec      (default *-*-* 03:30:00)
#   BACKUP_MODE        backup.sh argument          (default all; never models)
#
# Runs as root: /data/backups is root-owned, earlier manual runs left root-owned
# run directories that retention must be able to prune, and some volumes are
# root-only. backup.sh does not stop or restart any container, so a run does
# not touch vLLM.

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "run as root: sudo bash $0" >&2
    exit 1
fi

UNIT=ai-workstation-backup
UNIT_DIR=/etc/systemd/system
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ONCALENDAR="${BACKUP_ONCALENDAR:-*-*-* 03:30:00}"
MODE="${BACKUP_MODE:-all}"

if [[ "${1:-}" == "--remove" ]]; then
    systemctl disable --now "$UNIT.timer" 2>/dev/null || true
    rm -f "$UNIT_DIR/$UNIT.service" "$UNIT_DIR/$UNIT.timer"
    systemctl daemon-reload
    echo "removed $UNIT.timer and $UNIT.service"
    exit 0
fi

case "$MODE" in
    all|volumes|configs) ;;
    *) echo "BACKUP_MODE must be all, volumes or configs (got '$MODE')" >&2; exit 1 ;;
esac
[[ -f "$PROJECT_DIR/scripts/backup.sh" ]] || { echo "no scripts/backup.sh under $PROJECT_DIR" >&2; exit 1; }
systemd-analyze calendar "$ONCALENDAR" >/dev/null || { echo "invalid BACKUP_ONCALENDAR: $ONCALENDAR" >&2; exit 1; }

cat > "$UNIT_DIR/$UNIT.service" <<EOF
# Installed by scripts/install-backup-timer.sh. Re-run it to change; do not edit.
[Unit]
Description=AI Workstation nightly backup (scripts/backup.sh $MODE)
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/bash $PROJECT_DIR/scripts/backup.sh $MODE
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
TimeoutStartSec=6h
StandardOutput=journal
StandardError=journal
StandardInput=null
EOF

# No Requires=/Wants= on the service here: a timer that requires its service
# starts it as soon as the timer itself starts (on enable and on every boot).
cat > "$UNIT_DIR/$UNIT.timer" <<EOF
# Installed by scripts/install-backup-timer.sh. Re-run it to change; do not edit.
[Unit]
Description=Run the AI Workstation backup nightly

[Timer]
OnCalendar=$ONCALENDAR
RandomizedDelaySec=10min
Persistent=true
Unit=$UNIT.service

[Install]
WantedBy=timers.target
EOF

chmod 644 "$UNIT_DIR/$UNIT.service" "$UNIT_DIR/$UNIT.timer"
systemd-analyze verify "$UNIT_DIR/$UNIT.service" "$UNIT_DIR/$UNIT.timer"
systemctl daemon-reload
systemctl enable --now "$UNIT.timer"

echo "installed: $UNIT.timer ($ONCALENDAR) -> backup.sh $MODE in $PROJECT_DIR"
systemctl list-timers "$UNIT.timer" --no-pager
echo
echo "Run one now:   sudo systemctl start $UNIT.service   (follow: journalctl -fu $UNIT)"
echo "Last result:   systemctl status $UNIT.service"
