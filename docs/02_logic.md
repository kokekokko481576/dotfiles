# 第2章：条件分岐とループ 🔄

プログラミングっぽくなってくるよ！
「もしファイルがなかったら作る」とか「メニューを表示し続ける」とか、dotfiles作りには欠かせない技術だね。

## 1. 「もし〜なら」 (`if`)

一番大事な構文！書き方が独特だから、最初はコピペで覚えちゃおう。

```bash
#!/bin/bash

NAME="Kokko"

if [ "$NAME" = "Kokko" ]; then
    echo "やあ、マスター！"
else
    echo "誰だお前は！"
fi
```

### ⚠️ 注意点
- `[` と `]` の内側には **必ずスペースが必要**！
    - `["$NAME"...]` ❌ ダメ
    - `[ "$NAME" ... ]` ⭕️ OK

## 2. ファイルやフォルダがあるかチェックする

`dotfiles` で一番使うのがこれ！
「ファイルが存在するか？」を調べる便利な記号があるんだ。

- `-f` : ファイルがあるか (File)
- `-d` : ディレクトリがあるか (Directory)
- `!`  : 〜じゃない (Not)

```bash
#!/bin/bash

# ファイルがあるかチェック
if [ -f "install.sh" ]; then
    echo "install.sh は存在します！"
fi

# ディレクトリがない場合（!を使用）
if [ ! -d "/home/kokko/nazo_folder" ]; then
    echo "謎のフォルダはありません。作ります..."
    mkdir "/home/kokko/nazo_folder"
fi
```

`install.sh` の中で「すでに `~/.zprezto` があったらインストールをスキップする」とかに使ってるのはこの技術だよ！

## 3. 繰り返す (`while`, `for`)

### メニューを表示し続ける (`while`)

`install.sh` でメニューを出してるのは `while` ループだよ。

```bash
while true; do
    echo "1. 挨拶する"
    echo "q. 終了"
    
    read -p "選んでね: " choice

    case $choice in
        1)
            echo "こんにちは！"
            ;;
        q)
            echo "ばいばい！"
            exit 0  # スクリプトを終了
            ;;
        *)
            echo "よくわからないよ..."
            ;;
    esac
done
```

- `while true`: 「無限に繰り返せ！」って意味。
- `case ... esac`: 「もし1なら〜、qなら〜」っていう分岐を見やすく書く方法。

---

[次へ進む (関数と実践) 👉](./03_practical.md)
