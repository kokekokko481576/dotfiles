# 03. Discord Bot の作成

## 概要

このステップでは：
1. Discord Developer Portal でBotを作成
2. BotをあなたのDiscordサーバーに招待
3. チャンネルIDを取得して `.env` に設定

---

## ステップ1: Discordサーバーの準備

まだ執事用のDiscordサーバーがない場合は作成します：

1. Discordアプリを開く
2. 左サイドバーの **「+」** をクリック
3. **「自分用に作成」** → **「趣味や友達向け」**
4. サーバー名: `homeserver`（なんでも可）

### チャンネル作成

サーバー内に以下のチャンネルを作成：

| チャンネル名 | 用途 |
|------------|-----|
| `#butler-chat` | AIとの対話（こちらから話しかける） |
| `#butler-notify` | AIからの能動通知（カレンダー・アラート等） |

---

## ステップ2: Bot アプリケーションの作成

1. https://discord.com/developers/applications にアクセス
2. **「New Application」** をクリック
3. 名前: `butler`（なんでも可）→ **「Create」**

---

## ステップ3: Bot の設定

1. 左メニューの **「Bot」** をクリック
2. **「Reset Token」** → **「Yes, do it」**
3. 表示されたトークンをコピー（**一度しか表示されません！**）
4. `.env` に設定：
   ```
   DISCORD_TOKEN=コピーしたトークン
   ```

### 権限の設定

Bot ページで以下を有効にする：

- **Message Content Intent** → **ON** にする
  （このチェックがないとメッセージを読めません）

---

## ステップ4: Bot をサーバーに招待

1. 左メニューの **「OAuth2」** → **「URL Generator」**
2. **SCOPES** で `bot` にチェック
3. **BOT PERMISSIONS** で以下にチェック：
   - `Send Messages`
   - `Read Message History`
   - `Mention Everyone`（通知用）
4. 生成されたURLをブラウザで開く
5. 招待先のサーバーを選択 → **「認証」**

---

## ステップ5: チャンネルIDとサーバーIDの取得

### 開発者モードを有効にする

1. Discord設定 → **「詳細設定」**
2. **「開発者モード」** を ON

### IDの取得

- **サーバーID**: サーバー名を右クリック → **「サーバーIDをコピー」**
- **チャンネルID**: チャンネル名を右クリック → **「チャンネルIDをコピー」**

`.env` に設定：

```
DISCORD_GUILD_ID=サーバーID
DISCORD_CHANNEL_NOTIFY=butler-notifyのチャンネルID
DISCORD_CHANNEL_CHAT=butler-chatのチャンネルID
```

---

## ステップ6: 動作確認（Botを有効にした後）

`docker compose --profile butler up -d` でBotを起動後：

1. `#butler-chat` で `@butler こんにちは` と送信
2. Botが返事をすれば成功！

### コマンド一覧

| コマンド | 説明 |
|---------|-----|
| `@butler <メッセージ>` | AIと会話 |
| `!status` | サーバー状態確認 |
| `!health` | 内部サービス（Immich/n8n/LiteLLM等）の死活確認 |
| `!clear` | 会話履歴リセット |

### さらに進んだ使い方

執事にこのサーバーホスト自体を操作させたい場合（シェルコマンド実行・ファイル読み書き）は、
`11_執事エージェント権限有効化.md`を参照。
