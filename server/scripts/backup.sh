#!/usr/bin/env bash
# =============================================================
# backup.sh — resticによるローカル暗号化バックアップ
# 使い方: cd ~/dotfiles/server && bash scripts/backup.sh
#
# バックアップ先: /mnt/data/backup/restic-repo（同一ディスク内。
# 別ディスク・オフサイトへのコピーは別途検討すること＝3-2-1の
# 「1」はまだ満たしていない）
# =============================================================
set -uo pipefail

SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SERVER_DIR"

source .env
export RESTIC_PASSWORD RESTIC_REPOSITORY

DUMP_DIR="/mnt/data/backup/db-dumps"
STAGING_DIR="/mnt/data/backup/docker-volumes-staging"
mkdir -p "$DUMP_DIR" "$STAGING_DIR"

echo "=== [1/4] PostgreSQL(Immich)のダンプ ==="
docker exec immich_postgres pg_dump -U "${DB_USERNAME:-immich}" "${DB_DATABASE_NAME:-immich}" \
  > "$DUMP_DIR/immich_latest.sql" || { echo "!! pg_dump失敗、中断"; exit 1; }
echo "  -> $DUMP_DIR/immich_latest.sql ($(du -h "$DUMP_DIR/immich_latest.sql" | cut -f1))"

echo "=== [2/4] Dockerボリュームをステージング領域へコピー ==="
# /var/lib/docker/volumes は root所有で一般ユーザーから読めないため、
# 一時コンテナ経由でkokkoユーザーが読める場所にコピーしてからresticに渡す
for vol in server_openwebui-data server_uptime-kuma-data; do
  dest="$STAGING_DIR/$vol"
  mkdir -p "$dest"
  docker run --rm \
    -v "${vol}:/src:ro" \
    -v "${dest}:/dest" \
    alpine sh -c "cp -a /src/. /dest/" \
    || { echo "!! ${vol}のステージングに失敗、中断"; exit 1; }
done
echo "  -> $STAGING_DIR ($(du -sh "$STAGING_DIR" | cut -f1))"

echo "=== [3/4] resticバックアップ実行 ==="
restic backup \
  /mnt/data/photos \
  /mnt/data/documents \
  /mnt/data/immich \
  /mnt/data/ai \
  /mnt/data/backup/db-dumps \
  "$STAGING_DIR" \
  "$SERVER_DIR/.env" \
  --exclude-caches \
  --tag daily
RESTIC_EXIT=$?

if [ "$RESTIC_EXIT" -eq 0 ]; then
  echo "  -> 全ファイル正常にバックアップ完了"
elif [ "$RESTIC_EXIT" -eq 3 ]; then
  echo "  -> 警告: 一部ファイルが読み込めませんでした（ディスク不良セクタ等の可能性）。"
  echo "     スナップショット自体は保存されています。詳細は上記のerror行を確認してください。"
else
  echo "!! restic backupが異常終了(exit ${RESTIC_EXIT})、整理処理はスキップします"
  exit "$RESTIC_EXIT"
fi

echo "=== [4/4] 古いスナップショットの整理（7日/4週/6ヶ月保持） ==="
restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune

echo ""
echo "=== 完了 ==="
restic snapshots --last
