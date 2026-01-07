# --- Main .zshrc ---
# This file is managed by dotfiles.
# Any machine-specific changes should be added to ~/.zshrc.local

# P10k instant prompt
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# Prezto init
if [[ -s "${ZDOTDIR:-$HOME}/.zprezto/init.zsh" ]]; then
  source "${ZDOTDIR:-$HOME}/.zprezto/init.zsh"
fi

# Load split configs from dotfiles
DOTFILES_ZSH="$HOME/dotfiles/zsh"
[ -f "$DOTFILES_ZSH/exports.zsh" ]      && source "$DOTFILES_ZSH/exports.zsh"
[ -f "$DOTFILES_ZSH/aliases.zsh" ]      && source "$DOTFILES_ZSH/aliases.zsh"
[ -f "$DOTFILES_ZSH/ros.zsh" ]          && source "$DOTFILES_ZSH/ros.zsh"
[ -f "$DOTFILES_ZSH/google_cloud.zsh" ] && source "$DOTFILES_ZSH/google_cloud.zsh"

# --- Local Config (Not managed by git) ---
# このPC固有の設定（他と共有したくないもの）はここに入れてね！
[ -f ~/.zshrc.local ] && source ~/.zshrc.local

# P10k theme
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

# FZF
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh
