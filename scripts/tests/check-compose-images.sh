#!/bin/bash
# Check that every image referenced in docker/compose.*.yml can still be pulled.
#
# Images are resolved with `docker manifest inspect` (registry metadata only,
# nothing is downloaded). ${VAR:-default} references are resolved to their
# default. Services with a build: key (loadout-manager, minio, the MCP servers)
# are built locally rather than pulled, so their images are skipped.
#
# KNOWN_BROKEN lists images with an open issue. They are reported, not failed,
# and the check fails if one of them starts resolving again so the list cannot
# go stale.
#
# Usage: bash scripts/tests/check-compose-images.sh
# Exit:  0 all resolve (or known broken), 1 a new unresolvable image or a stale
#        KNOWN_BROKEN entry

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

declare -A KNOWN_BROKEN=(
    ["unslothai/unsloth:latest"]="#95 official image is unsloth/unsloth, needs port/password changes"
    ["pablogimenez/realesrgan-api:latest"]="#95 image removed"
)

# One "<built> <image>" line per service; built=1 when the service also has a
# build: key. Services sit at two-space indent under `services:`, keys at four.
list_images() {
    awk '
        function flush() { if (img != "") print built, img; img = ""; built = 0 }
        /^[^ #]/      { flush(); in_svc = ($0 ~ /^services:/); next }
        !in_svc       { next }
        /^  [^ #]/    { flush(); next }
        /^    build:/ { built = 1 }
        /^    image:/ { img = $0; sub(/^    image:[ \t]*/, "", img) }
        END           { flush() }
    ' "$REPO_ROOT"/docker/compose.*.yml \
        | sed -E 's/["'"'"']//g; s/\s+#.*$//' \
        | sed -E 's/\$\{[A-Za-z_][A-Za-z0-9_]*:-([^}]*)\}/\1/g'
}
mapfile -t BUILT < <(list_images | awk '$1 == 1 { print $2 }' | sort -u)
mapfile -t IMAGES < <(list_images | awk '$1 == 0 { print $2 }' | sort -u)

fail=0
for img in "${BUILT[@]}"; do echo "skip    $img (built locally)"; done
for img in "${IMAGES[@]}"; do
    if [[ "$img" == *'$'* ]]; then echo "FAIL    $img (unresolved variable)"; fail=1; continue; fi

    if out=$(docker manifest inspect "$img" 2>&1 >/dev/null); then
        if [ -n "${KNOWN_BROKEN[$img]:-}" ]; then
            echo "STALE   $img resolves again; remove it from KNOWN_BROKEN (${KNOWN_BROKEN[$img]})"
            fail=1
        else
            echo "ok      $img"
        fi
    elif [[ "$out" == *toomanyrequests* || "$out" == *"rate limit"* ]]; then
        # Docker Hub's anonymous limit, not a property of the image: don't fail
        echo "unknown $img (registry rate limit, not checked)"
    elif [ -n "${KNOWN_BROKEN[$img]:-}" ]; then
        echo "known   $img (${KNOWN_BROKEN[$img]})"
    else
        echo "FAIL    $img: $(echo "$out" | head -n1 | cut -c1-120)"
        fail=1
    fi
done

for img in "${!KNOWN_BROKEN[@]}"; do
    printf '%s\n' "${IMAGES[@]}" | grep -qxF "$img" \
        || { echo "STALE   $img is in KNOWN_BROKEN but no compose file uses it"; fail=1; }
done

[ "$fail" = 0 ] && echo "All compose images resolve." || echo "Unresolvable compose images found."
exit $fail
