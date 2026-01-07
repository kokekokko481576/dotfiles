#!/bin/bash

# カラー定義
COLOR_RED="\033[31m"
COLOR_GREEN="\033[32m"
COLOR_YELLOW="\033[33m"
COLOR_BLUE="\033[34m"
COLOR_RESET="\033[0m"

log_info() { echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} $1"; }
log_success() { echo -e "${COLOR_GREEN}[OK]${COLOR_RESET} $1"; }
log_warn() { echo -e "${COLOR_YELLOW}[WARN]${COLOR_RESET} $1"; }
log_error() { echo -e "${COLOR_RED}[ERROR]${COLOR_RESET} $1"; }

# --- Root実行チェック ---
# dotfilesのセットアップは一般ユーザーで行うべきものなので、
# root (sudo) で実行された場合は警告して停止する。
if [ "$(id -u)" -eq 0 ]; then
    log_error "⚠️  Do NOT run this script as root (sudo)."
    log_error "   Please run without sudo: ./install.sh"
    log_error "   (The script will ask for sudo password when needed)"
    exit 1
fi

# リンク作成（バックアップ機能付き）
create_safe_link() {
    local src="$1"
    local dest="$2"
    mkdir -p "$(dirname "$dest")"

    if [ -e "$dest" ] && [ ! -L "$dest" ]; then
        log_warn "$dest already exists. Backing up to ${dest}.bak"
        mv "$dest" "${dest}.bak"
    fi

    ln -sf "$src" "$dest"
    log_success "Linked $dest -> $src"
}

# Yes/No 質問関数
# Usage: if ask_yes_no "Question?"; then ... fi
ask_yes_no() {
    local question="$1"
    local default="${2:-y}" # デフォルトは y

    if [ "$default" = "y" ]; then
        prompt="[Y/n]"
    else
        prompt="[y/N]"
    fi

    echo -ne "${COLOR_YELLOW}$question $prompt${COLOR_RESET} "
    read answer

    # Enterのみの場合はデフォルト値
    if [ -z "$answer" ]; then
        answer="$default"
    fi

    # y または Y で始まるなら真(0)を返す
    [[ "$answer" =~ ^[Yy] ]]
}
