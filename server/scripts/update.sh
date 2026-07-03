#!/usr/bin/env bash
# =============================================================
# update.sh — サービス更新スクリプト
# 使い方: cd ~/dotfiles/server && bash scripts/update.sh
# =============================================================
set -euo pipefail

SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SERVER_DIR"

echo "=== サービス更新 ==="
echo "[*] 最新イメージを取得..."
sudo docker compose pull

echo "[*] サービスを再起動..."
sudo docker compose up -d --remove-orphans

echo "[*] 古いイメージを削除..."
sudo docker image prune -f

echo ""
echo "=== 更新完了 ==="
sudo docker compose ps
