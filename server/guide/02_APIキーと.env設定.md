# 02. APIキーの取得と .env 設定

## 手順の全体像

`.env` ファイルに以下のAPIキーを設定します：

| キー | 取得元 | 必須度 |
|-----|------|--------|
| `DB_PASSWORD` | 自分で生成 | **必須**（Immich起動に必要） |
| `GEMINI_API_KEY` | Google AI Studio | **必須**（AIチャットに必要） |
| `DISCORD_TOKEN` | Discord Developer Portal | ★（Butler Bot用） |
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
