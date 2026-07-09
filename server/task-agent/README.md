# タスク管理エージェント兼思考ログシステム

設計: `../plan/12_task-management.md`
セットアップ手順（GitHub Project/PAT作成、Discord Bot作成、systemd timer登録）:
`../guide/12_タスク管理エージェント設定.md`

## 概要

GitHub Projects V2のissueをローカルLLM（Ollama, `llama3.2:3b`）が優先度判断し、毎朝Discordに
レコメンドを投稿する。Discordスレッドでの返信を毎晩回収し、返信ごとにパースして該当issueの
Statusを更新する。やり取りの生ログは`/mnt/data/ai/task-agent/`に蓄積する
（将来の「思考のデータベース」化に向けた素材）。

- **クラウドは使わない**: 自宅サーバー（`docker-compose.yml`管理下、`--profile task-agent`）で
  完結する。LLM呼び出しは同一Docker network上の`ollama`コンテナへ。GitHub/Discordへのアクセスは
  1日2回のバッチのみなので、常時稼働のクラウドインフラは不要と判断した。
- **専用のDiscord Botを新規作成する**（butler-botとは別トークン）: 同じBot名でGemini(butler-bot)
  とOllama(task-agent)の発言が混在すると「どのAIが喋っているか」が分かりにくくなるため。
  投稿・スレッド作成・返信取得はREST API経由（Gateway常時接続は不要）。トークン自体は
  `server/.env`の`DISCORD_TOKEN_OLLAMA`/`DISCORD_CHANNEL_OLLAMA`（butler-botの
  `DISCORD_TOKEN_BUTLER`と同じ場所で管理）にあり、docker-compose.ymlが
  `DISCORD_TOKEN`/`DISCORD_CHANNEL_ID`としてこのコンテナに渡す。
- **LLMはGeminiではなくローカルのllama3.2:3b**: 定例タスクで緊急性がないため、コスト・外部依存
  のないローカルモデルを採用。3Bクラスの小型モデルは一発の複雑な指示より、issue/返信単位に
  分解して個別に考えさせる方が安定するため、`llm_client.py`は逐次型のプロンプト構成にしている。

## ローカルでの動作確認

```bash
cd task-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # 値を埋める。DISCORD_TOKEN/DISCORD_CHANNEL_IDは
            # ../.env（server/.env）のDISCORD_TOKEN_OLLAMA/DISCORD_CHANNEL_OLLAMAと同じ値
            # OLLAMA_BASE_URLは自宅サーバー外から実行するならhttp://<サーバーのTailscale IP>:11434
            # DATA_DIRは書き込み可能なローカルパス（例: ./data）に変更

cd src
python job_recommend.py   # 朝のジョブを手元で1回実行
python job_collect.py     # 夜のジョブを手元で1回実行
```

## 本番運用（自宅サーバー、docker-compose + systemd timer）

```bash
cd ~/dotfiles/server
sudo mkdir -p /mnt/data/ai/task-agent && sudo chown -R "$(whoami):$(whoami)" /mnt/data/ai/task-agent
cp task-agent/.env.example task-agent/.env
nano task-agent/.env   # GITHUB_TOKEN, GITHUB_PROJECT_OWNER/NUMBER等
                        # （DISCORD関連はserver/.envのDISCORD_TOKEN_OLLAMA/DISCORD_CHANNEL_OLLAMAを使うので
                        #   docker-compose経由なら空でよい）

docker compose --profile task-agent build task-agent-recommend task-agent-collect
docker compose --profile task-agent run --rm task-agent-recommend   # 動作確認
docker compose --profile task-agent run --rm task-agent-collect     # 動作確認
```

動作確認後、`scripts/systemd/task-agent-recommend.{service,timer}` /
`task-agent-collect.{service,timer}` をsystemdに登録して1日2回自動実行する
（手順: `guide/12_タスク管理エージェント設定.md`）。

## ディレクトリ

| パス | 役割 |
|---|---|
| `src/config.py` | 環境変数読み込み |
| `src/github_client.py` | Projects V2 GraphQL（issue一覧取得・Status更新） |
| `src/llm_client.py` | Ollama呼び出し（優先度評価・レコメンド生成・返信パース） |
| `src/discord_client.py` | Discord REST API |
| `src/logstore.py` | ローカルJSONファイルへの保存（`/app/data`、docker-compose上は`/mnt/data/ai/task-agent`） |
| `src/job_recommend.py` | Job A（朝） |
| `src/job_collect.py` | Job B（夜） |
