#!/bin/bash
#
# setup_neovim.sh: Neovimの環境をセットアップするスクリプト
#

DOTFILES_DIR=~/dotfiles

create_safe_link() {
  source_path=$1
  link_target=$2
  mkdir -p "$(dirname "$link_target")"
  if [ -e "$link_target" ] && [ ! -L "$link_target" ]; then
    echo "⚠️ $link_target を $link_target.bak にバックアップします。"
    mv "$link_target" "$link_target.bak"
  fi
  rm -f "$link_target"
  ln -s "$source_path" "$link_target"
  echo "✅ $link_target をリンクしました！"
}

echo "--- Neovimの設定をリンク中... ---"
create_safe_link "$DOTFILES_DIR/config/nvim" "$HOME/.config/nvim"
echo "✨ Neovimのリンク作業完了！"
