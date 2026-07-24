# Vaultwarden設定(パスワード管理)

Bitwarden互換のセルフホストパスワード管理サーバー。ブラウザ拡張機能・スマホアプリの
自動入力がWebAuthn等でHTTPSを要求するため、n8nと同じ`tailscale serve`でHTTPS化している。

## アクセス

- URL: `https://kokko-server-pavilion.tailed0412.ts.net:8444`
- 管理画面(`/admin`): 同URL + `/admin`。パスワードは`.env`の`VAULTWARDEN_ADMIN_TOKEN`
  (このドキュメント作成時に自動生成済み。値は`.env`参照。**gitには含まれない**)

※ サーバー自身から`curl`等で上記ドメインへアクセスすると名前解決に失敗するのが正常
  (このマシンがtailscaleのMagicDNSリゾルバを使っていないため。n8n・waniの既存URLも同様)。
  実際のスマホ・PCからは問題なくアクセスできる。

## 初回セットアップ

1. 上記URLをブラウザで開き、「アカウント作成」から自分のBitwardenアカウントを作る
   (マスターパスワードは他とは別の強いものにする。忘れると復旧不可)。
2. アカウント作成後、`.env`の`VAULTWARDEN_SIGNUPS_ALLOWED`を`false`にして
   `docker compose up -d vaultwarden`で再作成し、他人の新規登録を止める
   (既定は`true`で、初回サインアップのため一時的に開けてある)。
3. 各ブラウザ・スマホにBitwarden公式拡張機能/アプリを入れ、サーバーURLに上記アドレスを指定して
   ログインする。

## 管理者パネル(`/admin`)

- `.env`の`VAULTWARDEN_ADMIN_TOKEN`がそのままログインパスワードになる(現状プレーンテキスト)。
- 起動ログに「Argon2ハッシュ化を推奨」という警告が出る。ハッシュ化は対話的TTYでの
  パスワード入力が必要で自動化に向かないため未実施。気になる場合は手動で:
  ```
  docker run --rm -it vaultwarden/server:latest /vaultwarden hash
  ```
  で表示されたハッシュを`.env`の`VAULTWARDEN_ADMIN_TOKEN`に設定し直し、
  `docker compose up -d vaultwarden`で反映する。
  `.env`自体が600権限・gitignore済みなので、実害は小さい。

## 構成

| 項目 | 値 |
|-----|---|
| イメージ | `vaultwarden/server:latest`(Rust製、超軽量) |
| データ | `/mnt/data/vaultwarden`(暗号化された保管庫の実体。バックアップ対象) |
| mem_limit | 128m(実測は起動直後で~8MB) |
| 公開範囲 | `127.0.0.1:8222`のみ(LAN/tailnet直アクセス不可)。tailscale serveの`:8444`経由のみ到達可能 |

## バックアップ

`scripts/backup.sh`の対象に`/mnt/data/vaultwarden`を追加済み。マスターパスワードを忘れると
このバックアップからも復元できない(Vaultwarden自体はゼロ知識暗号化のため)ので、
マスターパスワードは別途(紙・別のパスワードマネージャ等)保管すること。
