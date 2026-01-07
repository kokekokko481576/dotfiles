# dotfiles

作業環境を再現するための設定ファイル（dotfiles）リポジトリです。
PCごとの差異を吸収しつつ、必要な設定を選んでインストールできる設計になっています。

## 概要

このリポジトリには、主に以下のツールの設定ファイルが含まれています。

- **Zsh**: Prezto + Powerlevel10k をベースにした最強のシェル環境
- **Neovim**: Luaベースのモダンな設定（LazyVimライクな構成）
- **VSCode**: `settings.json`, スニペット, 拡張機能リスト
- **LaTeX**: `.latexmkrc` などのビルド設定
- **Git**: 基本的なエイリアスとユーザー設定
- **ROS 2**: 環境構築・移行用のスクリプトとパッケージリスト

## 🚀 セットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/kokekokko481576/dotfiles.git ~/dotfiles
cd ~/dotfiles
```

### 2. インストール（対話形式）

以下のコマンドを実行するとメニューが表示され、インストールしたいコンポーネントを選べます。

```bash
./install.sh
```

**メニュー例:**
1. **All**: 全ての設定（Zsh, Neovim, VSCode）をインストール
2. **Zsh only**: シェル環境のみ構築
3. **Neovim only**: エディタ設定のみリンク
4. **VSCode only**: 設定同期と拡張機能のインストール

※ 既存の設定ファイルがある場合は、自動的に `.bak` としてバックアップが作成されます。

## 🤖 ROS 2 環境のセットアップ

ROS 2 (Humble) 環境の構築や、別のPCへの移行には専用のスクリプトを使用します。

```bash
# 新しいPCで実行：ROS環境のインストールとワークスペースの復元
./scripts/ros/install_env.sh
```

※ 移行元のPCで準備をする場合は `./scripts/ros/prepare_transfer.sh` を使用します。

## 🔄 環境の同期（Update）

現在のPCの設定をリポジトリに取り込みたい（dotfilesを更新したい）場合は、以下のスクリプトを使用します。

```bash
./update_repo.sh
```

これにより、以下の処理が行われます：
- VSCodeの `settings.json`, `snippets` のコピー
- VSCode拡張機能リスト (`vscode/extensions.txt`) の更新
- Neovim設定のバックアップ

その後、変更内容を確認して Git にコミットしてください。

## 📂 ディレクトリ構成

```text
~/dotfiles/
├── install.sh             # メインインストーラー
├── update_repo.sh         # 設定吸い出しスクリプト
├── scripts/               # 各種セットアップスクリプト
│   ├── setup_zsh.sh
│   ├── setup_neovim.sh
│   ├── setup_vscode.sh
│   └── ros/               # ROS環境構築用
│       ├── install_env.sh
│       ├── prepare_transfer.sh
│       └── packages.txt   # パッケージリスト類
├── zsh/                   # Zsh設定（分割管理）
│   ├── .zshrc             # エントリーポイント
│   ├── aliases.zsh
│   ├── exports.zsh
│   └── ros.zsh
├── config/                # ~/.config/ へのリンク元
│   ├── nvim/
│   ├── mozc/
│   └── dconf/             # GNOME設定など
├── vscode/                # VSCode設定
│   ├── settings.json
│   ├── snippets/
│   └── extensions.txt
└── latex/                 # LaTeX設定
```

## 📝 その他

- **PC固有設定**: `~/.zshrc.local` を作成すると、git管理外でそのPC固有の設定を追加できます。