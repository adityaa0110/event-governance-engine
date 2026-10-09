#!/bin/sh
# Restore the newest backup into a temporary database and read it back.
set -eu
restore_db="${RESTORE_DATABASE:-governance_restore}"
newest=$(ls -1t /backups/governance-*.sql /backups/governance-*.sql.enc 2>/dev/null | head -n 1)
if [ -z "${newest:-}" ]; then
  echo "No backup found in /backups" >&2
  exit 1
fi
sql="$newest"
if [ "${newest%.enc}" != "$newest" ]; then
  sql="/tmp/governance-restore.sql"
  openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_PASSPHRASE -in "$newest" -out "$sql"
fi
psql -h "${PGHOST:-postgres}" -U "${PGUSER:-governance}" -d postgres -c "DROP DATABASE IF EXISTS ${restore_db}"
psql -h "${PGHOST:-postgres}" -U "${PGUSER:-governance}" -d postgres -c "CREATE DATABASE ${restore_db}"
psql -h "${PGHOST:-postgres}" -U "${PGUSER:-governance}" -d "$restore_db" -f "$sql" >/dev/null
count=$(psql -h "${PGHOST:-postgres}" -U "${PGUSER:-governance}" -d "$restore_db" -tAc "SELECT COUNT(*) FROM events")
echo "Restored ${count} events into ${restore_db}"
psql -h "${PGHOST:-postgres}" -U "${PGUSER:-governance}" -d postgres -c "DROP DATABASE IF EXISTS ${restore_db}"
echo "Restore check passed"
