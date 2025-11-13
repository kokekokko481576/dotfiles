#!/bin/bash
#
# ROS環境お引越し準備スクリプト
# 古い（動いてる）PCで実行してね！
#
# --- 新しいPCでの作業手順 ---
#
# 1. **ROSの基本とビルドツールをインストール**
#    sudo apt update && sudo apt upgrade -y
#    sudo apt install -y ros-humble-desktop-full ros-dev-tools
#
# 2. **このスクリプトが作ったファイルたちを新しいPCのホームディレクトリにコピー**
#
# 3. **APTパッケージのインストール**
#    (ros_apt_packages.txt を使って、リストにあるパッケージを全部入れる)
#    cat ros_apt_packages.txt | sed 's|/.*||' | xargs sudo apt install -y
#
# 4. **Pythonパッケージのインストール**
#    pip install -r python_packages.txt
#
# 5. **ROSワークスペースの復元とビルдo**
#    mkdir -p ~/ros2_workspaces/azimuth_project/src
#    tar -xzvf azimuth_project_src.tar.gz -C ~/ros2_workspaces/azimuth_project/
#    cd ~/ros2_workspaces/azimuth_project
#    rosdep init
#    rosdep update
#    rosdep install --from-paths src -y --ignore-src
#    colcon build
#
# 6. **シェルの設定**
#    (dotfilesのセットアップを再実行して、新しいワークスペースを認識させる)
#    cd ~/dotfiles
#    ./setup.sh
#
# 7. **最後に**
#    新しいターミナルを開いて、エラーが出ないか確認！
#    もし `colcon build` でエラーが出たら、エラーメッセージを教えてね！
#
# ----------------------------------------------------

echo "🚚 ROS環境のお引越し準備を始めるよ！"
echo "----------------------------------------"

# --- 1. APTでインストールしたROSパッケージのリストを保存 ---
echo "✅ APTで入れたROSパッケージのリストを ros_apt_packages.txt に保存中..."
apt list --installed 2>/dev/null | grep 'ros-humble-' > ros_apt_packages.txt
echo "👍 保存完了！"
echo ""

# --- 2. pipでインストールしたPythonパッケージのリストを保存 ---
echo "✅ pipで入れたPythonパッケージのリストを python_packages.txt に保存中..."
pip freeze > python_packages.txt
echo "👍 保存完了！"
echo ""

# --- 3. azimuth_project ワークスペースを圧縮 ---
# ユーザーのホームディレクトリにあることを想定
AZIMUTH_WS_PATH="$HOME/ros2_workspaces/azimuth_project"
if [ -d "$AZIMUTH_WS_PATH/src" ]; then
  echo "✅ 'azimuth_project' の 'src' フォルダを azimuth_project_src.tar.gz に圧縮中..."
  tar -czvf azimuth_project_src.tar.gz -C "$AZIMUTH_WS_PATH" src
  echo "👍 圧縮完了！"
else
  echo "⚠️ ワークスペースが見つからないみたい: $AZIMUTH_WS_PATH"
  echo "    azimuth_projectの圧縮はスキップするね。"
fi
echo ""

# --- 4. 完了メッセージ ---
echo "----------------------------------------"
echo "🎉 準備完了！"
echo "このフォルダにできた3つのファイルを新しいPCに持っていってね:"
echo "  - ros_apt_packages.txt"
echo "  - python_packages.txt"
echo "  - azimuth_project_src.tar.gz"
echo ""
echo "新しいPCでの作業手順は、このスクリプトの最初のほうのコメントに書いておいたから、それに従って進めてね！"
