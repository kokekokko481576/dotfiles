# 02. APIキーの取得と .env 設定

## 手順の全体像

`.env` ファイルに以下のAPIキーを設定します：

| キー | 取得元 | 必須度 |
|-----|------|--------|
| `DB_PASSWORD` | 自分で生成 | **必須**（Immich起動に必要） |
| `GEMINI_API_KEY` | Google AI Studio | **必須**（AIチャットに必要） |
| `DISCORD_TOKEN_BUTLER` | Discord Developer Portal | ★（Butler Bot用） |
| `N8N_PASSWORD` | 自分で決める | **必須**（n8nログイン用） |
| `SWITCHBOT_TOKEN` | Switchbotアプリ | 任意 |

---

## ステップ1: .env ファイルを作成

```bash
cd ~/dotfiles/server
cp .env.example .env
nano .env   # または好きなエディタで
```

---

## ステップ2: DB_PASSWORD を生成・設定

```bash
openssl rand -hex 32
```

表示された文字列をコピーして、`.env` の `DB_PASSWORD=` の後に貼り付けます。

```
DB_PASSWORD=ここに生成した文字列
```

---

## ステップ3: Gemini API キーの取得

1. https://aistudio.google.com/app/apikey にアクセス
2. **「APIキーを作成」** をクリック
3. 表示されたキーを `.env` の `GEMINI_API_KEY=` に設定

```
GEMINI_API_KEY=AIzaSy...
```

> 無料枠: Gemini 2.0 Flash は月に十分な無料クォータあり（個人利用レベルは無料で賄える）

---

## ステップ4: N8N_PASSWORD を設定

n8n管理画面にログインするためのパスワードを決めます（英数字推奨）：

```
N8N_PASSWORD=好きなパスワード
```

---

## ステップ5: OPENWEBUI_SECRET を設定（任意）

OpenWebUIのセッション暗号化キーです。ランダム文字列を生成して設定：

```bash
openssl rand -hex 32
```

```
OPENWEBUI_SECRET=生成した文字列
```

---

## ステップ6: Switchbot トークンの取得（任意）

Switchbotデバイスを持っている場合のみ：

1. Switchbotアプリを開く
2. **プロフィール** → **設定** → **アプリバージョン** を **10回タップ**
3. 「開発者向けオプション」が表示される
4. トークンとシークレットをコピーして `.env` に設定

```
SWITCHBOT_TOKEN=token...
SWITCHBOT_SECRET=secret...
```

---

## ステップ7: 執事BotのWeb検索について（設定不要）

執事Botの `web_search` ツールは **Vertex AI Geminiの「Grounding with Google Search」**
を使う。LiteLLM経由で `tools=[{"googleSearch": {}}]` を渡すだけで動くため、
Vertex AI（`vertex-sa.json`）が設定済みなら**追加のAPIキーは不要**。
`fetch_url`（URL閲覧）も同様にキー不要。

過去の変遷（同じ轍を踏まないための記録）:
- DuckDuckGoスクレイピング → このサーバーのIPがbot対策で常時ブロックされ断念
- Google Custom Search JSON API → キー作成・API有効化・billing紐付けを全て行っても
  `This project does not have the access to Custom Search JSON API` (403) が解消せず断念。
  `.env` の `GOOGLE_CSE_API_KEY` / `GOOGLE_CSE_ID` はこの名残で、現在は未使用（削除してよい）

動作確認（コンテナ内から）:

```bash
docker exec butler_bot python -c "
import asyncio, sys; sys.path.insert(0, '/app/src')
import web_tools
print(asyncio.run(web_tools.web_search('今日の大阪の天気')))
"
```

コスト注意: groundingは通常のGemini呼び出しより高い（Vertex AIのGrounding with
Google Search課金、無料枠超過後は検索1,000回あたり$35）。個人のチャット用途の
頻度なら実質無料枠内に収まる。

---

## .env の権限設定（重要）

```bash
chmod 600 ~/dotfiles/server/.env
```

これで他のユーザーから読めなくなります。

---

## 確認

```bash
grep -E "^[A-Z_]+=" ~/dotfiles/server/.env | grep -v "^#"
```

`=` の後が空白のものが残っていないか確認してください。
Discord関連は `03_Discord_Bot作成.md` で設定します。
