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

## 🔄 環境の同期（Update）

現在のPCの設定をリポジトリに取り込みたい（dotfilesを更新したい）場合は、以下のスクリプトを使用します。

```bash
./update_repo.sh
```

これにより、以下の処理が行われます：
- VSCodeの `settings.json`, `snippets` のコピー
- VSCode拡張機能リスト (`vscode_extensions.txt`) の更新
- Neovim設定のバックアップ

その後、変更内容を確認して Git にコミットしてください。

## 📂 ディレクトリ構成

- `install.sh`: メインのセットアップスクリプト
- `update_repo.sh`: 現環境の設定を吸い出すスクリプト
- `scripts/`: 各機能ごとのセットアップスクリプト
- `zsh/`: Zshの設定ファイル群（`aliases.zsh`, `exports.zsh` など分割管理）
- `config/`: `~/.config` 以下に配置される設定（nvim, mozcなど）
- `vscode/`: VSCode用設定
- `latex/`: LaTeX用設定

## 📝 その他

- **ROS環境**: `install_ros_environment.sh` などの専用スクリプトも含まれています。
- **PC固有設定**: `~/.zshrc.local` を作成すると、git管理外でそのPC固有の設定を追加できます。
