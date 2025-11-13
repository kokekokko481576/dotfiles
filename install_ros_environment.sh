#!/bin/bash
#
# ROS環境お引越しスクリプト（新しいPCで実行する用）
#
# 実行する前に、新しいPCで `git pull` して、この dotfiles リポジトリを
# 最新の状態にしておいてね！
#

set -e # エラーが起きたらすぐにスクリプトを停止するおまじない
DOTFILES_DIR="$HOME/dotfiles"

echo "🚀 新しいPCにROS環境をセットアップするよ！"
echo "   ($DOTFILES_DIR からファイルを参照するよ)"
echo "----------------------------------------"

# --- 1. ROSの基本とビルドツールをインストール ---
echo "STEP 1/6: ROSの基本とビルドツールをインストール中..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y ros-humble-desktop-full ros-dev-tools
echo "👍 STEP 1完了！"
echo ""

# --- 2. APTパッケージのインストール ---
echo "STEP 2/6: 追加のROSパッケージをインストール中..."
if [ -f "$DOTFILES_DIR/ros_apt_packages.txt" ]; then
  # パッケージ名だけを抽出してインストール
  sed 's|/.*||' "$DOTFILES_DIR/ros_apt_packages.txt" | xargs sudo apt install -y
else
  echo "⚠️ $DOTFILES_DIR/ros_apt_packages.txt が見つからないからスキップするね。"
fi
echo "👍 STEP 2完了！"
echo ""

# --- 3. Pythonパッケージのインストール ---
echo "STEP 3/6: Pythonパッケージをインストール中..."
if [ -f "$DOTFILES_DIR/python_packages.txt" ]; then
  pip install -r "$DOTFILES_DIR/python_packages.txt"
else
  echo "⚠️ $DOTFILES_DIR/python_packages.txt が見つからないからスキップするね。"
fi
echo "👍 STEP 3完了！"
echo ""

# --- 4. ROSワークスペースの復元 ---
echo "STEP 4/6: ROSワークスペースを復元中..."
if [ -f "$DOTFILES_DIR/azimuth_project_src.tar.gz" ]; then
  mkdir -p $HOME/ros2_workspaces/azimuth_project/src
  tar -xzvf "$DOTFILES_DIR/azimuth_project_src.tar.gz" -C $HOME/ros2_workspaces/azimuth_project/
else
  echo "⚠️ $DOTFILES_DIR/azimuth_project_src.tar.gz が見つからないからスキップするね。"
fi
echo "👍 STEP 4完了！"
echo ""

# --- 5. ワークスペースの依存関係インストールとビルド ---
echo "STEP 5/6: ワークスペースの依存関係をインストールしてビルドするよ！"
if [ -d "$HOME/ros2_workspaces/azimuth_project" ]; then
  cd $HOME/ros2_workspaces/azimuth_project
  # rosdep initは失敗することがあるので、sudoをつけて実行し、失敗しても続ける
  sudo rosdep init || echo "rosdep init はもう実行済みかも。処理を続けるね！"
  rosdep update
  rosdep install --from-paths src -y --ignore-src
  colcon build
else
    echo "⚠️ ワークスペースのディレクトリが見つからないのでビルドをスキップします。"
fi
echo "👍 STEP 5完了！"
echo ""

# --- 6. シェルの設定 ---
echo "STEP 6/6: dotfilesのセットアップを実行してシェルの設定を更新するよ！"
if [ -f "$DOTFILES_DIR/setup.sh" ]; then
  cd $DOTFILES_DIR
  ./setup.sh
else
    echo "⚠️ $DOTFILES_DIR/setup.sh が見つからないみたい。この手順は手動でやってね！"
fi
echo "👍 STEP 6完了！"
echo ""

# --- 完了メッセージ ---
echo "----------------------------------------"
echo "🎉🎉🎉 セットアップ完了！ 🎉🎉🎉"
echo "おつかれさま！ 新しいターミナルを開いて、エラーが出ないか確認してみてね！"
echo "もし colcon build でエラーが出てたら、そのメッセージを教えてくれると助かる！"
