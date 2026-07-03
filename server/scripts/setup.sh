#!/usr/bin/env bash
# =============================================================
# setup.sh — 初回セットアップスクリプト
# 使い方: cd ~/dotfiles/server && bash scripts/setup.sh
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== ホームサーバー初回セットアップ ==="

# ---- .env の確認 ----
if [[ ! -f "$SERVER_DIR/.env" ]]; then
  echo "[!] .env ファイルが存在しません。.env.example をコピーして編集してください:"
  echo "    cp $SERVER_DIR/.env.example $SERVER_DIR/.env"
  echo "    nano $SERVER_DIR/.env"
  exit 1
fi

# ---- DB_PASSWORD の確認 ----
source "$SERVER_DIR/.env"
if [[ -z "${DB_PASSWORD:-}" ]]; then
  echo "[!] .env の DB_PASSWORD が未設定です。以下のコマンドで生成できます:"
  echo "    openssl rand -hex 32"
  exit 1
fi

# ---- /mnt/data ディレクトリ確認 ----
echo "[*] /mnt/data ディレクトリを確認..."
sudo mkdir -p /mnt/data/{photos,documents,shared,ai/context,ai/n8n,backup}
sudo chown -R "$(whoami):$(whoami)" /mnt/data

# ---- Samba ユーザー設定 ----
echo "[*] Samba ユーザーを設定..."
echo "Sambaのパスワードを入力してください（SMB接続時に使うパスワード）:"
sudo smbpasswd -a "$(whoami)"

# ---- Docker ネットワーク確認 ----
echo "[*] Docker 確認..."
if ! sudo docker info >/dev/null 2>&1; then
  echo "[!] Docker が起動していません。sudo systemctl start docker"
  exit 1
fi

# ---- サービス起動 ----
echo "[*] サービスを起動..."
cd "$SERVER_DIR"
sudo docker compose up -d

echo ""
echo "=== セットアップ完了 ==="
echo "サービスの状態を確認: sudo docker compose ps"
echo ""
echo "各サービスへのアクセス（Tailscale接続後）:"
echo "  Immich:    http://server:2283"
echo "  OpenWebUI: http://server:3000"
echo "  n8n:       http://server:5678"
echo ""
echo "次のステップ: ~/dotfiles/server/guide/ を参照してください"
