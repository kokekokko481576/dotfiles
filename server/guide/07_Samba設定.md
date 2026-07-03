# 07. Samba 設定（ファイル共有）

## 概要

Samba を使うと、Mac の Finder から `/mnt/data` にアクセスできます。
研究資料・ドキュメントの保管・アクセスに使います。

---

## ステップ1: Samba パスワードの変更

初期パスワードとして `homeserver` が仮設定されています。
セキュリティのため、必ず変更してください：

```bash
sudo docker exec -it samba smbpasswd kokko
```

新しいパスワードを2回入力します。

---

## ステップ2: 接続テスト（Macから）

1. Finder を開く
2. メニュー: **「移動」** → **「サーバへ接続...」** (⌘K)
3. 以下を入力：
   ```
   smb://server/data
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
sudo mount -t cifs //server/data /mnt/remote \
  -o username=kokko,password=パスワード,uid=$(id -u),gid=$(id -g)

# 自動マウント（/etc/fstab に追加）
//server/data  /mnt/remote  cifs  username=kokko,password=パスワード,uid=1000,gid=1000,nofail  0  0
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
```bash
# パスワードを再設定
sudo docker exec -it samba smbpasswd -a kokko
```
