# NeoVimの使い方 - 🛠️上級編「設定をいじる」

ここからは上級編！君だけの最強NeoVim環境を作るための、カスタマイズ方法を教えちゃうよ！
ちょっと難しいけど、ここをマスターすれば君もNeoVimマスターの一員だ！一緒にやっていこ！

## 📂 1. 設定ファイルの地図を読もう

このNeoVimの全設定は、`~/.config/nvim` っていうフォルダに全部入ってるんだ。
このフォルダをdotfilesとかで管理すれば、どこでも同じ環境を再現できるってワケ！

まずは、このフォルダの地図を頭に入れよう！

```
~/.config/nvim
├── init.lua                -- 全ての設定の入り口！まずNeovimはこれを読む。
└── lua/
    └── user/                 -- 君のカスタム設定は、全部ここに入ってるよ！
        ├── packer.lua        -- プラグインを管理するファイル
        ├── settings.lua      -- エディタの基本的な設定ファイル
        └── keymaps.lua       -- キーマップ（ショートカット）の設定ファイル
```

設定は全部**Lua**っていう言語で書かれてるよ。

- **`packer.lua`**: 新しい機能（プラグイン）を追加したり、いらなくなった機能を消したりする場所。
- **`keymaps.lua`**: 「このキーを押したら、この機能が動く」っていう対応（キーマップ）を全部書く場所。安全にキーマップを追加できる仕組みになってるんだ（理由は後でね！）。

## 📦 2. プラグインを改造する (`packer.nvim`)

プラグインの管理は `~/.config/nvim/lua/user/packer.lua` ファイルでやるよ！

### プラグインを追加したいとき

1.  `packer.lua` を開いて、`return require('packer').startup(function(use)` って書いてあるブロックを探す。
2.  その中に、`use 'GitHubリポジトリ名'` の形で、新しいプラグインを書き足す。
3.  もしプラグインに初期設定が必要なら、`config`ブロックも追加するよ。
    ```lua
    use {
      'some/new-plugin', -- 例：新しいプラグイン
      config = function() 
        require('new-plugin').setup({ ... })
      end
    }
    ```
4.  ファイルを保存して、NeoVimを再起動するか、ノーマルモードで`:PackerSync` ってコマンドを打つと、新しいプラグインがインストールされるよ！

### プラグインを削除したいとき

1.  `packer.lua` を開いて、いらないプラグインの `use '...'` のブロックを丸ごと消すか、行の先頭に`--`をつけてコメントにする。
2.  NeoVimを開いて、`:PackerSync` コマンドを実行！これだけでお掃除完了！

## 🤖 3. LSP（言語サーバー）を育てる

LSPは、賢いコード補完とかエラーチェックをしてくれる秘書みたいなやつ。新しい言語のサポートを追加して、もっと賢く育ててみよう！

### お手軽コース：サポート言語を増やす

ただ新しい言語（例えばGoとか）のサポートを追加したいだけなら、超かんたん！

1.  `packer.lua` を開いて、`mason-lspconfig` の設定を探す。
2.  `ensure_installed` のリストに、追加したいLSPの名前（`:Mason`ってコマンドを打つと名前の一覧が見れるよ）を追加するだけ！
    ```lua
    require('mason-lspconfig').setup({
        ensure_installed = { 'clangd', 'pyright', 'texlab', 'marksman', 'gopls' }, -- 例えば gopls を追加！
    })
    ```
3.  ファイルを保存してNeoVimを再起動すれば、自動でインストールが始まるよ。

### こだわりコース：LSPの動きをカスタマイズする

`setup_log.md`に書いてあったLaTeX環境みたいに、LSPのデフォルト設定を上書きしたいときもあるよね。
そのときは、`lsp-zero`の`configure`機能を使うのが正解！

```lua
-- packer.lua の lsp-zero の config ブロックの中で…

-- lsp.setup() を呼び出す前に、設定したいサーバーの configure を書くのがポイント！
lsp.configure('texlab', { -- 例えば texlab の設定を上書き
    settings = {
        texlab = {
            build = { ... } -- ここに上書きしたい設定を書く
        }
    }
})

-- この後に lsp.setup() を呼び出す
lsp.setup()
```

## 🗺️ 4. キーマップを追加・変更する

キーマップは `~/.config/nvim/lua/user/keymaps.lua` ファイルで全部管理するのが、この環境では一番安全だよ！

**なんで安全なの？**
実はこのファイル、NeoVimの起動と**すべてのプラグインの読み込みが終わった後**に実行されるように設定されてるんだ。
だから、プラグインが提供する機能を呼び出すキーマップを書いても、「そんな機能、まだないよ！」ってエラーになる心配がないってこと！

```lua
-- keymaps.lua の基本構造はこんな感じ

local function set_keymaps()
  -- ここに、君だけのキーマップをどんどん追加していこう！
  -- vim.keymap.set('モード', '押すキー', '実行するコマンド', { オプション })
  vim.keymap.set('n', '<leader>t', ':ToggleTerm<CR>', { noremap = true, silent = true })
end

-- NeoVimの起動が全部終わったら、上の set_keymaps() を実行してね、っていうおまじない
vim.api.nvim_create_autocmd("VimEnter", {
  pattern = "*",
  callback = set_keymaps,
})
```

## ✨ 5. NeoVim本体をピカピカにする（アップデート）

NeoVim本体も、たまにアップデートしてピカピカにしてあげよう！
ターミナルで、いつもやってるみたいに以下のコマンドを実行すればOK！

```bash
sudo apt update
sudo apt upgrade
```

## ⚠️ 最後に：改造する前のお約束

設定をいじるのは、すごく楽しい！でも、間違えるとNeoVimが起動しなくなっちゃうこともある…！

だから、**`~/.config/nvim` フォルダを、どこかにコピーしてバックアップを取っておくこと！**

これ、絶対のお約束だよ！バックアップさえあれば、何かあってもすぐに元に戻せるから、安心して改造にチャレンジできる！

それじゃ、Happy Hacking！君だけのNeoVimを育てていってね！