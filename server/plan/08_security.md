# セキュリティ方針

## 基本方針

- 外部への直接ポート開放は**しない**（Tailscale で全て賄う）
- 認証情報は `.env` ファイルに集約し、git に含めない
- シングルユーザー前提のため複雑なアクセス制御は不要

## ネットワークセキュリティ

| 項目 | 設定 |
|-----|------|
| 外部ポート開放 | なし |
| ファイアウォール | ufw で SSH (22) は LAN(`192.168.11.0/24`)限定 + Tailscale全許可、それ以外は DROP |
| SSH | 鍵認証のみ、パスワード認証無効 |
| Tailscale | ACL はデフォルト（自分のデバイスのみ）|

```bash
# ufw 設定
ufw default deny incoming
ufw allow in on tailscale0  # Tailscale 経由は全て許可
ufw allow from 192.168.11.0/24 to any port 22 proto tcp  # SSHはLANのみ（鍵認証のみ）
ufw enable
```

セキュリティレビューで「22/tcpがAnywhere（全世界）に開いている」ことが発覚したため2026-07-05に修正。
Tailscale障害時にもLAN経由でSSH復旧できるよう、LAN限定は残しつつ全世界への公開だけを塞いだ。

### Docker × UFWのバイパス問題について（調査済み・問題なし）

Dockerはiptablesを直接操作するため「UFWのルールをバイパスして全ポートが外部公開される」という
既知の問題があるが、実機で`iptables -L INPUT`等を確認した結果、**このサーバーでは該当しない**ことを
確認済み（2026-07-05）。理由：Dockerが`userland-proxy`（`docker-proxy`プロセスが実際にホストの
ポートをlistenする方式）で動作しているため、公開ポートへの接続は通常のINPUT chainで正しく
UFWの制御下に入る（`DOCKER-USER` chainは空で影響なし）。

確認の結果、Immich(2283)/OpenWebUI(3000)/n8n(5678)/Uptime Kuma(3001)/Homepage(3005)は
UFWに明示ルールがないため**Tailscale経由のみ**でLANからは遮断されていた。一方Samba(445)は
`plan/02_network.md`の設計（LAN + Tailscale）に反してLAN許可ルールが存在しなかったため、
`ufw allow from 192.168.11.0/24 to any port 445 proto tcp`を追加して設計通りに復元した。

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

- [ ] Let's Encrypt 証明書（Tailscale Funnel を使う場合）
- [ ] バックアップデータの暗号化
- [ ] SSHのUFW許可範囲の見直し（現状`22/tcp ALLOW IN Anywhere`。Tailscale経由に絞るなら`ufw allow in on tailscale0`のみに変更し22/tcpの全体許可を削除）

## 執事エージェントのホスト操作権限（新規、2026-07-05）

執事Botに、Discord経由でこのサーバーホスト自体を操作させる機能（シェル実行・ファイル読み書き）を追加した。
詳細設計は`plan/11_agent-control.md`。ここでは本ファイルの観点（脅威モデル）から要点のみ記す。

- 実行権限は`DISCORD_OWNER_ID`で指定した1ユーザーのみに限定（コードレベルで強制）。
- 実行そのものは、Discord/LLM APIとやり取りする`butler-bot`コンテナではなく、ホスト上で
  `kokko`ユーザーのsystemdサービスとして常駐する別プロセス(`scripts/agent_executor.py`)が
  Unixソケット経由で行う。`kokko`はNOPASSWD ALLのsudo権限とdockerグループを持つため、
  この別プロセス自体は実質ホストroot相当の力を持つ（＝分離の目的はコンテナ側の攻撃面の遮断であり、
  権限の弱体化ではない）。
- 破壊的操作（未知のコマンド・書き込み含む）は実行前にDiscordリアクションでの承認を必須化。
- 新たな残存リスク: Discordアカウント自体が乗っ取られた場合、この権限モデルは無力
  （持ち主本人になりすませるため）。**Discordアカウントの2要素認証は必須**として運用すること。
- 新たな残存リスク: `run_shell`経由で`.env`等の認証情報を間接的に読み出すことは技術的に防げていない
  （`read_file`の拒否リストは直接指定のみをブロック）。単一ユーザー運用という前提の範囲内でのリスク受容。

## 実施済み

- [x] docker-compose.yml 全サービスに`mem_limit`を設定（RAM 7.1GB環境でのOOM対策、2026-07-05）
- [x] Uptime Kuma を追加（サービス死活監視、`http://kokko-server-pavilion:3001`、2026-07-05）
- [x] `scripts/validate.sh` で `docker compose config` 構文チェックを追加（2026-07-05）
- [x] fail2ban 導入・有効化（sshd jail、2026-07-05）
- [x] unattended-upgrades 有効化確認（既にインストール済み、`APT::Periodic::Unattended-Upgrade "1"`を確認、2026-07-05）
- [x] sambaコンテナのSMB接続不能問題を修正（`/data/cache`・`/data/lib`の所有者不一致、2026-07-05）
- [x] swapを8GBに拡張（2026-07-05）
