# セキュリティ方針

## 基本方針

- 外部への直接ポート開放は**しない**（Tailscale で全て賄う）
- 認証情報は `.env` ファイルに集約し、git に含めない
- シングルユーザー前提のため複雑なアクセス制御は不要

## ネットワークセキュリティ

| 項目 | 設定 |
|-----|------|
| 外部ポート開放 | なし |
| ファイアウォール | ufw で SSH (22) のみ許可、それ以外は DROP |
| SSH | 鍵認証のみ、パスワード認証無効 |
| Tailscale | ACL はデフォルト（自分のデバイスのみ）|

```bash
# ufw 設定
ufw default deny incoming
ufw allow in on tailscale0  # Tailscale 経由は全て許可
ufw allow 22/tcp            # SSH（鍵認証のみ）
ufw enable
```

## 認証情報管理

| 項目 | 管理方法 |
|-----|---------|
| API キー（Gemini, Switchbot 等）| `.env` ファイル（git 除外）|
| SSH 鍵 | dotfiles の鍵管理（秘密鍵は git に含めない）|
| Samba パスワード | `smbpasswd` で設定、`.env` に保存 |
| Discord Token | `.env` に保存 |

`.gitignore` に必ず追加するもの：
```
server/.env
server/**/*.key
server/**/*.pem
```

## 外部共有ファイルのセキュリティ

Immich の共有リンクを使う場合：
- 有効期限を必ず設定する（無期限リンクを避ける）
- 機密ファイルは `/mnt/data/shared/` に置かない
- 必要に応じてパスワードを設定する

## Docker セキュリティ

- コンテナは非 root ユーザーで実行（可能な限り）
- ボリュームマウントは必要最小限のパスのみ
- `privileged: true` は使わない

## 監視・アラート

| 対象 | 監視方法 |
|-----|---------|
| ディスク残量 | 定期チェック → 閾値超えで Discord 通知 |
| サービスダウン | Docker ヘルスチェック + n8n アラート |
| 不審なSSHログイン | fail2ban（将来）|

## 未実施・将来対応

- [ ] fail2ban の設定（ブルートフォース対策）
- [ ] Let's Encrypt 証明書（Tailscale Funnel を使う場合）
- [ ] 定期的なセキュリティアップデートの自動化（unattended-upgrades）
- [ ] バックアップデータの暗号化
