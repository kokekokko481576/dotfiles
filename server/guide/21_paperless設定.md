# Paperless-ngx設定(書類管理+OCR)

PDF・スキャン書類をOCRして全文検索できるようにする書類管理システム。院試・研究・
各種手続き書類・領収書の整理に。

## アクセス・ログイン

- URL: `http://kokko-server-pavilion:8000`
- ユーザー名: `kokko`(`.env`の`PAPERLESS_ADMIN_USER`)
- パスワード: `.env`の`PAPERLESS_ADMIN_PASSWORD`(自動生成済み。値は`.env`参照。gitには含まれない)

## 書類の取り込み方

- Web UIから直接アップロード、または`/mnt/data/paperless/consume`フォルダにファイルを置くと
  自動で取り込まれる(Samba経由で`smb://kokko-server-pavilion/data/...`にマウントできるよう
  にすれば、スマホ/PCから「置くだけ」で取り込める。現状consumeフォルダはSamba公開設定に
  含まれていないので、使いたければ`guide/07_Samba設定.md`を参考にshareを追加すること)。
- OCR言語は日本語(`PAPERLESS_OCR_LANGUAGE=jpn`/`PAPERLESS_OCR_LANGUAGES=jpn`)。
  英語文書は既定で英独伊西仏が入っているため両方そこそこ読める。

## 構成

| 項目 | 値 |
|-----|---|
| webserver | `ghcr.io/paperless-ngx/paperless-ngx:latest`(Django、OCR含む) |
| db | 専用`postgres:18`(`paperless-db`。Immichの`database`はpgvector拡張入りの特殊イメージのため共用しない) |
| broker | `valkey/valkey:9-alpine`(タスクキュー用、Redis互換) |
| データ | `/mnt/data/paperless/{data,media,export,consume}` (media=取り込んだ原本+OCR結果。最重要) |
| mem_limit | webserver 1g / db 384m / broker 128m。4サービス中もっとも重い
      (実測は起動直後で~180MB、OCR処理中は一時的に増える見込み) |
| 公開範囲 | ポート`8000`をtailnet+LANのufw default-denyで保護 |

## RAM事情の注意(2026-07-24導入時)

導入時点でこのマシンは元々RAMが逼迫気味(swap 8GB中ほぼ埋まっていた)だったため、導入と
同時に`zram-tools`(zstd圧縮スワップ、`/etc/default/zramswap`で`PERCENT=50`)を追加し、
実質的な安全マージンを確保した(`plan/09_improvements.md`で以前から検討課題だったもの)。
大量の書類を一度に取り込む(OCRが並列で走る)と一時的にメモリ消費が増えるため、
最初は数枚ずつ試すのが無難。

## バックアップ

`scripts/backup.sh`に`paperless_db`の`pg_dump`と`/mnt/data/paperless`(consumeは空でよい)を
追加済み。**media(原本+OCR結果)はこのシステムで一番実害が大きいデータ**なので特に重要。
