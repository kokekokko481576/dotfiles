#!/bin/bash
source "$(dirname "$0")/../lib/utils.sh"

log_info "Setting up Neovim..."

# Neovimの最新版をPPAからインストール
if ! nvim --version | grep -q 'v0\.\(1[0-9]\|[7-9]\)'; then
    log_info "Updating Neovim to a newer version via PPA..."
    sudo add-apt-repository ppa:neovim-ppa/unstable -y
    sudo apt update
    sudo apt install neovim ripgrep -y
else
    log_info "Neovim version is already sufficient."
fi

# nvimディレクトリのリンク
create_safe_link "$HOME/dotfiles/config/nvim" "$HOME/.config/nvim"

log_success "Neovim setup complete!"
