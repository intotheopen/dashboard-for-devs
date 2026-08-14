#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMA_PATH="${VECTOR_SCHEMA_PATH:-$ROOT_DIR/vector_platform/sql/001_ito_posts_schema.sql}"
DB_CONTAINER="${DB_CONTAINER:-intotheopen-backend-db-1}"
POSTGRES_USER="${POSTGRES_USER:-ito}"
POSTGRES_DB="${POSTGRES_DB:-ito_posts}"

if [[ ! -f "$SCHEMA_PATH" ]]; then
  echo "Schema file not found: $SCHEMA_PATH" >&2
  exit 1
fi

cat "$SCHEMA_PATH" | docker exec -i "$DB_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
echo "Applied schema: $SCHEMA_PATH -> $DB_CONTAINER/$POSTGRES_DB"
