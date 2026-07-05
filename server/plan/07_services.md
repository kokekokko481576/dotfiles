# サービス管理

## 方針

- 全サービスを Docker Compose で管理
- `server/docker-compose.yml` で一元定義
- 環境変数（APIキー等）は `.env` に分離し、`.env.example` のみをgit管理
- ボリュームは `/mnt/data/` 配下に集約

## Phase 1 サービス構成

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
  whisper:           # STT（将来ローカル化）
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
| ベース | Python 3.12 + discord.py（Phase 1実装はGemini API直呼び出し、LangGraph等は未採用）|
| ポート | なし（アウトバウンドのみ）|
| ボリューム | `/mnt/data/ai/context:/app/context` |
| 環境変数 | `GEMINI_API_KEY`, `DISCORD_TOKEN`, `SWITCHBOT_TOKEN` |

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
├── .env.example           # テンプレート（git管理対象）
├── .env                   # 実際の認証情報（.gitignore 対象）
├── samba/
│   └── smb.conf
├── ai/
│   ├── Dockerfile         # Butler Bot
│   ├── requirements.txt
│   └── src/
└── scripts/
    ├── setup.sh           # 初期セットアップ（マウント・権限設定）
    └── update.sh          # サービス更新
```

## .env.example テンプレート

```bash
# Google AI
GEMINI_API_KEY=

# Discord
DISCORD_TOKEN=
DISCORD_GUILD_ID=
DISCORD_CHANNEL_NOTIFY=

# Switchbot
SWITCHBOT_TOKEN=
SWITCHBOT_SECRET=

# Immich
DB_PASSWORD=

# Ollama（Phase 2）
OLLAMA_BASE_URL=http://gpu-pc:11434
```

## 起動・管理コマンド

```bash
# 全サービス起動
docker compose up -d

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

## リソース使用量の目安（Phase 1）

| サービス | RAM 目安 |
|---------|---------|
| Immich（全体）| ~1.5 GB |
| Samba | ~50 MB |
| OpenWebUI | ~300 MB |
| n8n | ~300 MB |
| Butler Bot | ~200 MB |
| **合計** | **~2.5 GB** |

OS + バッファで 7.1 GB のうち約 4.5 GB を使用する計算。ギリギリ許容範囲。
Immich の機械学習モデル（顔認識等）はメモリを多く使うため、不要なら無効化する。
