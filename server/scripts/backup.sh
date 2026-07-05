#!/usr/bin/env bash
# =============================================================
# backup.sh — resticによるローカル暗号化バックアップ
# 使い方: cd ~/dotfiles/server && bash scripts/backup.sh
#
# バックアップ先: /mnt/data/backup/restic-repo（同一ディスク内。
# 別ディスク・オフサイトへのコピーは別途検討すること＝3-2-1の
# 「1」はまだ満たしていない）
# =============================================================
set -euo pipefail

SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SERVER_DIR"

source .env
export RESTIC_PASSWORD RESTIC_REPOSITORY

DUMP_DIR="/mnt/data/backup/db-dumps"
mkdir -p "$DUMP_DIR"

echo "=== [1/3] PostgreSQL(Immich)のダンプ ==="
docker exec immich_postgres pg_dump -U "${DB_USERNAME:-immich}" "${DB_DATABASE_NAME:-immich}" \
  > "$DUMP_DIR/immich_latest.sql"
echo "  -> $DUMP_DIR/immich_latest.sql ($(du -h "$DUMP_DIR/immich_latest.sql" | cut -f1))"

echo "=== [2/3] resticバックアップ実行 ==="
restic backup \
  /mnt/data/photos \
  /mnt/data/documents \
  /mnt/data/immich \
  /mnt/data/ai \
  /mnt/data/backup/db-dumps \
  /var/lib/docker/volumes/server_openwebui-data/_data \
  /var/lib/docker/volumes/server_uptime-kuma-data/_data \
  "$SERVER_DIR/.env" \
  --exclude-caches \
  --tag daily

echo "=== [3/3] 古いスナップショットの整理（7日/4週/6ヶ月保持） ==="
restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune

echo ""
echo "=== 完了 ==="
restic snapshots --last
