#!/bin/bash

set -e

echo "🚀 最強の環境構築、全自動で開始するぜ！"

# --- 1. 共通で必要なアプリをインストールする ---
echo "--- STEP 1: 共通アプリをインストール中... ---"
sudo apt update
sudo apt install -y git zsh curl

# --- もしWSLじゃなかったら、Linux専用アプリもインストール ---
if ! grep -qi "microsoft" /proc/version; then
  echo "--- [追加] Linux専用アプリをインストール中... ---"
  # ここに将来的にzellijとかfzfとかを追加していくと最強になれる！
  # sudo apt install -y zellij fzf
fi

# (ここから下のSTEP 2〜5は変更なし！)

# --- 2. dotfilesリポジトリをダウンロード (もし無ければ) ---
if [ ! -d "$HOME/dotfiles" ]; then
  echo "--- STEP 2: GitHubから君の魂(dotfiles)をダウンロード中... ---"
  git clone https://github.com/kokekokko481576/dotfiles.git "$HOME/dotfiles"
else
  echo "--- STEP 2: dotfilesは既に存在するみたいだね！スキップするよ。 ---"
fi

# --- 3. Prezto(zshの本体)をインストール (もし無ければ) ---
if [ ! -d "$HOME/.zprezto" ]; then
  echo "--- STEP 3: zshを最強にするPreztoをインストール中... ---"
  git clone --recursive https://github.com/sorin-ionescu/prezto.git "${ZDOTDIR:-$HOME}/.zprezto"
else
  echo "--- STEP 3: Preztoは既にインストール済みだね！スキップするよ。 ---"
fi

# --- 4. シンボリックリンクを全部貼る ---
echo "--- STEP 4: 設定ファイルとPCを魂で繋ぐ作業中... ---"
bash "$HOME/dotfiles/setup.sh"

# --- 5. デフォルトシェルをzshに変更する ---
if [ ! "$SHELL" = "$(which zsh)" ]; then
  echo "--- STEP 5: これからの相棒をzshに変更するぜ！ ---"
  chsh -s "$(which zsh)"
  echo "パスワードを求められるかもしれないよ！"
else
  echo "--- STEP 5: シェルは既にzshだね！OK！ ---"
fi

echo ""
echo "🎉 全てのセットアップが完了したよ！🎉"
echo "PCを再起動するか、一度ログアウトして、新しい世界を楽しんでくれ！"