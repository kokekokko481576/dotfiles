# Obsidian 同期環境（LiveSync + CouchDB）

スマホと自宅サーバー（＋各PC）でObsidianのVaultをほぼリアルタイム同期する。
本命は **Obsidian LiveSync**（CouchDBをバックエンドにしたDB同期）。直いじり感覚で速い。

> **重要（Android仕様）:** Android版Obsidianは、サーバーのディレクトリを直接マウントして
> 読ませると激遅になる。必ず「ローカルVaultに落として同期する」方式（LiveSync等）にすること。
> このガイドのLiveSyncはまさにその方式。

代替案（今回はLiveSyncを採用）: Syncthing（P2Pファイル同期）、Remotely Save（プラグイン単体・
WebDAV/S3）、FolderSync（Android・SMB/Drive）。シンプルさ重視ならSyncthing、プラグイン完結が
よければRemotely Save。

---

## 1. サーバー側（CouchDB）を起動する

```bash
# 1) パスワードを設定（★必須。既定値のままにしない）
#    server/.env に:
#    COUCHDB_USER=obsidian
#    COUCHDB_PASSWORD=<openssl rand -hex 24 などで生成した強いもの>

# 2) データ用ディレクトリを作り、CouchDBコンテナのuid(5984)に所有させる
sudo mkdir -p /mnt/data/ai/couchdb
sudo chown -R 5984:5984 /mnt/data/ai/couchdb

# 3) obsidianプロファイルで起動（通常のupには含まれない）
docker compose --profile obsidian up -d couchdb

# 4) 起動確認
curl -s http://127.0.0.1:5984/ | head        # {"couchdb":"Welcome",...}
```

初回は同期用データベースを1つ作る（名前は任意、例 `obsidian`）:

```bash
source server/.env
curl -s -X PUT http://$COUCHDB_USER:$COUCHDB_PASSWORD@127.0.0.1:5984/obsidian
# CouchDB内部DBも初期化しておく(警告抑制)
for db in _users _replicator _global_changes; do
  curl -s -X PUT http://$COUCHDB_USER:$COUCHDB_PASSWORD@127.0.0.1:5984/$db ; done
```

CORS等の設定は `server/couchdb/local.ini`（read-onlyマウント）で投入済み。

## 2. スマホから届くようにHTTPS公開（Tailscale serve）

wani/n8nと同じく、tailnet内のHTTPSで公開する（LiveSyncはHTTPS必須）。

```bash
# 5984をMagicDNSのHTTPSにぶら下げる（パスは /obsidian-db/ にマッピングする例）
sudo tailscale serve --bg --https=443 --set-path=/obsidian-db localhost:5984
sudo tailscale serve status
```

これで `https://kokko-server-pavilion.tailed0412.ts.net/obsidian-db/` がLiveSyncのURLになる。
（wani等で443を既に別パスに使っている場合はパスを分ければ共存できる。競合するなら
`--https=5985` など別ポートにしてもよい。）

## 3. Obsidian側（各端末）

1. コミュニティプラグイン **Self-hosted LiveSync** をインストール＆有効化。
2. 設定ウィザードで **Remote Type: CouchDB**、以下を入力:
   - URI: `https://kokko-server-pavilion.tailed0412.ts.net/obsidian-db`
   - Username / Password: `.env` の `COUCHDB_USER` / `COUCHDB_PASSWORD`
   - Database name: `obsidian`（手順1で作ったもの）
3. **End-to-End Encryption を有効にし、パスフレーズを設定**（全端末で同一にする）。
   サーバーにも平文で残さないため必須。
4. 「Test Database Connection」→「Check database configuration」で全項目グリーンにする
   （足りない設定はプラグインが提案してくる。多くは `local.ini` で投入済み）。
5. 最初に母艦（PCのVault）で `Rebuild everything`（このデバイスの内容でDBを作る）を実行し、
   以降スマホ等は空Vaultから同期して取り込む。

> 注意: 「Rebuild everything」を複数端末で実行しない（DBを上書きし合う）。母艦1台で1回だけ。

## 4. バックアップ

`/mnt/data/ai/couchdb` は restic 日次バックアップ（guide/10）の対象範囲内。DBファイルごと
バックアップされる。復旧はディレクトリを戻して `--profile obsidian up -d` するだけ。

## トラブルシューティング

| 症状 | 確認 |
|---|---|
| プラグインで接続不可 | Tailscale serveが生きているか(`tailscale serve status`)、URI末尾/DB名、E2EEパスフレーズ一致 |
| CORSエラー | `couchdb/local.ini` の `[cors] origins` に `app://obsidian.md` 等があるか。変更後は `docker compose --profile obsidian restart couchdb` |
| 起動直後に権限エラー | `/mnt/data/ai/couchdb` の所有者が 5984:5984 か |
| 同期が重い/衝突 | LiveSync設定の「Batch size」等を下げる。母艦以外でRebuildしていないか確認 |
