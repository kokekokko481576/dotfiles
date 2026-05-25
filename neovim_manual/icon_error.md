
# Neovimでアイコンが文字化け（コードポイント表示）する問題の解決備忘録

Neovimの `mini.icons` 等のプラグインで、アイコンが正常に表示されず `E5FF` などの16進数の四角い数字（コードポイント）で表示されてしまう問題を解決した際の手順。

## 原因
Neovim（Lua）側のプラグインは正常に動作していたが、ターミナル側で適用されているフォントが **Nerd Fonts（アイコンフォントが埋め込まれたフォント）** になっていなかったため、アイコンの文字コードをレンダリングできていなかった。

---

## 解決手順

### 1. Nerd Fonts のインストール
システムに `JetBrainsMono Nerd Font` をインストールする。
ローカル（ユーザー環境）ではなく、システム全体から参照できるように `/usr/share/fonts` 配下に配置する。

```bash
# 1. システム全体のフォント置き場にフォルダを作成
sudo mkdir -p /usr/share/fonts/truetype/JetBrainsMono

# 2. ダウンロード済みのNerd Font（.ttf）をそこにすべてコピー
sudo cp ~/.local/share/fonts/JetBrainsMono/*.ttf /usr/share/fonts/truetype/JetBrainsMono/

# 3. フォントキャッシュを強制更新
sudo fc-cache -f -v

```

**確認コマンド:**

```bash
fc-list | grep -i "nerd"

```

出力結果に `/usr/share/fonts/...` のパスで JetBrainsMono が表示されていればOK。

### 2. ターミナル（Ubuntu標準端末 / GNOME Terminal）の設定変更

Ubuntu標準の端末は、等幅フォント判定が厳格なためGUIのフォント一覧に表示されない場合がある。その場合はシステム共通の配置に移動した上で、以下の手順でGUIから確実に切り替える。

1. ターミナルを完全に再起動する。
2. ターミナル内を右クリック ➜ **「設定 (Preferences)」** を開く。
3. 左メニューから現在使用しているプロファイル（「名前なし」や「Default」など）を選択。
4. **「テキスト (Text)」タブ** を開く。
5. **「独自のフォントを指定する (Custom font)」** にチェックを入れる。
6. フォント選択ボタンを押し、リストから **`JetBrainsMono Nerd Font`**（または `JetBrainsMono NF`）の `Regular` を選択して適用する。

---

## 備考（Neovim側のデバッグ方法）

もし今後設定がおかしくなった場合は、Neovim内で以下のLuaコマンドを叩くことで、プラグインが正常にアイコンを返せているかを確認できる。

```vim
:lua print(require("mini.icons").get("file", "test.lua"))

```

* **エラーが出ずに化けた文字や四角（数字）が出る場合:** プラグインは正常。ターミナルのフォント設定の問題。
* **`module 'mini.icons' not found` が出る場合:** プラグイン自体が読み込めていない（`init.lua` や `plugins.lua` の配置・パス指定の問題）。


