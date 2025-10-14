# dotfiles

作業環境を再現するための設定ファイル（dotfiles）リポジトリです。

## 概要

このリポジトリには、主に以下のツールの設定ファイルが含まれています。

- **Zsh**: Prezto と Powerlevel10k を使ったモダンで高速なシェル環境
- **Git**: エイリアスや署名設定など
- **VSCode**: `settings.json`, `snippets`, 拡張機能リスト
- **Linux Desktop**: GNOME Terminal, dconf, Mozc（日本語入力）など

## 🚀 セットアップ

新しい環境に設定を反映させるには、通常は以下のワンライナーコマンドを実行するだけです。

### 自動セットアップ（推奨）

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/kokekokko481576/dotfiles/main/bootstrap.sh)"
```

これにより、必要なアプリケーションのインストールから設定ファイルのシンボリックリンク作成までが自動的に行われます。

### 手動セットアップ

もしリポジトリを先にcloneしている場合は、各スクリプトを直接実行することもできます。

```bash
# 依存パッケージのインストールやPreztoのセットアップ
bash bootstrap.sh

# 設定ファイルのシンボリックリンク作成
bash setup.sh
```

## 📜 各スクリプトの役割

### `bootstrap.sh`

環境構築の初期セットアップ（ブートストラップ）を行います。主な処理は以下の通りです。

- `git`, `zsh`, `curl` などの基本的なパッケージをインストール
- `Prezto`（Zshフレームワーク）をセットアップ
- `setup.sh` を呼び出して設定を完了
- デフォルトシェルを `zsh` に変更

### `setup.sh`

このリポジトリ内の設定ファイルを、ホームディレクトリ以下の適切な場所にシンボリックリンクとして配置します。

- `~/.zshrc` や `~/.gitconfig` などをリンク
- VSCodeの拡張機能を `vscode_extensions.txt` からインストール
- （Linuxデスクトップの場合）`dconf` の設定を復元
