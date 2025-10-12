#!/bin/bash
#
# dotfiles setup script
#

DOTFILES_DIR=~/dotfiles

echo "最強の環境構築を開始するぜ！"

# --- リンクするファイルのリスト ---
# 書式: "dotfiles内のパス" "本来あるべき場所のパス"
declare -a link_pairs=(
  "$DOTFILES_DIR/.zshrc"                     "$HOME/.zshrc"
  "$DOTFILES_DIR/.zpreztorc"                 "$HOME/.zpreztorc"
  "$DOTFILES_DIR/.p10k.zsh"                  "$HOME/.p10k.zsh"
  "$DOTFILES_DIR/.gitconfig"                 "$HOME/.gitconfig"
  "$DOTFILES_DIR/config/mozc"                "$HOME/.config/mozc"
  "$DOTFILES_DIR/config/Code/User/settings.json"  "$HOME/.config/Code/User/settings.json"
  "$DOTFILES_DIR/config/Code/User/snippets"      "$HOME/.config/Code/User/snippets"
  "$DOTFILES_DIR/config/user-dirs.dirs"      "$HOME/.config/user-dirs.dirs"
)

# --- ループで一個ずつお掃除＆リンク作成 ---
for i in "${!link_pairs[@]}"; do
  # 2つで1ペアなので、偶数番目だけ処理する
  if (( i % 2 == 0 )); then
    source_path="${link_pairs[i]}"
    link_target="${link_pairs[i+1]}"

    # 1. まず、古いリンクやファイルを強制的に削除 (-fで確認なし！)
    rm -rf "$link_target"

    # 2. 途中のディレクトリがなければ作成
    mkdir -p "$(dirname "$link_target")"
    
    # 3. 新しいリンクを作成！
    ln -s "$source_path" "$link_target"
    
    echo "✅ $link_target をリンクし直したぜ！"
  fi
done

echo ""
echo "💪 全部のリンクを再構築完了！"
echo "次はターミナルを再起動して、魂が受け継がれているか確認しよう！"
