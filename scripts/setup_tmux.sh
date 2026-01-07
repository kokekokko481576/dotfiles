#!/bin/bash
source "$(dirname "$0")/../lib/utils.sh"

log_info "Setting up tmux..."

# リンク作成
create_safe_link "$HOME/dotfiles/tmux/.tmux.conf" "$HOME/.tmux.conf"

log_success "tmux setup complete!"
