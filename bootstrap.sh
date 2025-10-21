#!/bin/bash
set -e

echo "🚀 最強の環境構築（ハイブリッド型）を開始するぜ！"

# --- 1. 必要なアプリをインストールする ---
echo "--- STEP 1: 必要なアプリをインストール中... ---"
# apt updateのエラーはスルーする
sudo apt update || echo "⚠️ apt update に一部エラーがありましたが、処理を続行します。"
sudo apt install -y git zsh curl

# (WSL判定もそのまま残しておくよ)
if ! grep -qi "microsoft" /proc/version; then
  echo "--- [追加] Linux専用アプリをインストール中... ---"
fi

# --- 2. dotfilesリポジトリをダウンロード ---
if [ ! -d "$HOME/dotfiles" ]; then
  echo "--- STEP 2: GitHubから君の魂(dotfiles)をダウンロード中... ---"
  git clone https://github.com/kokekokko481576/dotfiles.git "$HOME/dotfiles"
else
  echo "--- STEP 2: dotfilesは既に存在するみたいだね！OK！ ---"
fi

# --- 3. Prezto(zshの本体)をインストール ---
if [ ! -d "$HOME/.zprezto" ]; then
  echo "--- STEP 3: zshを最強にするPreztoをインストール中... ---"
  git clone --recursive https://github.com/sorin-ionescu/prezto.git "${ZDOTDIR:-$HOME}/.zprezto"
else
  echo "--- STEP 3: Preztoは既にインストール済みだね！OK！ ---"
fi

# --- 4. ★最強のハイブリッド.zshrcを自動生成★ ---
echo "--- STEP 4: 相手の.bashrcと君の設定を合体させて、最強の.zshrcを生成中... ---"
bash "$HOME/dotfiles/setup.sh"

# --- 5. デフォルトシェルをzshに変更する ---
echo "--- STEP 5: これからの相棒をzshに変更するぜ！ ---"
if [ ! "$SHELL" = "$(which zsh)" ]; then
  chsh -s "$(which zsh)"
  echo "パスワードを求められたかも！"
else
  echo "シェルは既にzshだね！OK！"
fi

echo ""
echo "🎉 全てのセットアップが完了したよ！🎉"
echo "PCを再起動するか、一度ログアウトして、新しい世界を楽しんでくれ！"