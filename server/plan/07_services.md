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
| バックエンド設定 | Phase 1: Gemini API, Phase 2: Ollama（GPU PC）|

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
