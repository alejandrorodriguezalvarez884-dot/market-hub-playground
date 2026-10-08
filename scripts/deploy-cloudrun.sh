#!/usr/bin/env bash
# Deploys the production image (site + API in one container) to Google Cloud Run. Cloud Build
# builds the Dockerfile remotely, so Docker is not needed locally. The service keeps nothing (no
# bucket, no database) and scales to zero: it costs nothing while nobody uses it.
#
# Requirements: the gcloud CLI logged in on a project with billing enabled, and .env with HUB_URL.
# This script writes no secret: it points the service at two that already exist in Secret Manager.
#   - The Anthropic key of the chat: ANTHROPIC_SECRET names the secret (default ANTHROPIC_API_KEY,
#     the one the portal and Fundamentals Lab use). Without it the chat stays off.
#   - Market Hub's session secret (market-hub-session-secret), to read the hub's sign-in.
# HUB_URL is required: the chat spends with the owner's key and has no spending cap of its own,
# so the service is never deployed open to everybody.
#
# Optional overrides: GCP_PROJECT, GCP_REGION, SERVICE_NAME, MAX_INSTANCES, and in .env
# PLAYGROUND_MODEL and PLAYGROUND_EFFORT.
set -euo pipefail

cd "$(dirname "$0")/.."

fail() {
  echo "error: $*" >&2
  exit 1
}

command -v gcloud >/dev/null || fail "gcloud is not installed."

GCP_PROJECT="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
GCP_REGION="${GCP_REGION:-europe-west1}"
SERVICE_NAME="${SERVICE_NAME:-market-hub-playground}"
MAX_INSTANCES="${MAX_INSTANCES:-2}"
ENV_FILE=".env"

[[ -n "$GCP_PROJECT" ]] || fail "No GCP project selected. Run 'gcloud init' or set GCP_PROJECT."
[[ -f "$ENV_FILE" ]] || fail "$ENV_FILE not found."

# Read single values instead of sourcing the file, and drop the quotes around them.
env_value() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^"//' -e 's/"$//' || true; }
HUB_URL="$(env_value HUB_URL)"
MODEL="$(env_value PLAYGROUND_MODEL)"
EFFORT="$(env_value PLAYGROUND_EFFORT)"
ANTHROPIC_SECRET="${ANTHROPIC_SECRET:-$(env_value ANTHROPIC_SECRET)}"
ANTHROPIC_SECRET="${ANTHROPIC_SECRET:-ANTHROPIC_API_KEY}"
[[ "$HUB_URL" == https://* ]] || fail "HUB_URL in $ENV_FILE must be Market Hub's address: the service is not deployed without its sign-in."

gcp() { gcloud --project "$GCP_PROJECT" --quiet "$@"; }

# Give the service's account a role on something, only if it does not have it yet. A policy is
# one document: two deploys writing it at the same moment collide ("concurrent policy changes"),
# and the second fails. Reading it first means that in the ordinary deploy nothing is written,
# so the services' deploys can run side by side.
grant() {
  local kind="$1" resource="$2" role="$3" member="serviceAccount:$SERVICE_ACCOUNT"
  shift 3
  # grep reads the whole answer (no -q): leaving early would break the pipe, and that would read as "missing".
  if gcp $kind get-iam-policy "$resource" --flatten='bindings[].members' --format='value(bindings.role,bindings.members)' 2>/dev/null \
      | tr -d '\r' | grep -xF "$role"$'\t'"$member" >/dev/null; then
    return 0
  fi
  gcp $kind add-iam-policy-binding "$resource" --member "$member" --role "$role" "$@" >/dev/null
}

echo "→ Enabling APIs in $GCP_PROJECT"
gcp services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com

# Source deploys build with, and run as, the Compute Engine default service account.
PROJECT_NUMBER="$(gcp projects describe "$GCP_PROJECT" --format='value(projectNumber)' | tr -d '\r')"
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
grant projects "$GCP_PROJECT" roles/run.builder --condition=None

echo "→ Secrets"
gcp secrets describe market-hub-session-secret >/dev/null 2>&1 || fail "Market Hub's secret market-hub-session-secret does not exist. Deploy the hub first."
grant secrets market-hub-session-secret roles/secretmanager.secretAccessor
SECRETS="HUB_SESSION_SECRET=market-hub-session-secret:latest"
echo "→ Behind Market Hub's sign-in ($HUB_URL)"
if gcp secrets describe "$ANTHROPIC_SECRET" >/dev/null 2>&1; then
  grant secrets "$ANTHROPIC_SECRET" roles/secretmanager.secretAccessor
  SECRETS="$SECRETS,ANTHROPIC_API_KEY=$ANTHROPIC_SECRET:latest"
  echo "→ Chat on, key from the secret $ANTHROPIC_SECRET (no spending cap: the limit is the account's credit)"
else
  echo "note: the secret $ANTHROPIC_SECRET does not exist: the chat stays off."
fi
VARS="HUB_URL=$HUB_URL"
[[ -z "$MODEL" ]] || VARS="$VARS,PLAYGROUND_MODEL=$MODEL"
[[ -z "$EFFORT" ]] || VARS="$VARS,PLAYGROUND_EFFORT=$EFFORT"

echo "→ Building with Cloud Build and deploying '$SERVICE_NAME' to $GCP_REGION (a few minutes)"
# One turn of the chat has to fit in a request: the composer gives the model 45 seconds.
gcp run deploy "$SERVICE_NAME" \
  --source . \
  --region "$GCP_REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 1 \
  --memory 1Gi \
  --min-instances 0 \
  --max-instances "$MAX_INSTANCES" \
  --timeout 60 \
  --set-secrets "$SECRETS" \
  --set-env-vars "$VARS"

URL="$(gcp run services describe "$SERVICE_NAME" --region "$GCP_REGION" --format 'value(status.url)' | tr -d '\r')"
if curl -fsS "$URL/api/health" >/dev/null 2>&1; then
  echo "✓ Deployed: $URL"
else
  fail "Deployed, but $URL/api/health failed. Logs: gcloud run services logs read $SERVICE_NAME --region $GCP_REGION"
fi
