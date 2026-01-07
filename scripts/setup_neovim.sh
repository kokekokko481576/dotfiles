#!/bin/bash
source "$(dirname "$0")/../lib/utils.sh"

log_info "Setting up Neovim..."

# nvimディレクトリのリンク
create_safe_link "$HOME/dotfiles/config/nvim" "$HOME/.config/nvim"

log_success "Neovim setup complete!"
