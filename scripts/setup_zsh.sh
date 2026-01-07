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

# 2. シンボリックリンクの作成
create_safe_link "$HOME/dotfiles/zsh/.zshrc" "$HOME/.zshrc"
create_safe_link "$HOME/dotfiles/zsh/.zpreztorc" "$HOME/.zpreztorc"
create_safe_link "$HOME/dotfiles/zsh/.p10k.zsh" "$HOME/.p10k.zsh"

log_success "Zsh setup complete!"
