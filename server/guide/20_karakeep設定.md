# Karakeep設定(AIブックマーク管理)

URLを放り込むと自動でクロール・スクリーンショット取得・全文検索インデックス化し、
既存のOllama(task-agentと共用)でAIタグ付け・要約までしてくれるブックマークマネージャ。

## アクセス・初回セットアップ

- URL: `http://kokko-server-pavilion:3030`
- 初回アクセス時にブラウザ画面で自分のアカウントを作成する(静的な認証情報は`.env`に無い)。
- ブラウザ拡張機能(Chrome/Firefox)・スマホアプリからも同じURLをサーバーとして指定できる。

## AIタグ付け・要約の仕組み

- `OLLAMA_BASE_URL=http://ollama:11434` で、task-agentと同じOllamaコンテナ(既存)をそのまま
  使い回している(追加のAPIキー・追加コストなし)。
- 使うモデルは`.env`の`OLLAMA_MODEL`(既定`llama3.2:3b`)と共通。
- 精度を上げたい場合は`.env`に`OPENAI_API_KEY`系の変数を足してLiteLLM(Gemini)経由に
  切り替えることも可能(docker-compose.ymlの`karakeep`環境変数を要調整。現状は未設定=Ollama使用)。

## 構成

| 項目 | 値 |
|-----|---|
| web (`karakeep`) | `ghcr.io/karakeep-app/karakeep:release`。実測起動直後~420MB(Next.jsアプリ) |
| `karakeep-chrome` | ヘッドレスChrome(`alpine-chrome:124`)。スクリーンショット・JS実行が必要なページのクロール用 |
| `karakeep-meilisearch` | 全文検索エンジン(`getmeili/meilisearch:v1.41.0`) |
| データ | `/mnt/data/karakeep/data`(本体データ)、`/mnt/data/karakeep/meilisearch`(検索インデックス、
      壊れても再インデックス可能) |
| mem_limit | web 512m / chrome 384m / meilisearch 512m(3コンテナ合計で実測~530MB) |
| 公開範囲 | ポート`3030`をtailnet+LANのufw default-denyで保護(Navidrome等と同じパターン) |

## 注意

- 3コンテナ構成でこの4サービスの中では最も重い部類(Paperless-ngxを除く)。RAMが厳しい場合は
  `karakeep-chrome`を止めるとクロール自体は動くがスクリーンショット/JS実行サイトの取得ができなくなる、
  `karakeep-meilisearch`を止めると検索機能だけ丸ごと無効化される(公式ドキュメント記載の縮退運用)。

## バックアップ

`scripts/backup.sh`の対象に`/mnt/data/karakeep`を追加済み。
