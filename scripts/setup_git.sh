#!/bin/bash
DOTFILES_DIR=$(cd "$(dirname "$0")/../"; pwd)
source "$DOTFILES_DIR/lib/utils.sh"

log_info "Setting up Git..."

create_safe_link "$DOTFILES_DIR/git/.gitconfig" "$HOME/.gitconfig"

log_warn "git/.gitconfig の [user] セクションを確認してください。"
log_warn "  git config --global user.name  \"Your Name\""
log_warn "  git config --global user.email \"your@email.com\""

log_success "Git setup complete!"
