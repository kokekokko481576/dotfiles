# 音声インターフェース

## 要件

- 声でエージェントに命令を出す
- Switchbot デバイスの声操作（エアコン・照明など）
- 常時リスニングは難しい → トリガー方式で対応

## アーキテクチャ

```
[マイク入力]
    │
    ▼ (トリガー検出)
[STT: 音声 → テキスト]
    │
    ▼
[AIエージェントコア]（04_ai-butler.md）
    │
    ├──▶ Switchbot API
    ├──▶ ROS2 Bridge
    └──▶ Discord通知 / TTS応答
    
[TTS: テキスト → 音声]
    │
    ▼
[スピーカー出力 or スマホ返答]
```

## トリガー方式の選択肢

常時リスニング（ウェイクワード）はプライバシーと消費電力の問題があるため、
以下のトリガー方式を組み合わせる：

| 方式 | 説明 | 難易度 |
|-----|------|--------|
| **ボタン押し発話** | スマホアプリのボタン押しながら話す（最もシンプル）| 低 |
| **ウェイクワード** | 「ヘイ執事」など検出後に起動 | 中 |
| **Discord PTT** | DiscordのPush-to-Talk機能を流用 | 低 |

→ Phase 1 はスマホアプリ（Tasker + HTTP webhook）またはDiscordのボイス機能で実装。
　 Phase 2 以降でウェイクワードを検討。

## STT（音声認識）

### 候補

| ツール | 方式 | 日本語精度 | 備考 |
|------|------|----------|------|
| **Whisper（OpenAI, ローカル）** | ローカル推論 | 高い | faster-whisper で高速化可 |
| **Google Speech-to-Text API** | クラウド | 高い | クレジット消費 |
| **whisper.cpp** | ローカル（C++）| 高い | CPUでも動く、RAM 少 |

→ Phase 1: **Google STT API**（Gemini クレジットと同じ GCP で管理しやすい）
→ Phase 2: **faster-whisper** でローカル化（GPU PC の恩恵を受けられる）

### Whisper モデルサイズと精度

| モデル | VRAM/RAM | 日本語速度 |
|------|---------|----------|
| tiny | 390 MB | 低精度 |
| base | 740 MB | 実用最小 |
| small | 1.4 GB | バランス良 |
| medium | 3.0 GB | 高精度（現サーバーでは厳しい）|
| large-v3 | 6.2 GB | 最高精度（GPU PC 向け）|

→ 現サーバーで動かすなら **small** を上限とする。

## TTS（音声合成）

| ツール | 方式 | 日本語対応 | 備考 |
|------|------|----------|------|
| **VOICEVOX** | ローカル | ネイティブ | 品質が高い、無料 |
| **Piper + ja モデル** | ローカル | あり | 軽量 |
| **Google TTS API** | クラウド | 高品質 | クレジット消費 |

→ Phase 1: **Google TTS API**（手軽）
→ Phase 2: **VOICEVOX**（ローカル、個性を出せる）

## Switchbot 連携

Switchbot デバイスを声で操作するための連携設計。

### 前提

- Switchbot Hub Mini が必要（Bluetooth デバイスをクラウド経由で制御）
- Switchbot API v1.1 で制御可能

### フロー

```
「エアコンつけて」
    │
    ▼ STT
「エアコンつけて」（テキスト）
    │
    ▼ LLM（意図解析）
device: "エアコン", action: "turnOn"
    │
    ▼ Switchbot API
POST https://api.switch-bot.com/v1.1/devices/{deviceId}/commands
```

### 管理するデバイス一覧（要記入）

| デバイス名 | SwitchbotデバイスID | 操作 |
|----------|-------------------|------|
| エアコン | （要記入）| turnOn / turnOff / setTemperature |
| 照明 | （要記入）| turnOn / turnOff |
| （その他）| | |

## Phase 1 実装スコープ（最小構成）

1. スマホの Tasker アプリで録音 → サーバーに POST
2. サーバー側で Google STT → テキスト変換
3. AIエージェントに渡して実行
4. Google TTS → 音声ファイル生成 → スマホで再生

複雑なウェイクワードや常時リスニングは Phase 2 以降。

## 未決定事項

- [ ] ウェイクワード採用の可否・ツール選定（openWakeWord, Porcupine など）
- [ ] スマホからの音声送信方法（Tasker / 専用アプリ / Discord ボイス）
- [ ] スピーカーをサーバー側に置くか、スマホで再生するか
- [ ] 日本語 TTS の声質・キャラクター選定（VOICEVOX の話者）
- [ ] Switchbot Hub の有無確認
