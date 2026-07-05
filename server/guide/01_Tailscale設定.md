# 01. Tailscale 設定

## 何をするか

このサーバーをTailscaleのVPNに接続します。
これにより、外出先のスマホ・PCからも **「http://kokko-server-pavilion:2283」** のようなアドレスでアクセスできます。

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

### ホスト名の確認

このガイド以下すべての手順は、実際にこのサーバーがTailscaleへ登録している名前
**`kokko-server-pavilion`** を使う前提で書かれている。
TailscaleはデフォルトでOSのマシン名をそのまま登録するため、`server`のような短い名前では
アクセスできない点に注意（`tailscale status`で自分の環境の実際の名前を確認できる）。

---

## ステップ3: MagicDNS を有効にする

Tailscaleのダッシュボードで：
1. **DNS** タブを開く
2. **MagicDNS** を ON にする
3. 保存

これにより、IPアドレスの代わりに `http://kokko-server-pavilion:2283` のようなホスト名でアクセスできます。

---

## ステップ4: スマホにもTailscaleを入れる

- iOS: App Store で「Tailscale」をインストール
- Android: Play Store で「Tailscale」をインストール

アプリを開いて同じアカウントでログインするだけです。

---

## ステップ5: アクセス確認

スマホのブラウザで以下を開く：

```
http://kokko-server-pavilion:3000
```

OpenWebUIのログイン画面が出ればTailscale経由のアクセス成功です！

---

## トラブルシューティング

**「kokko-server-pavilion が見つかりません」と出る場合：**
- MagicDNS が有効になっているか確認
- `tailscale status` でサーバーが Online になっているか確認

**Tailscaleのステータス確認：**
```bash
tailscale status
sudo systemctl status tailscaled
```
