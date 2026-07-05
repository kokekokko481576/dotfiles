#!/usr/bin/env bash
# =============================================================
# validate.sh — docker-compose.yml の構文チェック
# 使い方: cd ~/dotfiles/server && bash scripts/validate.sh
# 変更を適用する前（update.sh実行前）に走らせる
# =============================================================
set -euo pipefail

SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SERVER_DIR"

echo "=== docker-compose.yml 構文チェック ==="
sudo docker compose config --quiet && echo "[OK] 構文エラーなし"
