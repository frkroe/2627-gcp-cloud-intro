#!/bin/bash
# Recreates what Cloud Intro needs from GCP Project Setup. Everyone runs it once at the
# start of Lab 2: at the end of Project Setup you deleted everything.
#
#   - APIs
#   - Pub/Sub topics and subscriptions: order-events(-sub), delivery-events(-sub)
#   - Artifact Registry repository "ecommerce"
#   - the delivery-app:v1 image, built by Cloud Build (no Docker needed on your laptop)
#
# No service accounts and no IAM bindings: with the Editor role you can't grant roles,
# so the apps run as the default compute service account ($SA_DEFAULT), as in Project Setup Lab 4.
#
# Requirements: you ran `source config.env` (PROJECT_ID and PROJECT_NUMBER filled in).
# Safe to run twice: resources that already exist are skipped.
set -uo pipefail

: "${PROJECT_ID:?run 'source config.env' first}"
: "${PROJECT_NUMBER:?set PROJECT_NUMBER in config.env, then run 'source config.env'}"
cd "$(dirname "$0")/.."
gcloud config set project "$PROJECT_ID"

step() { echo; echo "==> $*"; }
exists() { "$@" > /dev/null 2>&1; }

step "Enabling APIs"
gcloud services enable compute.googleapis.com pubsub.googleapis.com \
  artifactregistry.googleapis.com logging.googleapis.com cloudbuild.googleapis.com

step "Pub/Sub topics and subscriptions"
for t in order-events delivery-events; do
  exists gcloud pubsub topics describe "$t" || gcloud pubsub topics create "$t" --labels="$LABELS"
  exists gcloud pubsub subscriptions describe "$t-sub" ||
    gcloud pubsub subscriptions create "$t-sub" --topic="$t" --labels="$LABELS"
done

step "Artifact Registry repository"
exists gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" ||
  gcloud artifacts repositories create "$AR_REPO" --repository-format=docker \
    --location="$REGION" --labels="$LABELS"

step "delivery-app:v1 image (Cloud Build, 2-3 minutes)"
if exists gcloud artifacts docker images describe "$REGISTRY/delivery-app:v1"; then
  echo "already there"
else
  gcloud builds submit ecommerce \
    --config=scripts/cloudbuild-delivery.yaml \
    --substitutions="_IMAGE=$REGISTRY/delivery-app:v1"
fi

step "Done. You can start Lab 2."
