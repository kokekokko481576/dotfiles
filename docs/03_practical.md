# 第3章：関数と実践編 🛠️

最後は、実際の `dotfiles` のコードがどうなってるのか、読み解けるようになろう！

## 1. 関数（処理をまとめる）

何度も同じことを書くのは面倒だよね？
`create_safe_link` みたいに、名前をつけて処理をまとめることができるよ。

```bash
#!/bin/bash

# 関数を作る
say_hello() {
    echo "--- メッセージ開始 ---"
    echo "こんにちは、$1 さん！"  # $1 は「1番目の引数」って意味
    echo "--------------------"
}

# 関数を使う
say_hello "Kokko"
say_hello "Tanaka"
```

### dotfiles での使われ方
`lib/utils.sh` にある `log_info` も関数だよ！

```bash
log_info() {
    # 色をつけて文字を表示するだけの関数
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} $1"
}
```

こうしておけば、`log_info "準備完了"` って書くだけで、青色でカッコよく表示できるってわけ✨

## 2. 他のファイルを読み込む (`source`)

スクリプトを分割した時に使うのが `source` コマンド。
「指定したファイルの中身を、ここにコピペしたのと同じ状態にする」ってイメージ。

```bash
# utils.sh（便利ツール集）を読み込む
source "./lib/utils.sh"

# これで utils.sh に書いてある関数が使えるようになる！
log_success "読み込み完了！"
```

## 3. 実践：`install.sh` を読んでみよう

実際の `~/dotfiles/install.sh` の一部を見てみよう。ここまで学んだことの組み合わせだよ！

```bash
#!/bin/bash
set -e  # エラーが起きたら即停止（安全装置）

# 1. 自分の場所を特定する
DOTFILES_DIR=$(cd "$(dirname "$0")"; pwd)

# 2. 便利ツールを読み込む
source "$DOTFILES_DIR/lib/utils.sh"

# 3. メニューを表示して入力を待つ（無限ループ）
while true; do
    show_menu  # 関数呼び出し
    read -p "Selection: " choice
    
    # 4. 入力によって処理を分ける
    case $choice in
        1)
            # 別のスクリプトを実行する
            bash "$DOTFILES_DIR/scripts/setup_zsh.sh"
            bash "$DOTFILES_DIR/scripts/setup_neovim.sh"
            break # ループを抜ける
            ;;
        q)
            exit 0
            ;;
    esac
done
```

どう？なんとなく「あ、ここで読み込んでるな」とか「ここで分岐してるな」って見えてきたかな？

## 最後に

シェルスクリプトは、**「普段の手作業をファイルに書いただけ」** からスタートできるよ。
まずは「バックアップを取るスクリプト」とか、簡単なものから書いて遊んでみてね！

改造するときに困ったら、またいつでも聞いてね！😊
