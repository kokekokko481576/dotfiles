# 01. Tailscale 設定

## 何をするか

このサーバーをTailscaleのVPNに接続します。
これにより、外出先のスマホ・PCからも **「http://server:2283」** のようなアドレスでアクセスできます。

---

## ステップ1: Tailscaleアカウント作成

1. https://tailscale.com にアクセス
2. Googleアカウントでサインアップ（無料）
3. ダッシュボードが表示されればOK

---

## ステップ2: サーバーをTailscaleに接続

サーバーのターミナルで以下を実行：

```bash
sudo tailscale up
```

表示されるURLをブラウザで開いてログインします。

```
To authenticate, visit:
  https://login.tailscale.com/a/xxxxxxxxxx
```

ログイン後、ターミナルに戻ると接続完了のメッセージが出ます。

### 接続確認

```bash
tailscale status
```

このサーバーのIPアドレス（100.x.x.x）が表示されればOK。

### ホスト名を`server`に固定する（重要）

このガイド以下すべての手順で `http://server:2283` のように**ホスト名が`server`である前提**で書かれている。
しかしTailscaleはデフォルトでOSのマシン名（例：`kokko-server-pavilion`）をそのまま登録するため、
何もしないと`server`という名前ではアクセスできない。**セットアップ時に一度だけ**以下を実行して固定しておく：

```bash
sudo tailscale up --hostname=server
```

（既に`tailscale up`済みの場合も再実行すれば上書きされる）

---

## ステップ3: MagicDNS を有効にする

Tailscaleのダッシュボードで：
1. **DNS** タブを開く
2. **MagicDNS** を ON にする
3. 保存

これにより、IPアドレスの代わりに `http://server:2283` のようなホスト名でアクセスできます。

---

## ステップ4: スマホにもTailscaleを入れる

- iOS: App Store で「Tailscale」をインストール
- Android: Play Store で「Tailscale」をインストール

アプリを開いて同じアカウントでログインするだけです。

---

## ステップ5: アクセス確認

スマホのブラウザで以下を開く：

```
http://server:3000
```

OpenWebUIのログイン画面が出ればTailscale経由のアクセス成功です！

---

## トラブルシューティング

**「server が見つかりません」と出る場合：**
- MagicDNS が有効になっているか確認
- `tailscale status` でサーバーが Online になっているか確認

**Tailscaleのステータス確認：**
```bash
tailscale status
sudo systemctl status tailscaled
```
