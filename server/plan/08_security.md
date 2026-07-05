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
  ```bash
  sudo apt install -y fail2ban
  sudo systemctl enable --now fail2ban
  # デフォルトでsshd jailが有効。状態確認:
  sudo fail2ban-client status sshd
  ```
- [ ] Let's Encrypt 証明書（Tailscale Funnel を使う場合）
- [ ] 定期的なセキュリティアップデートの自動化（unattended-upgrades）
  ```bash
  sudo apt install -y unattended-upgrades
  sudo dpkg-reconfigure --priority=low unattended-upgrades
  # 自動再起動が必要な場合の設定は /etc/apt/apt.conf.d/50unattended-upgrades で調整
  ```
- [ ] バックアップデータの暗号化
- [ ] SSHのUFW許可範囲の見直し（現状`22/tcp ALLOW IN Anywhere`。Tailscale経由に絞るなら`ufw allow in on tailscale0`のみに変更し22/tcpの全体許可を削除）

## 実施済み

- [x] docker-compose.yml 全サービスに`mem_limit`を設定（RAM 7.1GB環境でのOOM対策、2026-07-05）
- [x] Uptime Kuma を追加（サービス死活監視、`http://kokko-server-pavilion:3001`、2026-07-05）
- [x] `scripts/validate.sh` で `docker compose config` 構文チェックを追加（2026-07-05）
