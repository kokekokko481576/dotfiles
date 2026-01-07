#!/bin/bash
source "$(dirname "$0")/../lib/utils.sh"

log_info "Setting up VSCode..."

# VSCode の設定ディレクトリ（Linux用）
VSCODE_CONFIG_DIR="$HOME/.config/Code/User"

if [ ! -d "$VSCODE_CONFIG_DIR" ]; then
    log_warn "VSCode config directory not found at $VSCODE_CONFIG_DIR. Is VSCode installed?"
    mkdir -p "$VSCODE_CONFIG_DIR"
fi

# settings.json と snippets のリンク
create_safe_link "$HOME/dotfiles/vscode/settings.json" "$VSCODE_CONFIG_DIR/settings.json"
create_safe_link "$HOME/dotfiles/vscode/snippets" "$VSCODE_CONFIG_DIR/snippets"

# 拡張機能のインストール
EXT_LIST="$HOME/dotfiles/vscode/extensions.txt"
if [ -f "$EXT_LIST" ]; then
    if command -v code >/dev/null 2>&1; then
        log_info "Installing VSCode extensions..."
        while read line; do
            code --install-extension "$line" --force
        done < "$EXT_LIST"
    else
        log_warn "'code' command not found. Skipping extension installation."
    fi
fi

log_success "VSCode setup complete!"