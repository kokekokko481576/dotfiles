# --- Main .zshrc ---
# This file is managed by dotfiles.

# P10k instant prompt
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# Prezto init
if [[ -s "${ZDOTDIR:-$HOME}/.zprezto/init.zsh" ]]; then
  source "${ZDOTDIR:-$HOME}/.zprezto/init.zsh"
fi

# --- Load Configs from ~/.config/zsh/conf.d/ ---
# 読み込み順序を制御するためにファイル名順でロードするよ
CONF_DIR="$HOME/.config/zsh/conf.d"
if [ -d "$CONF_DIR" ]; then
    for config_file in "$CONF_DIR"/*.zsh; do
        [ -r "$config_file" ] && source "$config_file"
    done
fi

# --- Local Config (Not managed by git) ---
# このPC固有の設定（他と共有したくないもの）はここに入れてね！
[ -f ~/.zshrc.local ] && source ~/.zshrc.local

# P10k theme
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

# FZF
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh