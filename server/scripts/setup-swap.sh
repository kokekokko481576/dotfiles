#!/usr/bin/env bash
# =============================================================
# setup-swap.sh — swapファイルの作成（OOM Killer対策）
# 使い方: cd ~/dotfiles/server && bash scripts/setup-swap.sh
#
# RAM 7.1GBに対しDocker全サービス合計で約4.5GB程度使う見積もりのため、
# 突発的なメモリスパイク時にOOM Killerでプロセスが落とされるのを防ぐ。
# 実行前に必ず内容を確認すること。/etc/fstab に1行追加される。
# =============================================================
set -euo pipefail

SWAP_FILE="/swapfile"
SWAP_SIZE="8G"

if [[ -f "$SWAP_FILE" ]]; then
  echo "[!] $SWAP_FILE は既に存在します。何もしません。"
  exit 0
fi

if swapon --show | grep -q .; then
  echo "[!] 既に有効なswapがあります:"
  swapon --show
  echo "続行する場合はこのチェックを外してください。"
  exit 1
fi

echo "[*] ${SWAP_SIZE} のswapファイルを作成..."
sudo fallocate -l "$SWAP_SIZE" "$SWAP_FILE"
sudo chmod 600 "$SWAP_FILE"
sudo mkswap "$SWAP_FILE"
sudo swapon "$SWAP_FILE"

echo "[*] /etc/fstab に追記..."
if ! grep -q "^$SWAP_FILE" /etc/fstab; then
  echo "$SWAP_FILE none swap sw 0 0" | sudo tee -a /etc/fstab
fi

echo ""
echo "=== 完了 ==="
free -h
