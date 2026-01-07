#!/bin/bash
source "$(dirname "$0")/../lib/utils.sh"

log_info "Setting up Zsh..."

# 1. Preztoのインストール (未導入の場合)
if [ ! -d "$HOME/.zprezto" ]; then
    log_info "Installing Prezto..."
    git clone --recursive https://github.com/sorin-ionescu/prezto.git "${ZDOTDIR:-$HOME}/.zprezto"
else
    log_info "Prezto is already installed."
fi

# 2. 基本的なシンボリックリンクの作成
create_safe_link "$HOME/dotfiles/zsh/.zshrc" "$HOME/.zshrc"
create_safe_link "$HOME/dotfiles/zsh/.zpreztorc" "$HOME/.zpreztorc"
create_safe_link "$HOME/dotfiles/zsh/.p10k.zsh" "$HOME/.p10k.zsh"

# 3. 分割設定ファイルのリンク（conf.d方式）
CONF_DIR="$HOME/.config/zsh/conf.d"
DOTFILES_ZSH="$HOME/dotfiles/zsh"
mkdir -p "$CONF_DIR"

log_info "Configuring Zsh plugins in $CONF_DIR ..."

# --- 必須設定（常に有効） ---
create_safe_link "$DOTFILES_ZSH/exports.zsh" "$CONF_DIR/00_exports.zsh"
create_safe_link "$DOTFILES_ZSH/aliases.zsh" "$CONF_DIR/10_aliases.zsh"

# --- 選択的設定（質問する） ---

# ROS
if ask_yes_no "ROS (Robot Operating System) の設定を有効にしますか？"; then
    create_safe_link "$DOTFILES_ZSH/ros.zsh" "$CONF_DIR/20_ros.zsh"
else
    if [ -L "$CONF_DIR/20_ros.zsh" ]; then
        rm "$CONF_DIR/20_ros.zsh"
        log_info "ROS設定を無効化しました。"
    fi
fi

# Google Cloud SDK
if ask_yes_no "Google Cloud SDK の設定を有効にしますか？"; then
    create_safe_link "$DOTFILES_ZSH/google_cloud.zsh" "$CONF_DIR/90_google_cloud.zsh"
else
    if [ -L "$CONF_DIR/90_google_cloud.zsh" ]; then
        rm "$CONF_DIR/90_google_cloud.zsh"
        log_info "Google Cloud設定を無効化しました。"
    fi
fi

# 4. デフォルトシェルの変更 (自動)
TARGET_SHELL=$(which zsh)
CURRENT_SHELL=$(getent passwd $USER | cut -d: -f7)

if [ "$CURRENT_SHELL" != "$TARGET_SHELL" ]; then
    echo ""
    log_info "デフォルトシェルを Zsh ($TARGET_SHELL) に変更します..."
    log_info "パスワードを求められる場合があります👇"
    
    if chsh -s "$TARGET_SHELL"; then
        log_success "デフォルトシェルを Zsh に変更しました！"
    else
        log_error "シェルの変更に失敗しました。後で 'chsh -s \$(which zsh)' を試してね。"
    fi
else
    log_info "デフォルトシェルは既に Zsh です。"
fi

log_success "Zsh setup complete!"
