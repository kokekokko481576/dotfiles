#!/bin/bash
#
# ROS環境お引越し準備スクリプト
#
set -e
SCRIPT_DIR=$(cd "$(dirname "$0")"; pwd)
DOTFILES_DIR=$(dirname "$(dirname "$SCRIPT_DIR")")

echo "🚚 ROS環境のお引越し準備を始めるよ！"
echo "   (Output: $DOTFILES_DIR)"
echo "----------------------------------------"

# --- 1. APTパッケージリスト保存 ---
OUTPUT_APT="$SCRIPT_DIR/apt_packages.txt"
echo "✅ ROSパッケージリストを保存中: $OUTPUT_APT"
apt list --installed 2>/dev/null | grep 'ros-humble-' > "$OUTPUT_APT"

# --- 2. Pythonパッケージリスト保存 ---
OUTPUT_PIP="$SCRIPT_DIR/python_packages.txt"
echo "✅ Pythonパッケージリストを保存中: $OUTPUT_PIP"
pip freeze > "$OUTPUT_PIP"

# --- 3. ワークスペース圧縮 ---
# アーカイブはdotfilesルートに保存
OUTPUT_TAR="$DOTFILES_DIR/azimuth_project_src.tar.gz"
AZIMUTH_WS_PATH="$HOME/ros2_workspaces/azimuth_project"

if [ -d "$AZIMUTH_WS_PATH/src" ]; then
  echo "✅ 'azimuth_project/src' を圧縮中: $OUTPUT_TAR"
  tar -czvf "$OUTPUT_TAR" -C "$AZIMUTH_WS_PATH" src
  echo "👍 圧縮完了！"
else
  echo "⚠️ ワークスペースが見つからないのでスキップ: $AZIMUTH_WS_PATH"
fi

echo "----------------------------------------"
echo "🎉 準備完了！"
echo "Gitで変更を確認してコミットしてね！"