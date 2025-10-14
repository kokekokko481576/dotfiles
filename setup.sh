#!/bin/bash

# このスクリプト自身の場所を基準にdotfilesディレクトリの絶対パスを取得
DOTFILES_DIR=$(cd "$(dirname "$0")" && pwd)

echo "💪 魂をPCに宿らせるぜ！"

# --- 共通でリンクするファイルのリスト ---
# source                                  target
declare -a common_links=(
  "$DOTFILES_DIR/zsh/.zshrc"                "$HOME/.zshrc"
  "$DOTFILES_DIR/zsh/.zpreztorc"            "$HOME/.zpreztorc"
  "$DOTFILES_DIR/zsh/.p10k.zsh"             "$HOME/.p10k.zsh"
  "$DOTFILES_DIR/git/.gitconfig"            "$HOME/.gitconfig"
)

# --- Linuxだけでリンクするファイルのリスト ---
# source                                  target
declare -a linux_only_links=(
  "$DOTFILES_DIR/config/mozc"               "$HOME/.config/mozc"
  "$DOTFILES_DIR/vscode/settings.json"      "$HOME/.config/Code/User/settings.json"
  "$DOTFILES_DIR/vscode/snippets"           "$HOME/.config/Code/User/snippets"
  "$DOTFILES_DIR/config/user-dirs.dirs"     "$HOME/.config/user-dirs.dirs"
)

# --- リンク作成関数 ---
# 古い設定ファイルやディレクトリが存在する場合に備えて、一度削除してからシンボリックリンクを作成する
create_link() {
  local source_path="$1"
  local link_target="$2"
  rm -rf "$link_target"
  mkdir -p "$(dirname "$link_target")"
  ln -s "$source_path" "$link_target"
  echo "✅ $link_target をリンクしたぜ！"
}

# --- 共通リンクを実行 ---
echo "--- [共通] 設定をリンク中... ---"
for i in "${!common_links[@]}"; do
  if (( i % 2 == 0 )); then
    create_link "${common_links[i]}" "${common_links[i+1]}"
  fi
done

# --- OS固有の処理 ---
# /proc/version に "microsoft" という文字列が含まれているかでWSL環境かどうかを判定
if ! grep -qi "microsoft" /proc/version; then
  echo "--- [Linux専用] 設定を追加するよ！ ---"
  # Linux専用リンクを実行
  for i in "${!linux_only_links[@]}"; do
    if (( i % 2 == 0 )); then
      create_link "${linux_only_links[i]}" "${linux_only_links[i+1]}"
    fi
  done

  # dconf設定を復元 (GNOMEなどのデスクトップ設定)
  if command -v dconf &> /dev/null && [ -f "$DOTFILES_DIR/dconf_settings.txt" ]; then
    echo "--- [Linux専用] dconf設定を復元中... ---"
    dconf load / < "$DOTFILES_DIR/dconf_settings.txt"
    echo "✅ dconf設定の復元完了！"
  else
    echo "⚠️ dconfコマンドが見つからないか、dconf_settings.txtが存在しないため、設定の復元をスキップします。"
  fi
else
  echo "--- [WSL] 専用設定はスキップするよ。 ---"
fi

# --- VSCodeの拡張機能をインストール ---
# vscode_extensions.txt を1行ずつ読み込み、空行と # で始まるコメント行を無視して拡張機能をインストール
if command -v code &> /dev/null && [ -f "$DOTFILES_DIR/vscode_extensions.txt" ]; then
    echo "--- VSCodeの拡張機能をインストール中... ---"
    # 最終行に改行がなくても読み込めるように `|| [[ -n $extension ]]` を追加
    while read -r extension || [[ -n "$extension" ]]; do
        if [[ ! "$extension" =~ ^# && -n "$extension" ]]; then
            code --install-extension "$extension"
        fi
    done < "$DOTFILES_DIR/vscode_extensions.txt"
    echo "✅ VSCode拡張機能のインストール完了！"
else
    echo "⚠️ codeコマンドが見つからないか、vscode_extensions.txtが存在しないため、VSCode拡張機能のインストールをスキップします。"
fi


echo ""
echo "✨ リンク・設定作業完了！"