#!/bin/bash
# Check that every image referenced in docker/compose.*.yml can still be pulled.
#
# Images are resolved with `docker manifest inspect` (registry metadata only,
# nothing is downloaded). ${VAR:-default} references are resolved to their
# default. Locally built images (loadout-manager) are skipped.
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
    ["minio/minio:latest"]="#92 MinIO stopped publishing images"
    ["unslothai/unsloth:latest"]="#95 official image is unsloth/unsloth, needs port/password changes"
    ["pablogimenez/realesrgan-api:latest"]="#95 image removed"
)
SKIP_PREFIXES=("loadout-manager:")

mapfile -t IMAGES < <(
    grep -hE '^\s*image:' "$REPO_ROOT"/docker/compose.*.yml \
        | sed -E 's/^\s*image:\s*//; s/["'"'"']//g; s/\s+#.*$//' \
        | sed -E 's/\$\{[A-Za-z_][A-Za-z0-9_]*:-([^}]*)\}/\1/g' \
        | sort -u
)

fail=0
for img in "${IMAGES[@]}"; do
    skip=0
    for p in "${SKIP_PREFIXES[@]}"; do [[ "$img" == "$p"* ]] && skip=1; done
    if [ "$skip" = 1 ]; then echo "skip    $img (built locally)"; continue; fi
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
