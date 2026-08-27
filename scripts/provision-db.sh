#!/usr/bin/env bash
# provision-db.sh — create the PostgreSQL role + dev/prod databases for this project.
#
# MANUAL, deliberate, one-time. NOT run by /init or any Claude skill — you invoke it
# yourself, only when the project actually needs a database. It mutates the SHARED
# cluster (creates a role + two databases) using db_admin creds from ~/.pgpass, and
# sources the app password from ./.keys at runtime — no secret is ever hardcoded here.
#
# Usage:  ./scripts/provision-db.sh <projectname>
set -euo pipefail

NAME="${1:?usage: ./scripts/provision-db.sh <projectname>}"
HOST="${DB_HOST:-postgres.o6.org}"

[ -f .keys ] || { echo "ERROR: no .keys in $(pwd) — run from the project root after env setup."; exit 1; }
DB_PASSWORD=$(grep -E '^DB_PASSWORD=' .keys | cut -d= -f2-)
[ -n "${DB_PASSWORD:-}" ] || { echo "ERROR: DB_PASSWORD not found in .keys"; exit 1; }

echo "Provisioning role '$NAME' + ${NAME}_dev / ${NAME}_prod on $HOST ..."
createuser -h "$HOST" -U db_admin "$NAME"
psql -h "$HOST" -U db_admin -d postgres -c "ALTER USER \"$NAME\" WITH PASSWORD '$DB_PASSWORD';"
psql -h "$HOST" -U db_admin -d postgres -c "GRANT \"$NAME\" TO db_admin;"
createdb -h "$HOST" -U db_admin -O "$NAME" "${NAME}_dev"
createdb -h "$HOST" -U db_admin -O "$NAME" "${NAME}_prod"
echo "Done: provisioned $NAME (dev + prod) on $HOST."
