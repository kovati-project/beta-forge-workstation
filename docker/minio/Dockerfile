# syntax=docker/dockerfile:1
#
# MinIO server + mc client, built from source at pinned releases.
#
# Why: MinIO stopped publishing community container images (minio/minio,
# minio/mc and the quay.io copies can no longer be pulled; see issue #92), so
# docker/compose.storage.yml builds this image locally instead.
#
# The result mirrors the old upstream image where it matters to this repo:
#   - `minio` and `mc` in /usr/bin (scripts run `docker exec minio mc ...`)
#   - upstream's docker-entrypoint.sh, so `command: server /data ...` works
#   - runs as root (default), so existing /data/minio ownership still works
#   - MC_CONFIG_DIR=/tmp/.mc, as upstream set it
#   - curl, for the compose healthcheck
#
# Note: 2025 MinIO releases ship a web console stripped of most admin
# features (users, policies, config). Use `mc admin ...` for those.
#
# Bump: change the RELEASE args below (and the image tag in compose.storage.yml),
# and the Go version if the new release's go.mod `toolchain` line requires it.

ARG GO_VERSION=1.24.8
ARG ALPINE_VERSION=3.22.2

FROM golang:${GO_VERSION}-bookworm AS build

ARG MINIO_RELEASE=RELEASE.2025-10-15T17-29-55Z
ARG MC_RELEASE=RELEASE.2025-08-13T08-35-41Z

ENV CGO_ENABLED=0 \
    GOTOOLCHAIN=local \
    GOFLAGS=-trimpath

WORKDIR /src

# minio server. ldflags come from upstream's own generator, invoked the same way
# their release Makefile target does (Version = the release timestamp).
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    set -eux; \
    git clone --depth 1 --branch "${MINIO_RELEASE}" https://github.com/minio/minio.git minio; \
    cd minio; \
    version="$(echo "${MINIO_RELEASE#RELEASE.}" | sed -E 's/T([0-9]+)-([0-9]+)-([0-9]+)Z/T\1:\2:\3Z/')"; \
    ldflags="$(MINIO_RELEASE=RELEASE go run buildscripts/gen-ldflags.go "${version}")"; \
    echo "minio ldflags: ${ldflags}"; \
    go build -tags kqueue -ldflags "${ldflags}" -o /out/minio .; \
    cp dockerscripts/docker-entrypoint.sh /out/docker-entrypoint.sh; \
    cp LICENSE /out/LICENSE; \
    cp CREDITS /out/CREDITS

# mc client
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    set -eux; \
    git clone --depth 1 --branch "${MC_RELEASE}" https://github.com/minio/mc.git mc; \
    cd mc; \
    version="$(echo "${MC_RELEASE#RELEASE.}" | sed -E 's/T([0-9]+)-([0-9]+)-([0-9]+)Z/T\1:\2:\3Z/')"; \
    ldflags="$(MC_RELEASE=RELEASE go run buildscripts/gen-ldflags.go "${version}")"; \
    echo "mc ldflags: ${ldflags}"; \
    go build -tags kqueue -ldflags "${ldflags}" -o /out/mc .

FROM alpine:${ALPINE_VERSION}

ARG MINIO_RELEASE=RELEASE.2025-10-15T17-29-55Z
ARG MC_RELEASE=RELEASE.2025-08-13T08-35-41Z

LABEL org.opencontainers.image.title="minio" \
      org.opencontainers.image.description="MinIO server and mc client built from source (AGPL-3.0)" \
      org.opencontainers.image.version="${MINIO_RELEASE}" \
      org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.opencontainers.image.source="https://github.com/minio/minio" \
      io.min.mc.version="${MC_RELEASE}"

RUN apk add --no-cache ca-certificates curl

# Same defaults as upstream's image (Dockerfile.release).
ENV MINIO_ACCESS_KEY_FILE=access_key \
    MINIO_SECRET_KEY_FILE=secret_key \
    MINIO_ROOT_USER_FILE=access_key \
    MINIO_ROOT_PASSWORD_FILE=secret_key \
    MINIO_KMS_SECRET_KEY_FILE=kms_master_key \
    MINIO_CONFIG_ENV_FILE=config.env \
    MC_CONFIG_DIR=/tmp/.mc

COPY --from=build /out/minio /out/mc /out/docker-entrypoint.sh /usr/bin/
COPY --from=build /out/LICENSE /out/CREDITS /licenses/

EXPOSE 9000 9001
VOLUME ["/data"]

ENTRYPOINT ["/usr/bin/docker-entrypoint.sh"]
CMD ["minio"]
