#!/bin/bash

set -e

echo "🚀 最強の環境構築、全自動で開始するぜ！"

# --- 1. 共通で必要なアプリをインストールする ---
echo "--- STEP 1: 共通アプリをインストール中... ---"
# apt(Debian/Ubuntu), dnf(Fedora), pacman(Arch)のいずれかのパッケージマネージャを検出し、共通アプリをインストール
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y git zsh curl
elif command -v dnf &> /dev/null; then
    sudo dnf install -y git zsh curl
elif command -v pacman &> /dev/null; then
    sudo pacman -Syu --noconfirm git zsh curl
else
    echo "❌ サポートされているパッケージマネージャ(apt, dnf, pacman)が見つかりませんでした。"
    exit 1
fi

# --- もしWSLじゃなかったら、Linux専用アプリもインストール ---
# /proc/version に "microsoft" という文字列が含まれているかでWSL環境かどうかを判定
if ! grep -qi "microsoft" /proc/version; then
  echo "--- [追加] Linux専用アプリをインストール中... ---"
  # ここに将来的にzellijとかfzfとかを追加していくと最強になれる！
  # sudo apt install -y zellij fzf
fi

# --- 2. dotfilesリポジトリをダウンロード (もし無ければ) ---
DOTFILES_DIR="$HOME/dotfiles"
if [ ! -d "$DOTFILES_DIR" ]; then
  echo "--- STEP 2: GitHubから君の魂(dotfiles)をダウンロード中... ---"
  git clone https://github.com/kokekokko481576/dotfiles.git "$DOTFILES_DIR"
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

# --- 4. セットアップスクリプトを実行して、魂をPCに宿らせる --- 
echo "--- STEP 4: 設定ファイルとPCを魂で繋ぐ作業中... ---"
bash "$DOTFILES_DIR/setup.sh"

# --- 5. デフォルトシェルをzshに変更する ---
# chshコマンドで、このユーザーのログインシェルをZshに変更
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