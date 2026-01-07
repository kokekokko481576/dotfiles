#!/bin/bash
source "$(dirname "$0")/../lib/utils.sh"

log_info "Setting up Mozc (Japanese Input)..."

# Linux以外ならスキップ
if [ "$(uname)" != "Linux" ]; then
    log_warn "Mozc setup is only for Linux. Skipping."
    exit 0
fi

# リンク作成
create_safe_link "$HOME/dotfiles/config/mozc" "$HOME/.config/mozc"

log_success "Mozc setup complete!"
echo "再起動後に設定が反映されるよ！"
