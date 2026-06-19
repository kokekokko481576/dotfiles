#!/bin/bash
DOTFILES_DIR=$(cd "$(dirname "$0")/../"; pwd)
source "$DOTFILES_DIR/lib/utils.sh"

log_info "Setting up tmux..."

create_safe_link "$DOTFILES_DIR/tmux/.tmux.conf" "$HOME/.tmux.conf"

# TPM (Tmux Plugin Manager) のインストール
TPM_DIR="$HOME/.tmux/plugins/tpm"
if [ ! -d "$TPM_DIR" ]; then
    log_info "Installing TPM (Tmux Plugin Manager)..."
    git clone https://github.com/tmux-plugins/tpm "$TPM_DIR"
    log_success "TPM installed! tmux 起動後に prefix + I でプラグインをインストールしてね。"
else
    log_info "TPM is already installed."
fi

log_success "tmux setup complete!"
