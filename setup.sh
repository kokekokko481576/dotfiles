#!/bin/bash

DOTFILES_DIR=~/dotfiles

echo "💪 魂をPCに宿らせるぜ！"

# --- 共通でリンクするファイルのリスト ---
declare -a common_links=(
  "$DOTFILES_DIR/.zshrc"      "$HOME/.zshrc"
  "$DOTFILES_DIR/.zpreztorc"  "$HOME/.zpreztorc"
  "$DOTFILES_DIR/.p10k.zsh"   "$HOME/.p10k.zsh"
  "$DOTFILES_DIR/.gitconfig"  "$HOME/.gitconfig"
)

# --- Linuxだけでリンクするファイルのリスト ---
declare -a linux_only_links=(
  "$DOTFILES_DIR/config/mozc"                "$HOME/.config/mozc"
  "$DOTFILES_DIR/config/Code/User/settings.json"  "$HOME/.config/Code/User/settings.json"
  "$DOTFILES_DIR/config/Code/User/snippets"      "$HOME/.config/Code/User/snippets"
  "$DOTFILES_DIR/config/user-dirs.dirs"      "$HOME/.config/user-dirs.dirs"
)

# --- 共通リンクを実行 ---
for i in "${!common_links[@]}"; do
  if (( i % 2 == 0 )); then
    source_path="${common_links[i]}"
    link_target="${common_links[i+1]}"
    rm -rf "$link_target"
    mkdir -p "$(dirname "$link_target")"
    ln -s "$source_path" "$link_target"
    echo "✅ [共通] $link_target をリンクしたぜ！"
  fi
done

# --- もしWSLじゃなかったら、Linux専用リンクも実行 ---
# /proc/versionに"microsoft"の文字がなければ、普通のLinuxだと判断する
if ! grep -qi "microsoft" /proc/version; then
  echo "---"
  echo "🐧 これは普通のLinuxだね！専用設定を追加するよ！"
  for i in "${!linux_only_links[@]}"; do
    if (( i % 2 == 0 )); then
      source_path="${linux_only_links[i]}"
      link_target="${linux_only_links[i+1]}"
      rm -rf "$link_target"
      mkdir -p "$(dirname "$link_target")"
      ln -s "$source_path" "$link_target"
      echo "✅ [Linux専用] $link_target をリンクしたぜ！"
    fi
  done
else
  echo "---"
  echo "🐧 これはWSLだね！専用設定はスキップするよ。"
fi

echo ""
echo "✨ リンク作業完了！"