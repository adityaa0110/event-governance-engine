#!/bin/sh
set -eu
mkdir -p /backups
stamp=$(date +%Y%m%d%H%M%S)
plain="/backups/governance-${stamp}.sql"
if ! pg_dump -h "${PGHOST:-postgres}" -U "${PGUSER:-governance}" "${PGDATABASE:-governance}" > "$plain"; then
  status=$?
  if [ -n "${BACKUP_ALERT_WEBHOOK:-}" ]; then
    wget -q -O- --header 'Content-Type: application/json' \
      --post-data "{\"alert\":\"Postgres backup failed\",\"service\":\"event-governance-engine\"}" \
      "$BACKUP_ALERT_WEBHOOK" || true
  fi
  exit "$status"
fi
target="$plain"
if [ -n "${BACKUP_PASSPHRASE:-}" ]; then
  openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_PASSPHRASE -in "$plain" -out "${plain}.enc"
  rm -f "$plain"
  target="${plain}.enc"
fi
if [ -n "${BACKUP_S3_BUCKET:-}" ] && command -v aws >/dev/null 2>&1; then
  aws s3 cp "$target" "s3://${BACKUP_S3_BUCKET}/event-governance/$(basename "$target")"
fi
retention="${BACKUP_RETENTION_DAYS:-14}"
find /backups -type f \( -name 'governance-*.sql' -o -name 'governance-*.sql.enc' \) -mtime +"$retention" -delete
echo "Wrote $target"
