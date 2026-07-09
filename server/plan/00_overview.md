# 自宅サーバー 全体概要

## 目的

個人用の自宅サーバーを段階的に構築する。
最終形はファイルサーバー・AIエージェント（執事）・ロボット制御基盤の三層構成。

## フェーズ定義

| フェーズ | タイミング | 主な目標 |
|---------|-----------|---------|
| Phase 1 | 今すぐ | ファイルサーバー・リモートアクセス・AIチャット（Gemini API）|
| Phase 2 | 自作PC完成後 | ローカルLLM（Ollama）・執事エージェント本格稼働 |
| Phase 3 | ロボット製作後 | ROS2連携・音声制御・Switchbot統合 |

## 設計方針

- **軽量優先**：RAM 7.1 GB の制約を常に意識し、重いサービスは後回し
- **Docker Compose で全管理**：`server/` ディレクトリをdotfilesに含め再現可能にする
- **API切替可能**：Gemini API ↔ ローカルOllama をフロントエンド設定だけで切り替え
- **段階的拡張**：Phase 1 の構成を壊さずに Phase 2・3 を乗せられる設計
- **一人運用**：マルチユーザー設計は不要。ただし限定リンクでの外部共有は対応する

## ディレクトリ構成

計画当初の予定に加え、運用の中で`guide/`（手順書）・`litellm/`（Vertex AI中継設定）・
`homepage/`（ダッシュボード設定）が増えている。詳細な最新版は`07_services.md`参照。

```
server/
├── plan/                  # この要件定義（本ディレクトリ）
├── guide/                 # 実施者が手を動かす手順書
├── docker-compose.yml     # 全サービスの定義
├── .env.example           # 環境変数テンプレート（認証情報は .env に分離）
├── samba/                 # Samba設定
├── litellm/               # Vertex AI Gemini中継(LiteLLM)の設定
├── homepage/              # ダッシュボードの設定
├── ai/                    # AIエージェント関連（Butler Bot、自宅サーバー上でdocker-compose管理）
├── task-agent/            # タスク管理エージェント兼思考ログシステム（12_task-management.md）
│                          # docker-compose.ymlに --profile task-agent として定義、
│                          # systemd timer(scripts/systemd/task-agent-*.timer)から1日2回起動
└── scripts/               # セットアップ・運用スクリプト
```

## 未解決・後回し事項

- 自作PC のスペック（GPU / VRAM）未定
- ロボットのハードウェア構成未定
- 音声インターフェースのトリガー方式（詳細は 05_voice.md）
- バックアップ戦略（外部ストレージ or クラウド）
- サーバー本体でのダッシュボード表示・音声対応（詳細は 10_dashboard-voice.md、実機確認待ち）
