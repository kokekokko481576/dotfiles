# 08. SSH セキュリティ強化

## 概要

現在の状態：
- SSH ポート22が開いている
- パスワード認証が有効（脆弱）

この手順でパスワード認証を無効化し、鍵認証のみにします。

---

## ⚠️ 重要な注意事項

**パスワード認証を無効化する前に、必ず鍵でSSHログインできることを確認してください。**
確認なしに無効化すると、サーバーに入れなくなる可能性があります。

---

## ステップ1: 現在の鍵認証動作確認

別のターミナルを開き、以下でSSH接続テストをします：

```bash
ssh -i ~/.ssh/id_ed25519 kokko@server
```

「Welcome to Ubuntu...」と出て接続できればOKです。

確認できたら次のステップへ。

---

## ステップ2: SSH設定の変更

```bash
sudo nano /etc/ssh/sshd_config
```

以下の項目を変更（`#` を外してから値を変える）：

```
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
```

---

## ステップ3: SSH設定の再読み込み

```bash
sudo systemctl reload sshd
```

---

## ステップ4: 動作確認

**別のターミナルで**（今の接続は切らずに）：

```bash
# 鍵認証で接続できることを確認
ssh kokko@server

# パスワード認証が拒否されることを確認（-o で鍵認証を一時無効化）
ssh -o PubkeyAuthentication=no kokko@server
# → "Permission denied (publickey)" と出ればOK
```

---

## UFW ファイアウォール確認

```bash
sudo ufw status verbose
```

以下のような出力が出ていれば正常です：

```
Status: active

To                         Action      From
--                         ------      ----
Anywhere on tailscale0     ALLOW IN    Anywhere
22/tcp                     ALLOW IN    Anywhere
```

---

## クライアント側の~/.ssh/config 設定（Mac/Linux）

接続元マシンに以下を追加すると `ssh server` だけで接続できます：

```
Host homeserver
  HostName server
  User kokko
  IdentityFile ~/.ssh/id_ed25519
```

使い方：
```bash
ssh homeserver
```
