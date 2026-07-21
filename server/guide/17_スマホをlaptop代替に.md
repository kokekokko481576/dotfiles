# スマホを laptop 代替にする（DeX + リモート + mosh）

スマホ（Galaxy等のデスクトップモード対応機）＋モバイルモニターで、外出先の作業を
laptopなしで回すための構成メモ。ネットワークは既存の **Tailscale**（guide/01）に相乗り
するので、ポート開放は不要（自宅サーバーへはtailnet内で直接届く）。

## 端末選び（メモ）

- **必須:** モニター接続で「デスクトップモード（Samsung DeX等）」になる機種。
- **狙い目:** 型落ちのGalaxy S23が完成度・使い勝手で本命。
- **RAM:** PCライクに複数アプリなら **12GB以上**（8GBは強制終了されやすい）。

## 用途別の相性

- **◎ スマホ単体（DeX）で完結:** ブラウザ / 書類 / Notion / Obsidian（guide/16のLiveSync同期）/
  Canva / **SSH接続でのコーディング**（数値解析のコード書き等はこれで完結）。
- **✕ 単体では厳しい→リモートデスクトップでカバー:** KiCAD / CubeIDE（Androidアプリ無し）/
  Onshape（ブラウザだがメモリ食い）。これらは自宅サーバー or PCの画面を飛ばして操作する。

---

## 1. SSH は mosh で（切れても復帰する）

DeXのターミナル（Termius / JuiceSSH / Termux等）から、mosh で自宅サーバーへ。
mosh は接続を続けたまま **Wi-Fi⇄モバイル回線の切替や一時切断から自動復帰**する（SSHは切れる）。

サーバー側（一度だけ）:
```bash
sudo apt update && sudo apt install -y mosh    # install.sh の deps にも追加済み
```
接続（tailnet内なのでMagicDNS名でOK。UDPはtailscaleが運ぶのでポート開放不要）:
```bash
mosh kokko@kokko-server-pavilion.tailed0412.ts.net
```
- サーバー内では `tmux`（guide同梱の設定）でセッションを永続化。切断→再接続でも作業が残る。
- 「SSH不安定だからローカルでコンパイル…」の沼を避けたいなら、重いビルドは
  `tmux` 内で走らせて放置し、mosh再接続で結果を拾うのが安定。

## 2. GUIアプリ（KiCAD等）はリモートデスクトップ

自宅サーバー/PCの画面をDeXに飛ばして全画面表示すれば、実質そのPCを直接触る感覚。
Tailscale上で使えて設定が軽い順:

| 方法 | 特徴 | 推奨度 |
|---|---|---|
| **RustDesk**（セルフホスト可・OSS） | 自前リレーをtailnetに置ける。プライバシー面で自己完結 | ◎ 本命 |
| **Sunshine + Moonlight** | GPUエンコードで低遅延。KiCAD/CAD操作が軽快 | ○ 重い操作向き |
| Chrome リモートデスクトップ | 設定が一番簡単。Googleアカウント経由 | ○ 手軽 |
| AnyDesk | 手軽だが商用クラウド経由 | △ |

いずれもDeXでウィンドウを全画面にすれば「自宅PCをそのまま操作」できる。KiCAD・CubeIDE・
Onshapeはこの方式に寄せる。

## 3. 使い分けの指針（ベストプラクティス）

- **コード書き / サーバー運用 / このdotfiles操作** → mosh + tmux（軽い・完結する）。
- **回路CAD・IDE・重いブラウザCAD** → リモートデスクトップで母艦に委譲。
- **メモ / ドキュメント** → Obsidian（guide/16のLiveSyncでスマホにもVaultが同期済み）。

> ネットワークはすべて Tailscale 内で完結させる（guide/08 のセキュリティ方針どおり、
> サービスをtailnet外に晒さない）。リモートデスクトップのリレーも可能な限り自ホストに置く。
