# Miniflux設定(RSSリーダー)

研究・ニュース・ブログを広告無しで購読する軽量RSSリーダー(Go製)。

## アクセス・ログイン

- URL: `http://kokko-server-pavilion:8223`
- ユーザー名: `kokko`(`.env`の`MINIFLUX_ADMIN_USERNAME`)
- パスワード: `.env`の`MINIFLUX_ADMIN_PASSWORD`(自動生成済み。値は`.env`参照。gitには含まれない)
- ログイン後、設定画面から自分の好きなパスワードに変更してよい。

## フィードの追加

- 右上のメニュー→「フィードを追加」でURLを登録するか、既存RSSリーダー(Feedly等)から
  OPML形式でエクスポートしたファイルを「設定→インポート」で一括インポートできる。

## 構成

| 項目 | 値 |
|-----|---|
| イメージ | `miniflux/miniflux:latest` + 専用`postgres:18` |
| DB | Immichとは別の専用Postgresコンテナ(`miniflux-db`)。Immichの`database`は
      pgvector拡張入りの特殊イメージのため共用しない |
| データ | `/mnt/data/miniflux-db`(フィード・記事・購読設定) |
| mem_limit | miniflux 256m / miniflux-db 256m(実測は合計~60MB) |
| 公開範囲 | ポート`8223`をtailnet+LANのufw default-denyで保護(Navidrome等と同じパターン、
      tailscale serveは使わずTailscale経由でそのままアクセス) |

## バックアップ

`scripts/backup.sh`に`miniflux_db`の`pg_dump`と`/mnt/data/miniflux-db`を追加済み。
