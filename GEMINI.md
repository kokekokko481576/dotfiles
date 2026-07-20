README.mdを見る

Gemini CLIへの指示: 日本語で返答してください。

# コミットメッセージ規約

Semantic Commit Messageを採用しています。

## フォーマット

フォーマット: `<Type>: <Emoji> #<Issue Number> <Title>`
例: `feat: ✨ #123 ログイン機能の実装をする`

- TypeとTitleは必須
- Issue Numberは強く推奨（無い場合は `#<Issue Number>` の部分を省略する）
- Emojiは任意
- Description（スリーライン）は任意

## Type

どんなコミットなのかシュッと分かるようにPrefixとしてコミットの種別を書きます。
Semantic Commit Messageと同様の種別を使います。

- `chore`: タスクファイルなどプロダクションに影響のない修正
- `docs`: ドキュメントの更新
- `feat`: ユーザー向けの機能の追加や変更
- `fix`: ユーザー向けの不具合の修正
- `refactor`: リファクタリングを目的とした修正
- `style`: フォーマットなどのスタイルに関する修正
- `test`: テストコードの追加や修正
