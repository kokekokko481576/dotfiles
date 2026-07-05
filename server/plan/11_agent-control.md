# 執事エージェントへのホスト操作権限付与（2026-07-05実装）

## 背景・目的

`04_ai-butler.md`の未決定事項「ファイル操作の権限スコープ」、および`09_improvements.md`
セクション6「AIエージェント（執事）の権限スコープ」で挙げていた懸念（許可リスト方式・
破壊的操作の確認・監査ログ）に対する実装。Discord経由で執事Botに、Claude Code /
Gemini CLI的な「このPC自体を操作できる」能力を持たせる。

## アーキテクチャ

```
[Discord] ←→ [butler-bot コンテナ]              [ホスト(kokkoユーザー)]
                 discord.py / LLM呼び出し           agent_executor.py (systemd常駐)
                 agent_tools.py（判断ロジック）  ←────Unixソケット────→ 実際のシェル実行
                 ・許可リスト判定                  /mnt/data/ai/agent/butler-agent.sock
                 ・Discord確認フロー
```

- **butler-botコンテナ**: Discord・LiteLLM(Vertex AI Gemini)という外部ネットワークと直接
  やり取りし、サードパーティ依存(discord.py, aiohttp, openai等)も多い。攻撃面が広い。
- **agent_executor.py**: `scripts/agent_executor.py`。ホスト上でsystemdサービス
  (`scripts/systemd/butler-agent.service`)として`kokko`ユーザー権限（sudo可・dockerグループ）
  で常駐し、Unixソケット越しに来たリクエストされたコマンド/ファイル操作をそのまま実行するだけの
  薄い層。判断ロジックは一切持たない。
- 両者をコンテナではなく別プロセス・別ユーザー(root-in-containerではなくkokko)に分離することで、
  「botコンテナ自体、あるいはその依存パッケージが何らかの形で乗っ取られた場合」の被害範囲を、
  「このソケットプロトコルで許されている操作」に限定する狙い。ただし後述のとおり、
  執事本人(LLM)が悪意ある/誤った操作を要求してくるケースに対する防御は別レイヤー(許可リスト+確認)で行う。

## 権限モデル

### 1. 所有者限定 (`DISCORD_OWNER_ID`)

`.env`の`DISCORD_OWNER_ID`にDiscordユーザーIDを設定した場合のみ、そのユーザーからのメッセージに
対してツール(`tools=`)をLLMに渡す。未設定なら常に無効（コード変更前と完全に同じ動作）。
単一運用前提（`08_security.md`）だが、念のためコードレベルでも他ユーザーには絶対にツールを渡さない。

### 2. 許可リスト方式（`ai/src/agent_tools.py`の`classify_shell`）

「危険なコマンドを列挙して弾く」のではなく、「読み取り専用・調査系として安全だと確認できたコマンドのみ
自動実行し、それ以外(未知のコマンドも含む)は全て要確認」という設計。デノリスト方式は列挙漏れのリスクが
高いため。`&&`・`|`・リダイレクト等を含む複合コマンドは、安全に見えても常に要確認扱いにする。

- 自動実行: `ls` `cat` `df` `git status/log/diff` `docker ps/compose ps/compose logs`
  `systemctl status` `journalctl` `curl http://localhost:...` `smartctl -a` 等の読み取り系
- 要確認: 上記以外全て（`rm` `sudo` `docker compose down` `git push` `systemctl restart` 等）
- `write_file`は常に要確認（新規作成・上書き問わず）

### 3. 破壊的操作の確認フロー

要確認と判定されたツール呼び出しは、実行前に対象チャンネルへ内容を投稿し、✅/❌のリアクションで
持ち主（`DISCORD_OWNER_ID`本人のみ）の承認を待つ（5分でタイムアウト→却下扱い）。
**Botに「リアクションの追加」権限が必要**（招待時のOAuth2スコープに含まれていなかったため、
Discordサーバー設定でBotロールに追加する必要がある。下記「有効化手順」参照）。

### 4. 監査ログ

すべてのツール呼び出し（自動実行・承認・却下・タイムアウト含む）を
`/mnt/data/ai/context/agent_audit.jsonl`にJSONL形式で記録（restic日次バックアップの対象範囲内）。

### 5. 機密情報アクセスの拒否（`is_sensitive_path`）

`read_file`/`write_file`/`list_dir`は、`.env` `*.pem` `id_rsa`等の認証情報らしきパスを
問答無用で拒否する。**ただし`run_shell`経由での間接的な読み出し（`base64`、Pythonでのopen等）までは
防げない。** これは意図的なトレードオフ：単一ユーザー・実運用時の攻撃者は基本的に本人しかいない
（＝Discordアカウント乗っ取り等が起きない限り悪用されない）という前提のもとでの最低限のガードであり、
完全なサンドボックスではない。運用者（本人）は、LLM(Google Vertex AI)に送った内容は外部サービスに
渡っている点を踏まえてツール利用すること。

## 有効化手順（実施者が行う必要がある。ここまでは自動化できない）

1. Discordで開発者モードを有効化 → 自分のアイコンを右クリック →「ユーザーIDをコピー」
2. `.env`に`DISCORD_OWNER_ID=<コピーしたID>`を追記
3. Discordサーバー設定 →「ロール」→ Botのロール →「Add Reactions（リアクションの追加）」権限をON
   （招待時のスコープに含めていなかったため。招待し直さなくてもロール権限の追加だけで反映される）
4. `cd ~/dotfiles/server && sudo docker compose up -d butler-bot`（`.env`の変更を反映するため再作成）
5. `#butler-chat`で試す。読み取り系（例:「dockerのコンテナ一覧を見せて」）はすぐ実行され、
   変更系（例:「n8nコンテナを再起動して」）は✅/❌の確認が挟まる

## 既知の制約・今後の課題

- `agent_executor.py`は`kokko`（NOPASSWD ALL sudo・dockerグループ）権限で動くため、確認フローを
  通過した操作は実質ホストroot相当のことができる。確認フローが最後の砦であり、慎重に運用すること。
- 許可リストのチューニングは今後の運用で調整する（例: `git commit`は現状「要確認」だが、
  ローカルコミットは`git reset`で戻せるため自動実行リストに入れてもよいかもしれない）。
- Discordアカウント自体が乗っ取られた場合、この権限モデルは無力（＝Discordの2要素認証は別途必須）。
- `write_file`の確認メッセージはパス+内容全文をそのまま貼るだけ（diff表示ではない）。
  Discordの1メッセージ上限(2000字)を超える内容は見切れるため、大きなファイル生成には注意。
