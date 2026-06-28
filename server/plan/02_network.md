# ネットワーク・リモートアクセス

## 構成方針

- **VPN**: Tailscale（ゼロ設定、NAT越え不要、無料枠で個人利用は十分）
- **外部公開**: 原則しない。ファイルの外部共有は限定リンク方式
- **ポート開放**: 不要（Tailscale で全て解決）

## Tailscale 構成

```
[スマホ]──┐
[ノートPC]─┤  Tailscale Mesh VPN  ├──[現サーバー 100.x.x.1]
[外出先PC]─┘                          └──[自作GPU PC 100.x.x.2]（将来）
```

### Tailscale 設定方針

| 設定項目 | 方針 |
|---------|------|
| MagicDNS | 有効化。`server`・`gpu-pc` でホスト名アクセス |
| Subnet routes | 必要に応じて自宅 LAN 全体を公開（例：192.168.1.0/24）|
| Exit node | 不要（セキュリティ重視なら現サーバーを Exit node にもできる）|
| ACL | デフォルト（個人利用なので全デバイス間通信を許可）|

### Tailscale Funnel（オプション）

公開 URL が必要な場面（ファイル一時共有など）で Tailscale Funnel を使う選択肢がある。
ただし常時公開は避ける。

## SSH アクセス

| 設定 | 値 |
|-----|---|
| 認証方式 | 公開鍵認証のみ（パスワード認証無効）|
| ポート | 22（Tailscale 経由のみ到達可能）|
| 鍵管理 | dotfiles の `git/` ディレクトリと統合 |

```bash
# ~/.ssh/config（クライアント側）に追加する想定
Host homeserver
  HostName server          # Tailscale MagicDNS
  User kokko
  IdentityFile ~/.ssh/id_ed25519
```

## ファイルの外部共有

自分以外の人間にファイルを渡したい場合の選択肢：

| 方式 | 特徴 | 採用可否 |
|-----|------|---------|
| Nextcloud 共有リンク | 期限・パスワード設定可。重い | 検討中 |
| nginx + 一時トークン | 軽量だが自前実装が必要 | 将来候補 |
| Tailscale Funnel | 手軽だが URL が固定されない | 一時共有向き |
| Immich 共有アルバム | 写真特化。使いやすい | 写真なら第一候補 |

→ Phase 1 は Immich の共有アルバム機能で対応する方向で検討。

## ポート一覧（サーバー内部）

Tailscale 経由でのアクセスを前提とするため、外部へのポート開放は不要。
Docker ネットワーク内の内部ポートのみ。

| サービス | 内部ポート | 備考 |
|---------|-----------|------|
| SSH | 22 | |
| Samba | 445 | LAN + Tailscale |
| OpenWebUI | 3000 | Tailscale 経由 |
| Immich | 2283 | Tailscale 経由 |
| Discord Bot | - | アウトバウンドのみ |
| Whisper API | 9000 | 内部通信のみ |
| Ollama（GPU PC）| 11434 | GPU PC 起動時のみ |
