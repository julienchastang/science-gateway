#!/usr/bin/env bash
set -euo pipefail

NB_ID="${1:?Usage: $0 NOTEBOOK_ID}"

TS=$(date +%s)

SECRET=$(kubectl -n jhub get secret nblaunch-secrets \
  -o jsonpath='{.data.SECRET}' | base64 -d)

SIG=$(NB_ID="$NB_ID" TS="$TS" SECRET="$SECRET" \
python3 -c 'import os,hmac,hashlib; msg=(os.environ["NB_ID"]+":"+os.environ["TS"]).encode(); print(hmac.new(os.environ["SECRET"].encode(), msg, hashlib.sha256).hexdigest())')

echo "https://jupyterhub.unidata.ucar.edu/services/nblaunch/launch?nb=${NB_ID}&ts=${TS}&sig=${SIG}"

