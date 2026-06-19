#!/bin/bash
DOTFILES_DIR=$(cd "$(dirname "$0")"; pwd)
source "$DOTFILES_DIR/lib/utils.sh"

log_info "今のPCの設定を dotfiles リポジトリに吸い出します..."

# 1. VSCode の設定を吸い出す
VSCODE_CONFIG_DIR="$HOME/.config/Code/User"
if [ -d "$VSCODE_CONFIG_DIR" ]; then
    log_info "Updating VSCode settings..."
    cp "$VSCODE_CONFIG_DIR/settings.json" "$DOTFILES_DIR/vscode/"
    cp -r "$VSCODE_CONFIG_DIR/snippets" "$DOTFILES_DIR/vscode/"

    # 拡張機能リストを更新
    if command -v code >/dev/null 2>&1; then
        code --list-extensions > "$DOTFILES_DIR/vscode/extensions.txt"
        log_success "Updated VSCode extensions list."
    fi
fi

# 2. Neovim の設定を吸い出す
# (もし ~/.config/nvim がシンボリックリンクじゃない場合だけコピーする)
if [ -d "$HOME/.config/nvim" ] && [ ! -L "$HOME/.config/nvim" ]; then
    log_info "Updating Neovim config (direct copy)..."
    cp -r "$HOME/.config/nvim/"* "$DOTFILES_DIR/config/nvim/"
fi

# 3. Zshの設定はすでに分割済みなので、
# 必要に応じて ~/.zshrc.local などから共通化したいものを exports.zsh とかに追加してね！

log_success "吸い出し完了！ git status で変更を確認してみてね✨"