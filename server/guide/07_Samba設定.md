# 07. Samba 設定（ファイル共有）

## 概要

Samba を使うと、Mac の Finder から `/mnt/data` にアクセスできます。
研究資料・ドキュメントの保管・アクセスに使います。

---

## ステップ1: Samba パスワードの設定・変更

2026-07-05に判明：`crazy-max/samba`イメージはコンテナ内の`/etc/passwd`が
**コンテナ再作成のたびに消える**ため、`smbpasswd`で直接パスワードを設定しても
再作成後に失われる（`kokko`というUnixアカウント自体が無くなり
`Failed to find a Unix account for kokko`エラーになる）。

そのため、`/mnt/data/config.yml`（イメージが起動時に読む宣言的設定）でユーザーを定義する
方式に変更した。パスワードは`.env`の`SAMBA_PASSWORD`で管理し、`docker-compose.yml`から
コンテナに渡している。

```yaml
# /mnt/data/config.yml
auth:
  - user: kokko
    group: kokko
    uid: 1000
    gid: 1000
    password: "${SAMBA_PASSWORD}"
```

**パスワードを変更したい場合**：`.env`の`SAMBA_PASSWORD`を書き換えて、コンテナを再作成するだけでよい。

```bash
cd ~/dotfiles/server
docker compose up -d samba
```

（`smbpasswd`を直接叩く必要はない。むしろUnixアカウントが無い状態で叩くと上記のエラーになる）

---

## ステップ2: 接続テスト（Macから）

1. Finder を開く
2. メニュー: **「移動」** → **「サーバへ接続...」** (⌘K)
3. 以下を入力：
   ```
   smb://kokko-server-pavilion/data
   ```
4. ユーザー名: `kokko`、パスワード: 先ほど設定したもの

---

## ステップ3: Finder にサイドバー登録（便利設定）

接続後、サイドバーの **「場所」** に `data` が表示されます。
ドラッグして **「よく使う項目」** に移動すると次回からワンクリックで接続できます。

---

## ディレクトリ構成

Sambaで見える `/mnt/data` の構成：

```
data/
├── photos/          ← Immichと共有（直接編集不推奨）
├── documents/       ← 研究資料・ドキュメント
├── shared/          ← 外部共有ファイルの一時置き場
├── ai/
│   └── context/     ← 執事の記憶ファイル（直接編集可）
├── obsidian/        ← 既存のObsidianノート
└── wiki/            ← 既存のWiki
```

---

## Linux からのマウント方法

```bash
# 必要パッケージ
sudo apt-get install -y cifs-utils

# マウント
sudo mount -t cifs //kokko-server-pavilion/data /mnt/remote \
  -o username=kokko,password=パスワード,uid=$(id -u),gid=$(id -g)

# 自動マウント（/etc/fstab に追加）
//kokko-server-pavilion/data  /mnt/remote  cifs  username=kokko,password=パスワード,uid=1000,gid=1000,nofail  0  0
```

---

## トラブルシューティング

**接続できない場合：**
```bash
# Sambaコンテナのログを確認
sudo docker compose logs samba

# ポート確認
sudo ss -tlnp | grep 445
```

**「認証エラー」と出る場合：**

`.env`の`SAMBA_PASSWORD`を確認し、必要なら書き換えてから再作成する（`smbpasswd`を
直接叩かないこと。ステップ1参照）：

```bash
cd ~/dotfiles/server
docker compose up -d samba
```
