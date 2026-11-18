#!/bin/bash
# Compute Engine startup script (runs as root on every boot).
#
# Everything this VM needs comes from instance metadata, set at creation time:
#   app-image     Artifact Registry image to run, e.g.
#                 europe-southwest1-docker.pkg.dev/<project>/ecommerce/orders-app:v1
#   compose-file  docker compose file for this VM (deploy/<app>/compose.yml)
#   init-sql      (optional) SQL file mounted into the Postgres container
#
# No keys are copied to the VM: Docker logs in to Artifact Registry with a
# short-lived token of the service account attached to the VM.
set -euo pipefail

METADATA=http://metadata.google.internal/computeMetadata/v1
md() { curl -sf -H "Metadata-Flavor: Google" "${METADATA}/$1"; }

# 1. Install Docker Engine + compose plugin (only on first boot)
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

# 2. Read configuration from metadata
APP_IMAGE=$(md instance/attributes/app-image)
REGISTRY_HOST=${APP_IMAGE%%/*}                   # e.g. europe-southwest1-docker.pkg.dev
PROJECT_ID=$(md project/project-id)

mkdir -p /opt/ecommerce && cd /opt/ecommerce
md instance/attributes/compose-file > compose.yml
md instance/attributes/init-sql > init.sql || true
cat > .env <<ENV
APP_IMAGE=${APP_IMAGE}
PROJECT_ID=${PROJECT_ID}
ENV

# 3. Log in to Artifact Registry with the VM's service account token
md instance/service-accounts/default/token \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' \
  | docker login -u oauth2accesstoken --password-stdin "https://${REGISTRY_HOST}"

# 4. Pull and (re)start the application
docker compose pull
docker compose up -d
