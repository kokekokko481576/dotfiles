# 13. ワニ博士タスク管理アプリ

たまごっち風のドット絵キャラ「ワニ博士」(大阪大学マスコット)が、その日のタスク進捗で
元気になったりぐったりしたりするタスク管理アプリ。タスクの正はGitHub Projects V2
(12_task-management.mdと同じProject)で、スマホ(PWA)とDiscord(butler-bot)の両方から
進捗を更新できる。

## 構成

```
[Pixel 7a PWA] --Tailscale HTTPS(8443)--> [wani コンテナ :8090]
[Discord] --> [butler-bot] --compose内HTTP--> [wani コンテナ :8090]
                                                |
                                                +-- GitHub Projects V2 (GraphQL)  ←タスクの正
                                                +-- /mnt/data/ai/wani/*.json      ←気分・履歴・モック
```

- **wani** (`server/wani/`): FastAPI。REST API + PWA静的配信を1コンテナで担う。
  - `GET /api/state` — 気分・タスク一覧・進捗
  - `POST /api/tasks/{item_id}/status` — Status更新(気分イベントも発火)
  - GitHub未設定(`GITHUB_TOKEN`空)なら**モックモード**で動く。環境変数は
    `task-agent/.env`をそのまま共用(設定箇所を1つにするため)。
- **butler-bot**: `list_tasks` / `update_task_status` ツールを追加。会話から
  「これ終わったで」→ Done化 → ワニ博士の気分報告、ができる。
- 状態はすべてwani APIに集約。**PWAとDiscordのどちらから更新しても同じ気分が動く。**

## 気分エンジン (`wani/src/mood.py`)

- 気分は0-100の連続値。Done +18 / In Progress +6 / Doneから戻す -10
- 起床時間帯(7-24時)に1.5/時で減衰。0-7時は睡眠(減衰なし・寝スプライト表示)
- レベル: excellent(≥75) / happy(≥45) / normal(≥20) / tired(<20)
- streak: 1件以上Doneにした連続日数
- パラメータは全部このファイルの定数。飽きたら調整する

## ドット絵 (`wani/tools/gen_sprites.py`)

32x32ピクセル、5表情(normal/happy/excellent/tired/sleeping)×各2-4フレーム。
ASCIIグリッドが原本で、実行すると`static/sprites.js`とPWAアイコンPNGを再生成する
(依存ライブラリなし)。キャラを差し替えたいときはこのファイルだけ編集すればよい。

## ネイティブAndroidアプリ化の調査メモ(両方やる場合の次の一手)

PWAのまま困らなければ不要。Play Storeに置きたい/通知やウィジェットが欲しくなったら:

1. **TWA (Trusted Web Activity)** — 最有力。既存PWAをそのままAPKに包む。
   [Bubblewrap](https://github.com/GoogleChromeLabs/bubblewrap)でコマンド一発、
   コード変更ほぼ不要。ただし公開URLとHTTPSが必要(Tailscale内URLはPlay配布とは相性が
   悪い。自分用のサイドロードAPKなら問題ない)。
2. **Capacitor** — Web資産を包んでネイティブAPI(通知等)も呼べる。中間の選択肢。
3. **Kotlin+Compose** — フル書き直し。ウィジェットやWear対応までやるなら。

自分用ならTWA+サイドロードで十分。まずPWAを1週間使ってから決めるのが良い。

## 収益化について(ユーザーの質問への回答)

- **ワニ博士のままでは不可。** ワニ博士は大阪大学の公式マスコットで著作権・商標は
  大学側にある。個人利用の範囲なら実害は考えにくいが、配布・販売は許諾が要る。
  リリースするならキャラをオリジナルに差し替える(gen_sprites.pyの編集だけで済む設計)。
- 「タスク完了でキャラが育つ」系アプリはHabitica、Finch等の先行が強い。差別化するなら
  「GitHub Projects直結」「自宅サーバー完結でデータが手元に残る」という開発者向けの
  切り口が現実的。まずは自分が毎日使うものに育てるのが先。

## 将来アイデア(未実装)

- 朝ブリーフィングに今日のタスクとワニ博士の気分を含める
- 完了時にDiscordへワニ博士のスタンプ的リアクション
- 気分の長期グラフ(履歴データは`/mnt/data/ai/wani/wani_state.json`に貯まっている)
- レベル/進化(累計Doneで博士帽が豪華になる等)
