#!/usr/bin/env bash
# Point this repo's ./data at the sibling backend data tree so embeddings,
# processed JSONL/CSV, raw scrapes, validation artefacts, and telemetry stay
# shared. Never keep a separate local data/ copy here.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PARENT="$(dirname "$ROOT")"
TARGET=""

for candidate in \
  "$PARENT/intotheopen-backend" \
  "$PARENT/ITO-RND" \
  "$PARENT/ITO Testing Visual Mock"
do
  if [[ -d "$candidate/data" && -f "$candidate/config/settings.py" ]]; then
    TARGET="$candidate/data"
    break
  fi
done

if [[ -z "$TARGET" ]]; then
  echo "ensure-shared-data: no sibling backend data/ found under $PARENT" >&2
  exit 1
fi

LINK="$ROOT/data"
if [[ -L "$LINK" ]]; then
  current="$(readlink "$LINK")"
  if [[ "$current" == "$TARGET" ]]; then
    exit 0
  fi
  rm -f "$LINK"
elif [[ -d "$LINK" ]]; then
  echo "ensure-shared-data: refusing to replace real directory $LINK" >&2
  echo "Move any unique files into $TARGET, then remove $LINK and re-run." >&2
  exit 1
elif [[ -e "$LINK" ]]; then
  echo "ensure-shared-data: unexpected path $LINK" >&2
  exit 1
fi

ln -s "$TARGET" "$LINK"
echo "Linked $LINK -> $TARGET"
