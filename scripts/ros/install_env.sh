#!/bin/bash
#
# ROS環境お引越しスクリプト
#
set -e
SCRIPT_DIR=$(cd "$(dirname "$0")"; pwd)
DOTFILES_DIR=$(dirname "$(dirname "$SCRIPT_DIR")") # ../../

echo "🚀 新しいPCにROS環境をセットアップするよ！"
echo "   (Root: $DOTFILES_DIR)"
echo "----------------------------------------"

# --- 1. ROSの基本とビルドツールをインストール ---
echo "STEP 1/5: ROSの基本とビルドツールをインストール中..."
# エラー無視設定を追加（apt updateがこけることがあるため）
sudo apt update || echo "⚠️ apt update failed, continuing..."
sudo apt install -y ros-humble-desktop-full ros-dev-tools
echo "👍 STEP 1完了！"
echo ""

# --- 2. APTパッケージのインストール ---
echo "STEP 2/5: 追加のROSパッケージをインストール中..."
APT_LIST="$SCRIPT_DIR/apt_packages.txt"
if [ -f "$APT_LIST" ]; then
  # パッケージ名だけを抽出してインストール
  sed 's|/.*||' "$APT_LIST" | xargs sudo apt install -y
else
  echo "⚠️ $APT_LIST が見つからないからスキップするね。"
fi
echo "👍 STEP 2完了！"
echo ""

# --- 3. Pythonパッケージのインストール ---
echo "STEP 3/5: Pythonパッケージをインストール中..."
PIP_LIST="$SCRIPT_DIR/python_packages.txt"
if [ -f "$PIP_LIST" ]; then
  pip install -r "$PIP_LIST"
else
  echo "⚠️ $PIP_LIST が見つからないからスキップするね。"
fi
echo "👍 STEP 3完了！"
echo ""

# --- 4. ROSワークスペースの復元 ---
echo "STEP 4/5: ROSワークスペースを復元中..."
ARCHIVE_FILE="$DOTFILES_DIR/azimuth_project_src.tar.gz"
if [ -f "$ARCHIVE_FILE" ]; then
  mkdir -p $HOME/ros2_workspaces/azimuth_project/src
  tar -xzvf "$ARCHIVE_FILE" -C $HOME/ros2_workspaces/azimuth_project/
else
  echo "⚠️ $ARCHIVE_FILE が見つからないからスキップするね。"
fi
echo "👍 STEP 4完了！"
echo ""

# --- 5. ビルド ---
echo "STEP 5/5: ワークスペースの依存関係解決とビルド..."
if [ -d "$HOME/ros2_workspaces/azimuth_project" ]; then
  cd $HOME/ros2_workspaces/azimuth_project
  sudo rosdep init || echo "rosdep init は実行済みかも。"
  rosdep update
  rosdep install --from-paths src -y --ignore-src
  colcon build
else
    echo "⚠️ ワークスペースが見つからないのでビルドをスキップ。"
fi
echo "👍 STEP 5完了！"
echo ""

echo "----------------------------------------"
echo "🎉 ROS環境セットアップ完了！ 🎉"
echo "続けて、その他の設定（Zsh, Neovim等）を行うには以下を実行してね："
echo "  $DOTFILES_DIR/install.sh"