#!/bin/bash
#
# 音楽フォルダを監視して、新しく置かれた .mp3 の「アルバム名」に
# 置かれたフォルダ名を自動でセットする。
# （例: /mnt/data/music/zelda/xxx.mp3 → アルバム名 = "zelda"）
#
# Navidrome がアルバム単位できれいに並ぶようにするための補助。
# systemd サービス autotagger.service から常駐実行される。

set -u

# 監視する音楽フォルダ（Navidrome の音源置き場と同じ）
MUSIC_DIR="/mnt/data/music"

echo "監視スタート！👀: $MUSIC_DIR"

# -m: ずっと監視し続ける
# -r: サブフォルダも全部監視
# -e close_write: ファイルの書き込みが完了して閉じた瞬間を検知（超重要！）
inotifywait -m -r -e close_write --format '%w%f' "$MUSIC_DIR" | while read -r FILEPATH; do
    # 拡張子が .mp3 の時だけ処理する
    if [[ "$FILEPATH" == *.mp3 ]]; then
        # ファイルが置いてあるフォルダのパスを取得
        DIR_PATH=$(dirname "$FILEPATH")
        # フォルダ名だけを抽出
        FOLDER_NAME=$(basename "$DIR_PATH")

        # music 直下（サブフォルダ無し）に置かれた場合はスキップ
        if [[ "$DIR_PATH" == "$MUSIC_DIR" ]]; then
            continue
        fi

        # id3v2 でアルバム名にフォルダ名を設定
        id3v2 -A "$FOLDER_NAME" "$FILEPATH"

        echo "タグ付け完了✨: [$FOLDER_NAME] -> $FILEPATH"
    fi
done
