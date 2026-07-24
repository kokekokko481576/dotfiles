# サービス管理

## 方針

- 全サービスを Docker Compose で管理
- `server/docker-compose.yml` で一元定義
- 環境変数（APIキー等）は `.env` に分離し、`.env.example` のみをgit管理
- ボリュームは `/mnt/data/` 配下に集約

## Phase 1 サービス構成（計画時点のイメージ）

以下は計画当初のラフなイメージで、実際の`docker-compose.yml`とはサービス名が異なる箇所がある
（例: `postgres`→`database`、`immich-ml`→`immich-machine-learning`）。また`litellm` `uptime-kuma`
`homepage`はこの後の運用で追加、`whisper`は未実装のまま。正確な現状は下記「サービス詳細」と
実ファイルの`docker-compose.yml`を参照。

```yaml
# 構成イメージ（実装時に詳細化）
services:
  immich-server:     # 写真管理
  immich-microservices:
  immich-ml:
  postgres:          # Immich 用 DB
  redis:             # Immich 用キャッシュ
  samba:             # ファイル共有
  openwebui:         # AI チャット UI
  butler-bot:        # Discord Bot + エージェント（自作）
  n8n:               # ワークフロー自動化
  whisper:           # STT（将来ローカル化、未実装）
```

## サービス詳細

### Immich

| 項目 | 値 |
|-----|---|
| イメージ | `ghcr.io/immich-app/immich-server:release` |
| ポート | `2283:2283`（バージョンによって内部ポートが変わるため`docker logs immich_server \| grep listening`で要確認）|
| ボリューム | `/mnt/data/photos:/usr/src/app/upload` |
| 依存 | PostgreSQL, Redis |

### Samba

| 項目 | 値 |
|-----|---|
| イメージ | `dperson/samba` または `crazymax/samba` |
| ポート | `445:445` |
| ボリューム | `/mnt/data:/data` |
| 設定 | ユーザー認証あり、ゲスト無効 |

### Navidrome（音楽ストリーミング）

Spotify等の代替として、手持ち音源をセルフホストで広告なし・無料でストリーミング再生（2026-07-12追加）。

| 項目 | 値 |
|-----|---|
| イメージ | `deluan/navidrome:latest`（ffmpeg同梱、Go製で軽量）|
| ポート | `4533:4533`（Tailscale経由のみ、ufwで外部遮断）|
| ボリューム | `${MUSIC_LOCATION:-/mnt/data/music}:/music:ro`（音源・読み取り専用）、`navidrome-data:/data`（DB・設定）|
| API | Subsonic API 互換。スマホは対応アプリ（iOS: Amperfy/play:Sub、Android: Symfonium/DSub/Substreamer）、PCはブラウザ内蔵プレイヤー |
| 音源の追加 | Samba（`smb://kokko-server-pavilion/data/music`）にコピー → `ND_SCANSCHEDULE=1h`で自動反映（即時は管理画面から手動スキャン）|
| 認証 | 初回ブラウザアクセス時に管理者アカウントを画面で作成（`.env`に秘密情報なし）|
| mem_limit | 384m（常時~80MBだが大規模ライブラリの初回スキャンで一時的に増える）|
| 手順書 | `guide/15_音楽サーバー設定.md` |

### OpenWebUI

| 項目 | 値 |
|-----|---|
| イメージ | `ghcr.io/open-webui/open-webui:main` |
| ポート | `3000:8080` |
| バックエンド設定 | Gemini API + Ollama（同一サーバー上でCPU推論）を同時接続。GPU PC完成後は`OLLAMA_BASE_URL`をそちらに向ける想定 |

### Ollama（ローカルLLM）

| 項目 | 値 |
|-----|---|
| イメージ | `ollama/ollama:latest` |
| ポート | 公開なし（OpenWebUIから内部ネットワーク`http://ollama:11434`でのみアクセス）|
| ボリューム | 名前付きボリューム `ollama-data` |
| 導入モデル | `llama3.2:3b`（Q4量子化、約2GB。RAM 7.1GB環境のためCPU推論は小型モデル限定）|
| 追加方法 | `docker exec ollama ollama pull <モデル名>` |

### LiteLLM（Vertex AI中継プロキシ）

Google AI Studio(`GEMINI_API_KEY`)のPrepaidクレジットが枯渇した際の代替経路として、
Vertex AI経由でGeminiを呼べるように追加（2026-07-05）。

| 項目 | 値 |
|-----|---|
| イメージ | `ghcr.io/berriai/litellm:main-stable` |
| ポート | 公開なし（内部ネットワーク`http://litellm:4000`のみ）|
| 認証 | `vertex-sa.json`（サービスアカウント鍵、`.gitignore`済み）+ `LITELLM_MASTER_KEY` |
| 設定 | `./litellm/config.yaml`（`gemini-2.5-flash`, `gemini-2.5-pro`をVertex AI `us-central1`で定義）|
| mem_limit | 1536m（依存ライブラリが多く512mでは起動時に不足した実績あり）|
| 利用側 | OpenWebUI（`openai.api_base_urls`にAI Studio Geminiと並べて2つ目の接続として登録）、
  Butler Bot（`ai/src/bot.py`が`openai`パッケージ経由でここを呼ぶ）|

**注意**：Google CloudのTrial credit（GenAI App Builder向けと表示されていたもの）がVertex AIの
Gemini呼び出しに実際に適用されているかは未確認（課金エラーは出ていないが、少額の実費が
決済カードに課金されている可能性も否定できない）。しばらくGoogle Cloudの請求画面で
実際の消費先を確認すること。`gemini-2.0-flash`系はこのプロジェクト/リージョンでは
404（モデルが見つからない）だったため`gemini-2.5-flash`/`gemini-2.5-pro`のみ使用している。

### n8n

| 項目 | 値 |
|-----|---|
| イメージ | `n8nio/n8n` |
| ポート | `5678:5678`（Tailscale 経由のみ）|
| ボリューム | `/mnt/data/ai/n8n:/home/node/.n8n` |
| 用途 | カレンダー連携・通知・ワークフロー自動化 |

### Butler Bot（自作）

| 項目 | 値 |
|-----|---|
| ベース | Python 3.12 + discord.py（LLM呼び出しは`openai`パッケージ経由でLiteLLMを叩く方式。LangGraph等は未採用）|
| ポート | なし（アウトバウンドのみ）|
| ボリューム | `/mnt/data/ai/context:/app/context`（会話履歴・監査ログ）、`/mnt/data/ai/agent:/app/agent-socket`（エージェント実行用ソケット） |
| 主な環境変数 | `DISCORD_TOKEN_BUTLER`, `DISCORD_GUILD_ID`, `DISCORD_CHANNEL_NOTIFY`, `DISCORD_CHANNEL_CHAT`, `LITELLM_MASTER_KEY`, `LLM_MODEL`, `DISCORD_OWNER_ID`（省略可・エージェントモード用）。全一覧は`.env.example`参照 |
| 起動 | `profiles: [butler]`のため`docker compose --profile butler up -d`（下記「起動・管理コマンド」参照）|
| コマンド | `/status` `/health` `/plan` `/todos` `/clear`、`#butler-chat`でのメンション/自然文会話 |
| エージェントモード | `DISCORD_OWNER_ID`設定時、ホストのシェル実行・ファイル操作ツールを利用可能。詳細: `plan/11_agent-control.md`、有効化手順: `guide/11_執事エージェント権限有効化.md` |

### Uptime Kuma（監視）

| 項目 | 値 |
|-----|---|
| イメージ | `louislam/uptime-kuma:1` |
| ポート | `3001:3001` |
| ボリューム | 名前付きボリューム `uptime-kuma-data` |
| 用途 | 各サービスの死活監視、Discord/Webhook通知（初回アクセス時にセットアップ必要）|

### Homepage（ダッシュボード）

| 項目 | 値 |
|-----|---|
| イメージ | `ghcr.io/gethomepage/homepage:latest` |
| ポート | `3005:3000` |
| 設定 | `./homepage/*.yaml`（services/bookmarks/settings/widgets） |
| 用途 | 全サービスへのリンク集。docker.sockはマウントしていない（セキュリティ優先、siteMonitorによるHTTP到達確認のみ）|

## ディレクトリ構成

```
server/
├── docker-compose.yml
├── .env.example           # テンプレート（git管理対象、環境変数の一覧はこれが正）
├── .env                   # 実際の認証情報（.gitignore 対象）
├── vertex-sa.json         # Vertex AIサービスアカウント鍵（.gitignore対象）
├── plan/                  # 要件定義・設計ドキュメント（このファイルもここ）
├── guide/                 # 実施者（あなた）が手を動かす手順書
├── samba/
│   └── smb.conf
├── litellm/
│   └── config.yaml        # Vertex AI Gemini中継の設定
├── homepage/               # ダッシュボードの設定(yaml)
├── ai/
│   ├── Dockerfile         # Butler Bot
│   ├── requirements.txt
│   └── src/
│       ├── bot.py
│       └── agent_tools.py # エージェントモードのツール定義・許可リスト判定
└── scripts/
    ├── setup.sh           # 初期セットアップ（マウント・権限設定）
    ├── update.sh          # サービス更新
    ├── validate.sh        # docker-compose.yml構文チェック
    ├── backup.sh          # resticバックアップ
    ├── agent_executor.py  # ホスト実行エージェント(systemd常駐)
    └── systemd/           # 各種systemdユニット定義
```

## .env.example について

実際に必要な環境変数の一覧は、常に最新の`.env.example`（本ファイルの複製ではない）を参照すること。
以前このファイルに簡易版のテンプレートを重複掲載していたが、更新されず実態と乖離していたため削除した。

## 起動・管理コマンド

```bash
# 全サービス起動（butler-botは含まれない。profiles: [butler]のため個別指定が必要）
docker compose up -d

# Butler Botも含めて起動
docker compose --profile butler up -d

# ログ確認
docker compose logs -f butler-bot

# 特定サービスだけ再起動
docker compose restart butler-bot

# 全停止
docker compose down
```

## Phase 2 追加サービス（GPU PC 側）

GPU PC に Ollama を直接インストール（Docker不要）：

```bash
# GPU PC での設定
OLLAMA_HOST=0.0.0.0 ollama serve
```

OpenWebUI の `OPENAI_API_BASE_URL` を `http://gpu-pc:11434/v1` に変更するだけで切替完了。

### Vaultwarden・Miniflux・Karakeep・Paperless-ngx（2026-07-24追加、定番セルフホストサービス4種）

「よくある人気のサーバーの使い方でまだ実装していないもの」という依頼を受け、寝ている間に
自律導入。手順詳細はそれぞれの guide を参照。

| サービス | 用途 | イメージ | アクセス | 手順書 |
|---------|------|---------|---------|--------|
| Vaultwarden | パスワード管理(Bitwarden互換) | `vaultwarden/server:latest` | `https://kokko-server-pavilion.tailed0412.ts.net:8444`(tailscale serve経由。WebAuthn等がHTTPS必須のため) | `guide/18_vaultwarden設定.md` |
| Miniflux | RSSリーダー | `miniflux/miniflux:latest` + 専用`postgres:18` | `http://kokko-server-pavilion:8223` | `guide/19_miniflux設定.md` |
| Karakeep | AIブックマーク(自動タグ付け・要約) | `karakeep-app/karakeep` + alpine-chrome + meilisearch | `http://kokko-server-pavilion:3030` | `guide/20_karakeep設定.md` |
| Paperless-ngx | 書類管理+OCR全文検索 | `paperless-ngx/paperless-ngx` + 専用`postgres:18` + valkey | `http://kokko-server-pavilion:8000` | `guide/21_paperless設定.md` |

- Miniflux・Paperlessは、Immichの`database`(pgvector拡張入りの特殊イメージ)を共用せず、
  それぞれ専用の軽量`postgres:18`コンテナを持つ(RAM増分は実測で1コンテナ20〜50MB程度と軽微)。
- KarakeepのAIタグ付け・要約は既存Ollama(`http://ollama:11434`, task-agentと共用)をそのまま
  使い回しており、追加のAPIキー・追加コストは無し。
- Vaultwarden以外は全てNavidrome等と同じ「ポート公開+ufw default-deny+Tailscale内のみ到達可」
  パターン。Vaultwardenのみ`127.0.0.1`ローカルバインド+`tailscale serve`でHTTPS化(n8nと同じ手法)。
- 導入時、このマシンは元々RAM/swapが逼迫気味だったため(下記リソース目安・`09_improvements.md`
  セクション1参照)、導入前に`zram-tools`(zstd圧縮スワップ、`PERCENT=50`)を追加して安全マージンを
  確保してから4サービスを1つずつ起動・安定確認しながら導入した。

## リソース使用量の目安（Phase 1計画時点の見積もり）

| サービス | RAM 目安 |
|---------|---------|
| Immich（全体）| ~1.5 GB |
| Samba | ~50 MB |
| OpenWebUI | ~300 MB |
| n8n | ~300 MB |
| Butler Bot | ~200 MB |
| **合計** | **~2.5 GB** |

上記は計画時点の見積もりであり、LiteLLM(1.5GB上限)・Uptime Kuma・Homepage等その後追加した
サービス分は含まれていない。また、このマシンはデスクトップ利用と共用されており（`01_hardware.md`参照）、
実測値・現状の判断は`plan/09_improvements.md`セクション1を参照のこと。
Immich の機械学習モデル（顔認識等）はメモリを多く使うため、無効化するかは実装者判断待ち
（`plan/09_improvements.md`セクション1に切替スイッチの用意状況を記載）。
