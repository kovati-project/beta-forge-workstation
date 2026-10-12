#!/usr/bin/env bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# ============================================================================
# setup-ufw.sh - configure the host firewall (UFW) for the beta workstation
#
# Tracks: TASK-071 / issue #33 (UFW was never enabled; every listening port was
# reachable from anything that could route to the host).
#
# SAFE BY DEFAULT
#   * DRY RUN unless --apply is given: prints the exact commands it would run
#     and changes nothing. Only --apply needs root.
#   * LOCKOUT-PROOF: there is NO default management network. You must pass
#     --allow-from <cidr> (repeatable) or export UFW_MGMT_CIDRS. The SSH allow
#     rule(s) for those CIDRs are added BEFORE anything else and BEFORE
#     `ufw enable`, and enabling is refused unless such a rule is confirmed.
#     (The repo's historical 10.10.10.0/24 assumption is wrong for this host,
#     which sits on 192.168.1.0/24 - see docs/validation/TASK-070.)
#   * Idempotent: rules that already exist in `ufw status` are skipped, and the
#     after.rules block is replaced in place, never duplicated.
#
# WHAT IT CONFIGURES
#   1. SSH allow rules from each management CIDR (port auto-detected, default 22)
#   2. (optional, default on) allow from Docker bridge subnets, so containers can
#      still reach host-published ports through the host IP
#   3. one allow rule per enabled entry of PORT_TABLE below, per management CIDR
#   4. default deny incoming / default allow outgoing
#   5. (only with --docker-user) a managed DOCKER-USER block in
#      /etc/ufw/after.rules, see next section
#   6. `ufw --force enable` (or `ufw reload` if already active)
#
# !! DOCKER CAVEAT - READ THIS !!
#   Ports PUBLISHED BY DOCKER (`ports: "3000:8080"` in a compose file) are NOT
#   filtered by UFW's normal rules. Docker DNATs them in the nat table and the
#   packets then traverse the FORWARD chain (DOCKER / DOCKER-USER), never UFW's
#   INPUT chain. So on a Docker host, `ufw default deny incoming` + `ufw allow
#   from <cidr> to any port 3000` protects only processes running directly on
#   the host (sshd, ...). Almost every service on this workstation is a
#   container, so WITHOUT --docker-user UFW WILL NOT PROTECT THEM.
#
#   --docker-user adds a clearly delimited, managed block to
#   /etc/ufw/after.rules (backup taken first, own block replaced idempotently)
#   that hooks Docker's DOCKER-USER chain - the well-known ufw-docker pattern -
#   so new connections to published ports are dropped unless they come from a
#   management CIDR (or from a Docker bridge subnet). Rules match the
#   ORIGINAL destination port (conntrack --ctorigdstport), i.e. the host port
#   you see in compose files, not the container port.
#
# OTHER LIMITS
#   * IPv4 only. Docker does not publish IPv6 by default; the DOCKER-USER block
#     does not touch ip6tables. UFW's own default-deny does apply to IPv6 when
#     IPV6=yes in /etc/default/ufw.
#   * Does not touch SSH hardening (password auth is still enabled per
#     TASK-071), the BMC, or Docker/compose files.
#   * Written to be verified statically; it has not been run against the live
#     workstation. See docs/runbooks/ufw-setup.md before using --apply.
#
# Usage: scripts/setup-ufw.sh --help
# ============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# PORT TABLE - edit here.
#
# One service per line:   GROUP  PORT  PROTO  SCOPE  LABEL...
#   GROUP  free-form purpose tag, used only for grouping in output
#   PORT   host port as published/listened, a single port or a range a:b
#   PROTO  tcp | udp
#   SCOPE  mgmt = reachable only from the management CIDRs   (default for all)
#          any  = reachable from anywhere (use sparingly)
#   LABEL  free text, becomes the UFW rule comment ("beta-ws: <label>")
#
# To disable an entry, comment it out. To enable one that is commented out,
# remove the leading "# ". Source of truth for ports: plan/PROJECT_PLAN.md
# "Key Ports Reference" plus the host ports published in docker/compose.*.yml.
# SSH is NOT in this table; its port is detected (see detect_ssh_ports).
# ---------------------------------------------------------------------------
read -r -d '' PORT_TABLE <<'EOF' || true
# --- web UIs operators open in a browser -------------------------------------
ui      3000   tcp  mgmt  Open WebUI
ui      3001   tcp  mgmt  Grafana
ui      3002   tcp  mgmt  Langfuse
ui      3003   tcp  mgmt  OpenHands
ui      3010   tcp  mgmt  Dify Web
ui      5678   tcp  mgmt  n8n
ui      7860   tcp  mgmt  Kohya_ss
ui      8081   tcp  mgmt  Label Studio
ui      8188   tcp  mgmt  ComfyUI
ui      8501   tcp  mgmt  Unsloth Studio
ui      8800   tcp  mgmt  Loadout Manager
ui      8888   tcp  mgmt  JupyterLab
ui      9001   tcp  mgmt  MinIO Console
ui      9090   tcp  mgmt  InvokeAI

# --- reverse proxy / identity ------------------------------------------------
edge    80     tcp  mgmt  Caddy HTTP
edge    443    tcp  mgmt  Caddy HTTPS
edge    9080   tcp  mgmt  Authentik HTTP
edge    9443   tcp  mgmt  Authentik HTTPS

# --- model / media APIs ------------------------------------------------------
api     11434  tcp  mgmt  Ollama API
api     8000   tcp  mgmt  vLLM pair A
api     8001   tcp  mgmt  vLLM pair B
api     8002   tcp  mgmt  vLLM 4-GPU
api     9099   tcp  mgmt  Whisper STT
api     5000   tcp  mgmt  Piper TTS
api     8189   tcp  mgmt  Real-ESRGAN
api     8190   tcp  mgmt  Rembg

# --- data stores --------------------------------------------------------------
data    6333   tcp  mgmt  Qdrant REST
data    6334   tcp  mgmt  Qdrant gRPC
data    9000   tcp  mgmt  MinIO S3 API

# --- monitoring ---------------------------------------------------------------
mon     9091   tcp  mgmt  Prometheus

# --- OFF by default: internal plumbing, no reason to expose to the LAN --------
# Containers still reach these through the Docker-subnet allow rule.
# data    5432   tcp  mgmt  PostgreSQL
# mon     9100   tcp  mgmt  node-exporter
# mon     9400   tcp  mgmt  DCGM exporter
# mon     8989   tcp  mgmt  cAdvisor
# mon     9093   tcp  mgmt  Alertmanager
# agent   3100:3103 tcp mgmt MCP servers (filesystem/browser/code-exec/fetch)
# agent   5001   tcp  mgmt  Dify API
# web     8080   tcp  mgmt  SearXNG
#
# NOTE: TASK-071 also saw something listening on 5201 (and DNS on 53). 5201 is
# not defined in any compose file in this repo - identify it before allowing it.
EOF

# ---------------------------------------------------------------------------
# Configuration / testing hooks (environment)
# ---------------------------------------------------------------------------
UFW_ETC_DIR="${UFW_ETC_DIR:-/etc/ufw}"            # where after.rules lives
SSHD_CONFIG="${SSHD_CONFIG:-/etc/ssh/sshd_config}"
UFW_MGMT_CIDRS="${UFW_MGMT_CIDRS:-}"              # comma/space separated
UFW_DOCKER_SUBNETS="${UFW_DOCKER_SUBNETS:-172.16.0.0/12}"

DOCKER_BEGIN="# BEGIN BETA-WORKSTATION UFW-DOCKER (managed by scripts/setup-ufw.sh - do not edit by hand)"
DOCKER_END="# END BETA-WORKSTATION UFW-DOCKER"
DOCKER_CHAIN="ufw-mgmt-docker"
COMMENT_PREFIX="beta-ws"

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
APPLY=0
DO_STATUS=0
DOCKER_USER=0
DOCKER_SUBNETS_ON=1
ALLOW_CLIENT_OUTSIDE=0
CLI_CIDRS=()
CLI_SSH_PORTS=()
MGMT_CIDRS=()
SSH_PORTS=()
DOCKER_SUBNETS=()
TBL_GROUP=(); TBL_PORT=(); TBL_PROTO=(); TBL_SCOPE=(); TBL_LABEL=()
EXISTING=""
UFW_ACTIVE=0
UFW_READABLE=0
SSH_RULES_OK=0
DOCKER_BLOCK_CHANGED=0
CLIENT_OUTSIDE=0
UFW_RAW=""
NOTICES=()

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
say()  { printf '%s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
usage_error() { printf 'ERROR: %s\nTry: %s --help\n' "$*" "$0" >&2; exit 2; }

usage() {
    cat <<'EOF'
Usage: setup-ufw.sh [--allow-from CIDR]... [options]

Configures UFW for the beta workstation. DRY RUN by default; nothing changes
until --apply is given (which requires root).

Management network (REQUIRED for dry-run and --apply, no default):
  --allow-from CIDR        management source network, e.g. 192.168.1.0/24 or a
                           single host 192.168.1.50. Repeatable. Also accepts a
                           comma-separated list. Overrides UFW_MGMT_CIDRS.
  UFW_MGMT_CIDRS=...       same, via environment (comma or space separated)

Modes:
  (default)                dry run: print the ufw commands that would be run
  --apply                  make the changes (root/sudo required)
  --status                 read-only report of firewall / Docker-integration state
  --help, -h               this text

Options:
  --docker-user            ALSO install the managed DOCKER-USER block in
                           /etc/ufw/after.rules so Docker-published ports are
                           restricted to the management CIDRs. WITHOUT THIS,
                           UFW DOES NOT PROTECT DOCKER-PUBLISHED PORTS.
  --ssh-port N             extra SSH port to allow (repeatable); added to the
                           ports detected from the current session, sshd and
                           live listeners (fallback 22)
  --no-docker-subnets      do not allow Docker bridge subnets to reach host
                           ports (default: allow, so container-to-host-IP
                           traffic keeps working); subnets from
                           UFW_DOCKER_SUBNETS, default 172.16.0.0/12
  --allow-client-outside-mgmt
                           proceed with --apply even though the SSH client you
                           are connected from is not inside any management CIDR
                           (new SSH sessions from there WILL be blocked)

Exit codes: 0 ok, 1 refused/failed, 2 usage error.

Examples:
  scripts/setup-ufw.sh --allow-from 192.168.1.0/24                  # dry run
  scripts/setup-ufw.sh --allow-from 192.168.1.50 --docker-user      # dry run
  sudo scripts/setup-ufw.sh --allow-from 192.168.1.0/24 --docker-user --apply
  scripts/setup-ufw.sh --status

See docs/runbooks/ufw-setup.md for the operator runbook and rollback.
EOF
}

# Print a command with shell quoting for arguments that need it.
fmt_cmd() {
    local a q="'" out=""
    for a in "$@"; do
        if [[ $a =~ ^[A-Za-z0-9_./:@%+=,-]+$ ]]; then
            out+="$a "
        else
            out+="'${a//$q/$q\\$q$q}' "
        fi
    done
    printf '%s\n' "${out% }"
}

# Run (apply) or just print (dry run) a state-changing command.
run_cmd() {
    if (( APPLY )); then
        printf '  + '
        fmt_cmd "$@"
        "$@" || die "command failed: $(fmt_cmd "$@")
       Aborting. ufw has NOT been enabled by this run; the firewall may be partially
       configured - review with: ufw status verbose"
    else
        printf '  [dry-run] '
        fmt_cmd "$@"
    fi
}

is_root() { [[ $(id -u) -eq 0 ]]; }

# ---------------------------------------------------------------------------
# IPv4 / CIDR helpers (pure bash)
# ---------------------------------------------------------------------------
is_ip4() {
    local o
    [[ $1 =~ ^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$ ]] || return 1
    for o in "${BASH_REMATCH[@]:1:4}"; do
        (( 10#$o <= 255 )) || return 1
    done
    return 0
}

ip4_to_int() {   # caller must have validated with is_ip4
    local a b c d
    IFS=. read -r a b c d <<<"$1"
    echo $(( (10#$a << 24) | (10#$b << 16) | (10#$c << 8) | 10#$d ))
}

int_to_ip4() {
    local n=$1
    echo "$(( (n >> 24) & 255 )).$(( (n >> 16) & 255 )).$(( (n >> 8) & 255 )).$(( n & 255 ))"
}

prefix_mask() {  # prefix length -> 32-bit mask as integer
    local p=$1
    if (( p == 0 )); then echo 0; else echo $(( (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF )); fi
}

# normalize_cidr "a.b.c.d[/n]" -> prints "network/n". Returns 1 if invalid.
normalize_cidr() {
    local in=$1 ip prefix mask net
    ip=${in%%/*}
    if [[ $in == */* ]]; then prefix=${in#*/}; else prefix=32; fi
    is_ip4 "$ip" || return 1
    [[ $prefix =~ ^[0-9]{1,2}$ ]] || return 1
    prefix=$(( 10#$prefix ))
    (( prefix <= 32 )) || return 1
    mask=$(prefix_mask "$prefix")
    net=$(( $(ip4_to_int "$ip") & mask ))
    echo "$(int_to_ip4 "$net")/$prefix"
}

ip_in_cidr() {   # ip, normalized cidr
    local ip=$1 cidr=$2 net prefix mask
    is_ip4 "$ip" || return 1
    net=${cidr%/*}
    prefix=${cidr#*/}
    mask=$(prefix_mask "$prefix")
    (( ( $(ip4_to_int "$ip") & mask ) == $(ip4_to_int "$net") ))
}

ip_in_any_mgmt() {
    local c
    for c in "${MGMT_CIDRS[@]}"; do
        if ip_in_cidr "$1" "$c"; then return 0; fi
    done
    return 1
}

# ---------------------------------------------------------------------------
# Argument / environment handling
# ---------------------------------------------------------------------------
split_list() {   # split on commas / whitespace, one item per line
    local IFS=$', \t\n' item
    for item in $1; do
        [[ -n $item ]] && printf '%s\n' "$item"
    done
    return 0
}

parse_args() {
    while (( $# )); do
        case $1 in
            --allow-from)
                (( $# >= 2 )) || usage_error "--allow-from needs a CIDR argument"
                CLI_CIDRS+=("$2"); shift 2 ;;
            --allow-from=*)
                CLI_CIDRS+=("${1#*=}"); shift ;;
            --ssh-port)
                (( $# >= 2 )) || usage_error "--ssh-port needs a port number"
                CLI_SSH_PORTS+=("$2"); shift 2 ;;
            --ssh-port=*)
                CLI_SSH_PORTS+=("${1#*=}"); shift ;;
            --apply)                    APPLY=1; shift ;;
            --status)                   DO_STATUS=1; shift ;;
            --docker-user)              DOCKER_USER=1; shift ;;
            --no-docker-subnets)        DOCKER_SUBNETS_ON=0; shift ;;
            --allow-client-outside-mgmt) ALLOW_CLIENT_OUTSIDE=1; shift ;;
            -h|--help)                  usage; exit 0 ;;
            *)                          usage_error "unknown argument: $1" ;;
        esac
    done
    if (( APPLY && DO_STATUS )); then
        usage_error "--status is read-only and cannot be combined with --apply"
    fi
}

resolve_mgmt_cidrs() {
    local raw item norm
    local -a items=()
    if (( ${#CLI_CIDRS[@]} )); then
        for raw in "${CLI_CIDRS[@]}"; do
            while IFS= read -r item; do items+=("$item"); done < <(split_list "$raw")
        done
    elif [[ -n $UFW_MGMT_CIDRS ]]; then
        while IFS= read -r item; do items+=("$item"); done < <(split_list "$UFW_MGMT_CIDRS")
    fi

    if (( ${#items[@]} == 0 )); then
        cat >&2 <<'EOF'
ERROR: no management CIDR given - refusing to continue.

There is deliberately NO default: a wrong guess would either lock you out or
leave the host open. Pass the network(s) you administer this host from:

    scripts/setup-ufw.sh --allow-from 192.168.1.0/24
    UFW_MGMT_CIDRS=192.168.1.50,192.168.1.51 scripts/setup-ufw.sh

(This host is on 192.168.1.0/24 per TASK-070; the 10.10.10.0/24 in older docs
does not exist here.)
EOF
        exit 2
    fi

    for item in "${items[@]}"; do
        norm=$(normalize_cidr "$item") || usage_error "not a valid IPv4 address or CIDR: '$item' (IPv6 is not supported)"
        if [[ $norm == */0 ]]; then
            usage_error "'$item' is a /0 - that would allow the whole internet. Refusing."
        fi
        if [[ $norm != "$item" && $item == */* ]]; then
            say "note: '$item' normalized to network address $norm"
        fi
        if (( ${norm#*/} < 16 )); then
            NOTICES+=("management CIDR $norm is very broad (prefix < /16); is that intended?")
        fi
        # de-duplicate, keep order
        local seen=0 e
        for e in ${MGMT_CIDRS[@]+"${MGMT_CIDRS[@]}"}; do
            [[ $e == "$norm" ]] && seen=1
        done
        (( seen )) || MGMT_CIDRS+=("$norm")
    done
}

resolve_docker_subnets() {
    local item norm
    (( DOCKER_SUBNETS_ON )) || return 0
    while IFS= read -r item; do
        norm=$(normalize_cidr "$item") || usage_error "UFW_DOCKER_SUBNETS: not a valid IPv4 CIDR: '$item'"
        DOCKER_SUBNETS+=("$norm")
    done < <(split_list "$UFW_DOCKER_SUBNETS")
}

# ---------------------------------------------------------------------------
# Port table
# ---------------------------------------------------------------------------
parse_port_table() {
    local line group port proto scope label n=0
    while IFS= read -r line; do
        line="${line#"${line%%[![:space:]]*}"}"          # ltrim
        [[ -z $line || $line == \#* ]] && continue
        n=$(( n + 1 ))
        read -r group port proto scope label <<<"$line"
        [[ $port =~ ^[0-9]+(:[0-9]+)?$ ]]   || die "PORT_TABLE: bad port '$port' in: $line"
        [[ $proto == tcp || $proto == udp ]] || die "PORT_TABLE: bad proto '$proto' in: $line"
        [[ $scope == mgmt || $scope == any ]] || die "PORT_TABLE: bad scope '$scope' in: $line"
        [[ -n $label ]]                      || die "PORT_TABLE: missing label in: $line"
        TBL_GROUP+=("$group"); TBL_PORT+=("$port"); TBL_PROTO+=("$proto")
        TBL_SCOPE+=("$scope"); TBL_LABEL+=("$label")
    done <<<"$PORT_TABLE"
    (( n > 0 )) || die "PORT_TABLE is empty"
}

# ---------------------------------------------------------------------------
# SSH detection
# ---------------------------------------------------------------------------
add_ssh_port() {
    local p=$1 e
    [[ $p =~ ^[0-9]+$ ]] || return 0
    p=$(( 10#$p ))
    (( p >= 1 && p <= 65535 )) || return 0
    for e in ${SSH_PORTS[@]+"${SSH_PORTS[@]}"}; do
        [[ $e == "$p" ]] && return 0
    done
    SSH_PORTS+=("$p")
}

# Union of every source we can find. Over-allowing an extra SSH port from the
# management CIDRs is harmless; missing the real one is a lockout.
detect_ssh_ports() {
    local p line sshd_bin f
    local -a conf_files=()

    # 1. the port this very session is connected to
    if [[ -n ${SSH_CONNECTION:-} ]]; then
        read -r _ _ _ p <<<"$SSH_CONNECTION" || true
        add_ssh_port "${p:-}"
    fi

    # 2. effective config (root only; resolves Include and defaults)
    sshd_bin=$(command -v sshd 2>/dev/null || true)
    [[ -x /usr/sbin/sshd ]] && sshd_bin=/usr/sbin/sshd
    if [[ -n $sshd_bin ]] && is_root; then
        while IFS= read -r line; do
            [[ $line == "port "* ]] && add_ssh_port "${line#port }"
        done < <("$sshd_bin" -T 2>/dev/null || true)
    fi

    # 3. static config files
    [[ -f $SSHD_CONFIG ]] && conf_files+=("$SSHD_CONFIG")
    if [[ -d ${SSHD_CONFIG}.d ]]; then
        for f in "${SSHD_CONFIG}".d/*.conf; do
            [[ -f $f ]] && conf_files+=("$f")
        done
    fi
    if (( ${#conf_files[@]} )); then
        while IFS= read -r p; do
            add_ssh_port "$p"
        done < <(grep -hiE '^[[:space:]]*Port[[:space:]]+[0-9]+' "${conf_files[@]}" 2>/dev/null | awk '{print $2}' || true)
    fi

    # 4. live listeners owned by sshd (also covers systemd ssh.socket, where
    #    sshd_config's Port is ignored). Needs root to see process names.
    if command -v ss >/dev/null 2>&1; then
        while IFS= read -r p; do
            add_ssh_port "$p"
        done < <(ss -Hltnp 2>/dev/null | grep -F '"sshd"' | awk '{n=split($4,a,":"); print a[n]}' || true)
    fi

    # 5. explicit --ssh-port
    for p in ${CLI_SSH_PORTS[@]+"${CLI_SSH_PORTS[@]}"}; do
        if ! [[ $p =~ ^[0-9]+$ ]] || (( 10#$p < 1 || 10#$p > 65535 )); then
            usage_error "--ssh-port: not a valid port: '$p'"
        fi
        add_ssh_port "$p"
    done

    (( ${#SSH_PORTS[@]} )) || add_ssh_port 22
}

# IP of the SSH client driving this session, if we are in one. Empty otherwise.
ssh_client_ip() {
    local ip=""
    if [[ -n ${SSH_CONNECTION:-} ]]; then
        ip=${SSH_CONNECTION%% *}
    elif [[ -n ${SSH_CLIENT:-} ]]; then
        ip=${SSH_CLIENT%% *}
    fi
    printf '%s' "$ip"
}

# Peers of established connections to the SSH port(s). Used when SSH_CONNECTION
# was stripped (typically by sudo) so we cannot tell which one is "us".
ssh_established_peers() {
    local p peer
    command -v ss >/dev/null 2>&1 || return 0
    for p in "${SSH_PORTS[@]}"; do
        while IFS= read -r peer; do
            peer=${peer%:*}
            peer=${peer#\[}; peer=${peer%\]}
            peer=${peer#::ffff:}
            [[ -n $peer ]] && printf '%s\n' "$peer"
        done < <(ss -Htn state established "( sport = :$p )" 2>/dev/null | awk '{print $NF}' || true)
    done | sort -u
}

ssh_session_checks() {
    local client peers peer
    local -a outside=()
    client=$(ssh_client_ip)
    if [[ -n $client ]]; then
        say "SSH session : you appear to be connected over SSH from $client"
        if is_ip4 "$client"; then
            if ip_in_any_mgmt "$client"; then
                say "               $client is inside a management CIDR - OK"
            else
                NOTICES+=("your SSH client $client is NOT inside any management CIDR. Existing sessions survive 'ufw enable' (conntrack), but NEW SSH sessions from $client will be blocked.")
                CLIENT_OUTSIDE=1
            fi
        else
            NOTICES+=("your SSH client address '$client' is not IPv4; this script only manages IPv4 allow rules, so new SSH sessions from it will be blocked.")
            CLIENT_OUTSIDE=1
        fi
        return 0
    fi

    peers=$(ssh_established_peers || true)
    if [[ -n $peers ]]; then
        say "SSH session : SSH_CONNECTION not set (sudo strips it?); established SSH peers on this host:"
        while IFS= read -r peer; do
            if is_ip4 "$peer" && ip_in_any_mgmt "$peer"; then
                say "               $peer  (inside management CIDR)"
            else
                say "               $peer  (NOT inside any management CIDR)"
                outside+=("$peer")
            fi
        done <<<"$peers"
        if (( ${#outside[@]} )); then
            NOTICES+=("established SSH peer(s) outside the management CIDRs: ${outside[*]} - if one of them is you, new sessions from there will be blocked.")
        fi
    fi
}

# ---------------------------------------------------------------------------
# UFW state
# ---------------------------------------------------------------------------
# Normalize `ufw status verbose` text: strip comments, squeeze whitespace, drop
# the "IN" of "ALLOW IN" so lines look like "3000/tcp ALLOW 192.168.1.0/24".
normalize_status() {
    sed -e 's/[[:space:]]*#.*$//' -e 's/[[:space:]]\{1,\}/ /g' -e 's/ ALLOW IN / ALLOW /'
}

load_existing() {
    EXISTING=""; UFW_ACTIVE=0; UFW_READABLE=0; UFW_RAW=""
    command -v ufw >/dev/null 2>&1 || return 0
    if UFW_RAW=$(ufw status verbose 2>/dev/null); then
        UFW_READABLE=1
        EXISTING=$(normalize_status <<<"$UFW_RAW")
        if grep -q '^Status: active' <<<"$UFW_RAW"; then UFW_ACTIVE=1; fi
    else
        UFW_RAW=""
    fi
}

# ufw prints single hosts without the /32 suffix.
ufw_addr() { printf '%s' "${1%/32}"; }

rule_present() {  # normalized "TO ALLOW FROM" key as printed by `ufw status`
    [[ -n $EXISTING ]] && grep -Fxq -- "$1" <<<"$EXISTING"
}

# add_allow LABEL PORT PROTO FROM   (PORT empty = any port; FROM "any" = anywhere)
# Skips rules already shown by `ufw status`; otherwise runs/prints the command.
add_allow() {
    local label=$1 port=$2 proto=$3 from=$4 key to from_key
    [[ $from == any ]] || from=$(ufw_addr "$from")
    local -a cmd=(ufw allow from "$from" to any)
    if [[ $from == any ]]; then from_key="Anywhere"; else from_key=$from; fi
    if [[ -n $port ]]; then
        cmd+=(port "$port" proto "$proto")
        to="$port/$proto"
    else
        to="Anywhere"
    fi
    cmd+=(comment "$COMMENT_PREFIX: $label")
    key="$to ALLOW $from_key"
    if rule_present "$key"; then
        printf '  [skip] already present: %s\n' "$key"
        return 0
    fi
    run_cmd "${cmd[@]}"
}

# Independent confirmation that an SSH allow rule from a management CIDR is in
# place (from `ufw show added`, which also works while ufw is inactive, or from
# the active status). Fail closed: if we cannot positively see one, return 1.
verify_ssh_rule_exists() {
    local added="" status="" c p a
    added=$(ufw show added 2>/dev/null || true)
    status=$(ufw status verbose 2>/dev/null | normalize_status || true)
    for c in "${MGMT_CIDRS[@]}"; do
        a=$(ufw_addr "$c")
        for p in "${SSH_PORTS[@]}"; do
            if grep -Eq "allow.* from ${a//./\.} .*port ${p}( |\$)" <<<"$added"; then return 0; fi
            if grep -Fxq -- "$p/tcp ALLOW $a" <<<"$status"; then return 0; fi
        done
    done
    return 1
}

# ---------------------------------------------------------------------------
# DOCKER-USER block
# ---------------------------------------------------------------------------
build_docker_block() {
    local i c s
    printf '%s\n' "$DOCKER_BEGIN"
    cat <<EOF
# Restricts connections to Docker-PUBLISHED ports (DNAT'd, so they bypass UFW's
# INPUT rules) to the management CIDRs. Generated from PORT_TABLE in
# scripts/setup-ufw.sh - re-run that script instead of editing this block.
# Containers talking to each other / to the internet are not affected: only
# NEW, DNAT'd (= published-port) connections are inspected.
*filter
:DOCKER-USER - [0:0]
:${DOCKER_CHAIN} - [0:0]
:${DOCKER_CHAIN}-deny - [0:0]
# insert (not append) so we sit in front of dockerd's own trailing RETURN
-I DOCKER-USER 1 -j ${DOCKER_CHAIN}
-A ${DOCKER_CHAIN} -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
-A ${DOCKER_CHAIN} -m conntrack ! --ctstate DNAT -j RETURN
EOF
    for s in ${DOCKER_SUBNETS[@]+"${DOCKER_SUBNETS[@]}"}; do
        printf -- '-A %s -s %s -j RETURN\n' "$DOCKER_CHAIN" "$s"
    done
    for i in "${!TBL_PORT[@]}"; do
        printf '# %s: %s\n' "${TBL_GROUP[$i]}" "${TBL_LABEL[$i]}"
        if [[ ${TBL_SCOPE[$i]} == any ]]; then
            printf -- '-A %s -p %s -m conntrack --ctorigdstport %s --ctdir ORIGINAL -j RETURN\n' \
                "$DOCKER_CHAIN" "${TBL_PROTO[$i]}" "${TBL_PORT[$i]}"
        else
            for c in "${MGMT_CIDRS[@]}"; do
                printf -- '-A %s -s %s -p %s -m conntrack --ctorigdstport %s --ctdir ORIGINAL -j RETURN\n' \
                    "$DOCKER_CHAIN" "$c" "${TBL_PROTO[$i]}" "${TBL_PORT[$i]}"
            done
        fi
    done
    cat <<EOF
# everything else that was published and is not allowed above
-A ${DOCKER_CHAIN} -j ${DOCKER_CHAIN}-deny
-A ${DOCKER_CHAIN}-deny -m limit --limit 3/min --limit-burst 10 -j LOG --log-prefix "[UFW DOCKER BLOCK] "
-A ${DOCKER_CHAIN}-deny -j DROP
COMMIT
EOF
    printf '%s\n' "$DOCKER_END"
}

# Print the existing managed block (markers included) from a file, or nothing.
extract_docker_block() {
    awk -v b="$DOCKER_BEGIN" -v e="$DOCKER_END" '
        $0 == b { inb = 1 }
        inb     { print }
        $0 == e { inb = 0 }
    ' "$1"
}

# Print the file with the managed block removed.
strip_docker_block() {
    awk -v b="$DOCKER_BEGIN" -v e="$DOCKER_END" '
        $0 == b { skip = 1; next }
        $0 == e { skip = 0; next }
        !skip   { print }
    ' "$1"
}

install_docker_block() {
    local rules="$UFW_ETC_DIR/after.rules" new_block cur_block stripped tmp backup nb ne

    new_block=$(build_docker_block)
    say "  target file : $rules"

    if [[ ! -r $rules ]]; then
        if (( APPLY )); then
            die "$rules not found or not readable - is ufw installed? (apt install ufw)"
        fi
        say "  ($rules not readable here; assuming block is not yet present)"
        cur_block=""
    else
        nb=$(grep -cxF -- "$DOCKER_BEGIN" "$rules" || true)
        ne=$(grep -cxF -- "$DOCKER_END" "$rules" || true)
        if [[ $nb != "$ne" || $nb -gt 1 ]]; then
            die "$rules has unbalanced or duplicate managed-block markers (begin=$nb end=$ne); fix it by hand before re-running"
        fi
        cur_block=$(extract_docker_block "$rules")
    fi

    if [[ -n $cur_block && $cur_block == "$new_block" ]]; then
        say "  [skip] managed block already present and up to date"
        return 0
    fi

    if [[ -n $cur_block ]]; then
        say "  action      : REPLACE existing managed block"
    else
        say "  action      : APPEND managed block"
    fi
    DOCKER_BLOCK_CHANGED=1

    if (( ! APPLY )); then
        say "  backup      : $rules.bak-<timestamp> (taken first)"
        say "  block to be written:"
        printf '%s\n' "$new_block" | sed 's/^/    | /'
        return 0
    fi

    # Syntax-check the block on its own (self-contained: declares every chain it
    # references). Nothing is committed with --test.
    if command -v iptables-restore >/dev/null 2>&1; then
        if ! printf '%s\n' "$new_block" | iptables-restore --test --noflush; then
            die "iptables-restore rejected the generated DOCKER-USER block; after.rules NOT modified"
        fi
        say "  [ok] iptables-restore --test accepted the block"
    else
        warn "iptables-restore not found; skipping syntax test of the generated block"
    fi

    backup="$rules.bak-$(date +%Y%m%d-%H%M%S)"
    cp -p -- "$rules" "$backup"
    say "  backup      : $backup"

    tmp=$(mktemp "$UFW_ETC_DIR/.after.rules.XXXXXX")
    stripped=$(strip_docker_block "$rules")        # $(...) trims trailing blank lines
    printf '%s\n\n%s\n' "$stripped" "$new_block" >"$tmp"
    chmod --reference="$rules" -- "$tmp"
    chown --reference="$rules" -- "$tmp" 2>/dev/null || true
    mv -f -- "$tmp" "$rules"
    say "  [ok] wrote managed block to $rules"
}

# ---------------------------------------------------------------------------
# --status (read-only)
# ---------------------------------------------------------------------------
cmd_status() {
    local rules="$UFW_ETC_DIR/after.rules" line addr port p covered i
    local -A seen=()

    say "=== UFW status (read-only) ==="
    say ""
    say "-- ufw --"
    if ! command -v ufw >/dev/null 2>&1; then
        say "ufw is not installed (apt install ufw)"
    elif ! is_root; then
        say "need root to read ufw state; re-run with sudo for the rule list"
    else
        ufw status verbose || true
    fi

    say ""
    say "-- SSH --"
    detect_ssh_ports
    say "ssh port(s) detected: ${SSH_PORTS[*]}"
    local client
    client=$(ssh_client_ip)
    [[ -n $client ]] && say "this session's client: $client"

    say ""
    say "-- Docker integration (DOCKER-USER block in $rules) --"
    if [[ -r $rules ]]; then
        if grep -qxF -- "$DOCKER_BEGIN" "$rules"; then
            say "managed block: PRESENT"
            for line in "$rules".bak-*; do
                [[ -e $line ]] && say "backup: $line"
            done
        else
            say "managed block: ABSENT - Docker-published ports are NOT restricted by UFW"
        fi
    else
        say "cannot read $rules (not root, or ufw not installed)"
    fi
    if command -v iptables >/dev/null 2>&1 && is_root; then
        say "live DOCKER-USER chain:"
        iptables -S DOCKER-USER 2>&1 | sed 's/^/    /' || true
    fi

    say ""
    say "-- listening TCP ports vs PORT_TABLE --"
    if ! command -v ss >/dev/null 2>&1; then
        say "ss not available"
        return 0
    fi
    parse_port_table
    while IFS= read -r line; do
        addr=$(awk '{print $4}' <<<"$line")
        port=${addr##*:}
        [[ $port =~ ^[0-9]+$ ]] || continue
        [[ -n ${seen[$port]:-} ]] && continue
        seen[$port]=1
        case $addr in
            127.*|\[::1\]:*|::1:*) printf '  %-6s loopback only\n' "$port"; continue ;;
        esac
        covered=""
        for i in "${!TBL_PORT[@]}"; do
            p=${TBL_PORT[$i]}
            if [[ $p == *:* ]]; then
                (( port >= ${p%%:*} && port <= ${p##*:} )) && covered="${TBL_LABEL[$i]}"
            else
                [[ $p == "$port" ]] && covered="${TBL_LABEL[$i]}"
            fi
        done
        if (( ${#SSH_PORTS[@]} )); then
            for p in "${SSH_PORTS[@]}"; do [[ $p == "$port" ]] && covered="SSH"; done
        fi
        if [[ -n $covered ]]; then
            printf '  %-6s in rule table: %s\n' "$port" "$covered"
        else
            printf '  %-6s NOT in rule table (would be denied from the LAN once enabled)\n' "$port"
        fi
    done < <(ss -Hltn 2>/dev/null | sort -k4)
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
main() {
    local i c p s group last_group=""

    parse_args "$@"

    if (( DO_STATUS )); then
        cmd_status
        return 0
    fi

    resolve_mgmt_cidrs
    resolve_docker_subnets
    parse_port_table
    detect_ssh_ports

    if (( APPLY )); then
        is_root || die "--apply must run as root (try: sudo $0 ... --apply)"
        command -v ufw >/dev/null 2>&1 || die "ufw is not installed (apt install ufw); not installing it automatically"
    fi

    load_existing

    say "=== beta-workstation UFW setup: $( (( APPLY )) && echo APPLY || echo 'DRY RUN - nothing will be changed') ==="
    say ""
    say "Management CIDRs : ${MGMT_CIDRS[*]}"
    say "SSH port(s)      : ${SSH_PORTS[*]}"
    if (( DOCKER_SUBNETS_ON )); then
        say "Docker subnets   : ${DOCKER_SUBNETS[*]} (allowed to reach host ports)"
    else
        say "Docker subnets   : not allowed (--no-docker-subnets) - containers reaching host IP:port will be blocked"
    fi
    say "Docker-user mode : $( (( DOCKER_USER )) && echo ON || echo off)"
    if ! command -v ufw >/dev/null 2>&1; then
        say "ufw             : not installed here - existing-rule detection skipped"
    elif (( ! UFW_READABLE )); then
        say "ufw             : state not readable without root - existing-rule detection skipped"
    else
        say "ufw             : $( (( UFW_ACTIVE )) && echo active || echo inactive)"
    fi
    ssh_session_checks
    say ""

    if (( ! DOCKER_USER )); then
        cat <<'EOF'
*** DOCKER CAVEAT *********************************************************
Without --docker-user, UFW WILL NOT PROTECT PORTS PUBLISHED BY DOCKER.
Docker DNATs published ports into the FORWARD/DOCKER-USER path, bypassing
UFW's INPUT rules. The allow rules below protect only host processes (e.g.
sshd). Nearly every service here is a container: add --docker-user to
restrict them to the management CIDRs. Not yet protected otherwise.
***************************************************************************

EOF
    fi

    for c in ${NOTICES[@]+"${NOTICES[@]}"}; do
        warn "$c"
    done
    if (( CLIENT_OUTSIDE )); then
        if (( APPLY && ! ALLOW_CLIENT_OUTSIDE )); then
            die "refusing to --apply: your SSH client is not inside any management CIDR (see warning above). Add its network with --allow-from, or pass --allow-client-outside-mgmt if you really intend this."
        fi
        (( APPLY )) && warn "continuing because --allow-client-outside-mgmt was given"
        (( APPLY )) || say "(--apply would REFUSE here unless --allow-client-outside-mgmt is given)"
    fi
    (( ${#NOTICES[@]} )) && say ""

    # ---- 1. SSH first: lockout protection ---------------------------------
    say "[1/6] SSH access from management CIDRs (added first, before anything else)"
    for c in "${MGMT_CIDRS[@]}"; do
        for p in "${SSH_PORTS[@]}"; do
            add_allow "ssh (management)" "$p" tcp "$c"
            SSH_RULES_OK=$(( SSH_RULES_OK + 1 ))
        done
    done
    # Fail closed, and do it NOW - before defaults or enable are touched, so an
    # already-active ufw never ends up with deny-incoming and no SSH rule.
    if (( APPLY )); then
        if ! verify_ssh_rule_exists; then
            die "could not confirm an SSH allow rule from a management CIDR in ufw (checked 'ufw show added' and 'ufw status'); stopping before default policy or enable are changed."
        fi
        say "  [ok] confirmed SSH allow rule from a management CIDR exists"
    fi
    say ""

    # ---- 2. Docker bridge subnets ------------------------------------------
    say "[2/6] Docker bridge subnets -> host ports"
    if (( DOCKER_SUBNETS_ON )); then
        for s in "${DOCKER_SUBNETS[@]}"; do
            add_allow "docker bridge subnet to host" "" "" "$s"
        done
    else
        say "  (skipped: --no-docker-subnets)"
    fi
    say ""

    # ---- 3. Service rules from PORT_TABLE ----------------------------------
    say "[3/6] Service ports from PORT_TABLE"
    for i in "${!TBL_PORT[@]}"; do
        group=${TBL_GROUP[$i]}
        if [[ $group != "$last_group" ]]; then
            say " # group: $group"
            last_group=$group
        fi
        if [[ ${TBL_SCOPE[$i]} == any ]]; then
            add_allow "${TBL_LABEL[$i]}" "${TBL_PORT[$i]}" "${TBL_PROTO[$i]}" any
        else
            for c in "${MGMT_CIDRS[@]}"; do
                add_allow "${TBL_LABEL[$i]}" "${TBL_PORT[$i]}" "${TBL_PROTO[$i]}" "$c"
            done
        fi
    done
    say ""

    # ---- 4. Defaults (after the allows, so an already-active ufw never ------
    #         has deny-incoming without the SSH rule in place) ----------------
    say "[4/6] Default policy"
    if (( UFW_READABLE )) && grep -q 'deny (incoming)' <<<"$UFW_RAW"; then
        say "  [skip] default incoming already deny"
    else
        run_cmd ufw default deny incoming
    fi
    if (( UFW_READABLE )) && grep -q 'allow (outgoing)' <<<"$UFW_RAW"; then
        say "  [skip] default outgoing already allow"
    else
        run_cmd ufw default allow outgoing
    fi
    say ""

    # ---- 5. DOCKER-USER block ----------------------------------------------
    say "[5/6] Docker-published ports (DOCKER-USER block in $UFW_ETC_DIR/after.rules)"
    if (( DOCKER_USER )); then
        install_docker_block
    else
        say "  (skipped: --docker-user not given - Docker-published ports stay UNFILTERED by UFW)"
    fi
    say ""

    # ---- 6. Enable ----------------------------------------------------------
    say "[6/6] Enable"
    if (( SSH_RULES_OK < 1 )); then
        die "internal check failed: no SSH allow rule from a management CIDR is planned; refusing to enable ufw"
    fi
    if (( APPLY )); then
        if (( UFW_ACTIVE )); then
            if (( DOCKER_BLOCK_CHANGED )); then
                run_cmd ufw reload
            else
                say "  [skip] ufw already active; rules above are live"
            fi
        else
            run_cmd ufw --force enable
        fi
        say ""
        say "Done. Verify:  sudo ufw status verbose"
        if (( DOCKER_USER )); then
            say "              sudo iptables -S DOCKER-USER ; sudo iptables -S $DOCKER_CHAIN"
            say "From a host OUTSIDE the management CIDRs, a published port must now time out:"
            say "              curl --max-time 5 http://<workstation-ip>:3000/"
        fi
        say "Rollback: see docs/runbooks/ufw-setup.md  (quick: sudo ufw disable)"
    else
        if (( UFW_ACTIVE )); then
            if (( DOCKER_BLOCK_CHANGED )); then
                run_cmd ufw reload
            else
                say "  [skip] ufw already active; rules above would be live immediately"
            fi
        else
            run_cmd ufw --force enable
        fi
        say ""
        say "DRY RUN complete - nothing was changed."
        say "Review the list above, keep a second SSH session open, then re-run with --apply (as root)."
    fi
}

main "$@"
