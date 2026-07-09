# タスク管理エージェント兼思考ログシステム

作成日: 2026-07-06（2026-07-06 実装中に構成変更: GCP撤去→自宅サーバー内で完結する構成へ）
ステータス: 実装中

## 背景・目的

### 課題
- 日記を書く習慣が続かない（三日坊主を繰り返している）
- 日々のタスク管理はDiscordの既存Bot（Butler Bot）への投稿で運用できているが、振り返りには使われていない
- タスクが複数の文脈（研究・個人雑務・趣味開発）に分散しており、GitHub Projectへの起票が面倒
- 日記を「思考のデータベース」として活用したいが、具体的に何を残すべきかが定まっていない

### 目的
1. GitHub Projectと連携し、その日やるべきタスクを自動でレコメンドする
2. Discordでの進捗報告を検知し、GitHub Project側のステータスを自動更新する
3. やり取りの生ログを蓄積し、将来的に「思考のデータベース」として活用できる状態を作る
4. 日記の内容（何を書くか）は今は決めず、まず生ログを貯めながら後で決める

### 方針
- 最初から作り込まず、小さく作って動かしながら考える（MVPファースト）
- 日記のテンプレート設計は保留し、まずは自動生成される生ログをそのまま貯める

## 決定事項（初期設計からの変更点）

初期設計はGitHub連携部分をCloud Run + Cloud Scheduler + Firestore + Vertex AI Geminiという
クラウド構成で考えていたが、実装着手時に以下の指摘を受けて全面的に見直した。

| # | 項目 | 初期案 | 変更後 | 理由 |
|---|------|--------|--------|------|
| 1 | 通知・報告チャネル | Slack/Discord未決定→新規Bot | Discord、**既存のbutler-bot Discordトークンを共用** | （一時的な決定。#5で撤回） |
| 2 | LLM | Vertex AI Gemini | **Ollama (`llama3.2:3b`、自宅サーバー内で既に稼働中)** | 定例タスク（1日2回のバッチ）で緊急性がなく、無料のローカルモデルで十分。3Bクラスの弱いモデルは一発の複雑な指示より逐次処理（issue/返信ごとに個別に考えさせて後で束ねる）の方が安定した結果になりやすいため、時間をかけて逐次型のプロンプト構成にした |
| 3 | 実行基盤 | Cloud Run Jobs + Cloud Scheduler | **自宅サーバーのdocker-compose(`--profile task-agent`) + systemd timer** | LLM呼び出しがOllama(自宅サーバー内、Tailscale経由でしか到達不能)に変わったため、クラウド側から呼べなくなった。同時にGitHub/Discordアクセスも自宅サーバー内で完結させられるようになり、クラウドインフラ一式が不要になった |
| 4 | 生ログ・状態の保存先 | Firestore | **ローカルJSONファイル**（`/mnt/data/ai/task-agent/`、1日1ファイル） | クラウドを使わなくなったことに伴う変更。`/mnt/data`は既存のrestic日次バックアップ対象範囲内（`10_バックアップ.md`）なので、バックアップ運用もそのまま乗る |
| 5 | 通知・報告チャネル（再変更） | butler-botとトークン共用 | **task-agent専用のDiscord Botを新規作成**（butler-botとは別トークン） | 実際にチャンネルを作った上で気づいた問題: 同じBot名で発言すると、Gemini(butler-bot)とOllama(task-agent)のどちらが喋っているか見分けがつかず分かりにくい。アクセス権の観点では共用で足りていたが、UI上の見分けやすさを優先して撤回した |

## 全体アーキテクチャ

```
[systemd timer: 毎朝07:00 JST — scripts/systemd/task-agent-recommend.timer]
  → docker compose --profile task-agent run --rm task-agent-recommend
      1. GitHub Projects V2(個人Organization)からissue一覧取得(GraphQL)
      2. Ollama(llama3.2:3b)で優先度判断・レコメンド文生成（issueごとに評価→まとめて生成の2段階）
      3. Discordへ投稿（task-agent専用のBotトークンで、スレッドを立てて返信を受け付ける）
      4. /mnt/data/ai/task-agent/<日付>.json に「本日のレコメンド」を保存（issue一覧・スレッドID等）

[systemd timer: 毎晩22:00 JST — scripts/systemd/task-agent-collect.timer]
  → docker compose --profile task-agent run --rm task-agent-collect
      1. 保存済みJSONから当日のスレッドIDを読み出す
      2. Discordスレッドの返信履歴を取得
      3. Ollama(llama3.2:3b)で返信1件ごとに「どのissueの話か」「進捗ステータス」をパース
         （GitHub Project側のStatusフィールドの選択肢に限定してパースさせ、誤マッチを抑制）
      4. GitHub Project側のStatusフィールドを更新(GraphQL mutation)
      5. やり取りの生ログ(レコメンド文＋ユーザー返信＋パース結果)を同じJSONファイルに追記
```

即時応答は不要なため、常時待ち受けのWebhookサーバーは持たず、定期実行＋ポーリング方式とする。
すべて自宅サーバー内（Docker network上の`ollama`コンテナ、`docker-compose.yml`管理下）で完結する。

## GitHub構成

### Organization
- **個人Organization**にGitHub Project (V2) を1本作成し、これを統合ボードとする
  - ※当初は研究室Organizationの案もあったが、個人Organizationに変更
- ボードビュー／タイムラインビューを引き続き使用

### リポジトリ構成
| 種別 | リポジトリ | 備考 |
|---|---|---|
| 研究タスク | 研究室Organization内の既存リポジトリ | 個人Organizationのプロジェクトにissueを追加する形で連携 |
| 個人の雑務 | `personal-tasks`（新規作成） | コードを伴わない雑務issueを格納。ラベルで分類 |
| 趣味プロジェクト | 既存の複数リポジトリ | 既存issueをプロジェクトに追加。issueがそのままdevlog・引き継ぎ資料として機能する |

### Draft Issueについて
- **不採用**。理由：ラベル・担当者などのメタデータが使えない/少なく、分類の柔軟性が落ちるため
- 個人タスクも含め、すべて通常issueとして作成する方針に統一

### ラベル設計（案）
- `research` / `personal` / `hobby:プロジェクト名` などで種別を分類
- レコメンド生成時にラベルでグルーピングして提示する

### 認証
- **Fine-grained Personal Access Token**を使用
- 対象リポジトリ・権限（Projects: 読み書き、Issues: 読み書き）を限定
- 有効期限を設定（例：90日）し、定期的にローテーション
- 実際の値・トークン発行手順は `guide/12_タスク管理エージェント設定.md` 参照

## 実行基盤

| 項目 | 選定 |
|---|---|
| コンピュート | 自宅サーバー、`docker-compose.yml`の`task-agent-recommend`/`task-agent-collect`(`--profile task-agent`) |
| スケジューリング | systemd timer（`scripts/systemd/task-agent-recommend.timer` / `task-agent-collect.timer`） |
| ストレージ（生ログ・日次状態） | ローカルファイル（`/mnt/data/ai/task-agent/`、1日1ファイルのJSON） |
| 機密情報 | GitHub PAT/Ollama設定は`task-agent/.env`、Discord Botトークンは`server/.env`の`DISCORD_TOKEN_OLLAMA`/`DISCORD_CHANNEL_OLLAMA`（butler-botの`DISCORD_TOKEN_BUTLER`と同じ場所で一元管理。いずれもgit管理対象外） |

常時起動サーバーを持たないことで、Webhook受信のためのポート開放・固定IP・DDNS等の設定が不要になる。

## LLM構成

| 用途 | モデル | 理由 |
|---|---|---|
| タスク優先度判断・レコメンド生成 | Ollama `llama3.2:3b`（自宅サーバー、`07_services.md`で導入済み） | 定例バッチで緊急性がなく無料。issueごとに個別評価→まとめて生成の2段階にして小型モデルの精度を補っている |
| Discord返信のパース→タスクの特定・GraphQL mutation組み立て | Ollama `llama3.2:3b` | 誤マッチのリスクを抑えるため、GitHub側のStatus選択肢を閉集合としてプロンプトに与え、返信1件ごとに個別処理する |

自宅サーバー上の`litellm`コンテナ（Vertex AI中継、`04_ai-butler.md`）は今回使わない。Ollamaは
Docker network内で`http://ollama:11434`として直接到達できるため中継が不要。

## 通知・報告インターフェース

- **task-agent専用のDiscord Botを新規作成する**（butler-bot（`11_agent-control.md`）とは別トークン、
  決定事項#5参照）。同じBot名でGemini(butler-bot)とOllama(task-agent)の発言が混在すると見分けが
  つかないため。task-agentはDiscord REST APIのみを使い、常時接続のGatewayは持たない
- やり取りの流れ：
  1. 朝：Botがレコメンドタスクをスレッド付きで投稿
  2. ユーザーがスレッドで進捗を返信（現行運用と同様の書き方でよい）
  3. 夜間バッチが返信を回収し、GitHub Projectを自動更新

## 日記（思考ログ）機能

### 現状の方針
- テンプレート項目や書く内容は**未確定**
- まずは以下を自動的に生ログとして蓄積する：
  - その日のレコメンド文（Ollama生成）
  - ユーザーの返信内容（進捗報告時のテキスト）
  - タイムスタンプ、紐づくissue ID
- スキーマを固めすぎず、後から分析して価値があるかを検証してから、書式・保存先（ベクトルDB化など）を再設計する

### 保留事項（今後決める）
- 日記に「意思決定の理由」など、進捗ログ以外の内容を含めるかどうか
- 生ログを実際に「思考のデータベース」として使う具体的なユースケース（検索、パターン分析など）

## 実装

コードは `server/task-agent/` 配下。詳細は同ディレクトリの `README.md` および
`guide/12_タスク管理エージェント設定.md`（ユーザーが手動で行う必要のあるセットアップ手順）を参照。

```
server/task-agent/
├── src/
│   ├── config.py           # 環境変数読み込み
│   ├── github_client.py    # Projects V2 GraphQL（issue一覧取得・Status更新）
│   ├── llm_client.py       # Ollama呼び出し（優先度評価・レコメンド生成・返信パース）
│   ├── discord_client.py   # Discord REST API（投稿・スレッド作成・返信取得）
│   ├── logstore.py         # ローカルJSONファイルへの日次状態・生ログ保存
│   ├── job_recommend.py    # Job A: 朝のレコメンド投稿
│   └── job_collect.py      # Job B: 夜の返信回収・Project更新
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md

server/scripts/systemd/
├── task-agent-recommend.service / .timer   # 毎朝07:00
└── task-agent-collect.service / .timer     # 毎晩22:00
```

## 未解決事項（Open Issues）

| # | 内容 |
|---|---|
| ~~1~~ | ~~Slack / Discordどちらを通知・報告チャネルにするか~~ → **Discord、task-agent専用Botで決定**（当初はbutler-botとの共用を検討したが、発言者が見分けにくいため撤回。決定事項#5） |
| ~~2~~ | ~~実行基盤（Cloud Run vs 自宅サーバー）~~ → **LLMをOllamaにした結果、自宅サーバー内で完結する構成に決定** |
| 3 | 既存の趣味プロジェクトリポジトリのissueを、個人OrganizationのProjectへ追加する初期セットアップ作業（`guide/12`参照、ユーザー手動） |
| 4 | レコメンド生成のプロンプト設計の継続チューニング（`llama3.2:3b`は弱いモデルなので、実運用しながら逐次プロンプトの粒度を調整する） |
| 5 | 日記コンテンツのテンプレート化（生ログ蓄積後に再検討） |
| 6 | Fine-grained PATの90日ローテーション運用（現状は手動更新。期限切れ時のアラートは未実装） |
