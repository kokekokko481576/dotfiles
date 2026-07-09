"""
Artifact用の単一ファイルUIプレビューを生成する。

実アプリのstatic/*.jsをそのまま連結し、fetchだけページ内のモックデータに
差し替える。実装とプレビューの乖離を防ぐため、手書きの複製は持たない。

使い方: python3 tools/build_preview.py 出力先.html
"""
import re
import sys
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"

BANNER = """
<div class="note">
  <b>ワニ博士 タスク管理 — UIプレビュー(デモデータ)</b><br>
  実機: <code>https://kokko-server-pavilion.tailed0412.ts.net:8443/</code>
  (Pixel 7aのTailscale経由)。このページは実アプリと同じコードをデモデータで
  動かしている。上のタブで「ぼうけん/リスト/マップ」を切替可能。
  敵をタップ→「完了」でとどめ(スロット)演出が見られる。
</div>
"""

NOTE_CSS = """
.note { max-width: 480px; margin: 14px auto 0; padding: 10px 14px;
  border: 1.5px dashed var(--line); border-radius: 12px;
  font-size: 12px; color: var(--sub); line-height: 1.7; }
.note b { color: var(--ink); }
.note code { font-size: 11px; background: var(--chip); padding: 1px 5px;
  border-radius: 4px; word-break: break-all; }
"""

FETCH_SHIM = """
// ---- fetchモック(プレビュー専用): 実APIの代わりにページ内データで応答する ----
const MOCK_TASKS = [
  {item_id: "d1", number: 10, title: "BLDC試運転", repo: "personal-tasks", labels: ["hw"], status: "In Progress", draft: false},
  {item_id: "d2", number: 15, title: "ハンダ付け", repo: "personal-tasks", labels: ["hw"], status: "In Progress", draft: false},
  {item_id: "d3", number: 4, title: "py-ship-sym触ってみる", repo: "personal-tasks", labels: [], status: "Todo", draft: false},
  {item_id: "d4", number: 14, title: "追加発注リスト", repo: "personal-tasks", labels: [], status: "Todo", draft: false},
  {item_id: "d5", number: 1, title: "コントローラー送信側ファームウェア", repo: "personal-tasks", labels: [], status: "waiting", draft: false},
  {item_id: "d6", number: 2, title: "無線基板ファームウェア", repo: "personal-tasks", labels: [], status: "waiting", draft: false},
  {item_id: "d7", number: 12, title: "PoE給電システム化", repo: "personal-tasks", labels: [], status: "wish list", draft: false},
  {item_id: "d8", number: null, title: "いつかやる: 3Dプリンタのファーム更新", repo: "", labels: [], status: "wish list", draft: true},
];
const MOCK_STATUSES = ["waiting", "Todo", "In Progress", "Review", "Done", "wish list"];
const MOCK_MOOD = {mood: 52, level: "happy", sleeping: false, streak: 2, today_done: 0, today_started: 0};
const EXCLUDED_P = new Set(["waiting", "wish list"]);
function lvl(m) { return m >= 75 ? "excellent" : m >= 45 ? "happy" : m >= 20 ? "normal" : "tired"; }
function progressOf() {
  const scoped = MOCK_TASKS.filter(t => !EXCLUDED_P.has((t.status||"").toLowerCase()));
  const done = scoped.filter(t => (t.status||"").toLowerCase() === "done").length;
  return {done, total: scoped.length, percent: scoped.length ? Math.round(done*100/scoped.length) : 0};
}
function stateNow() {
  MOCK_MOOD.level = lvl(MOCK_MOOD.mood);
  return {mock: true, error: null, mood: {...MOCK_MOOD}, progress: progressOf(),
          tasks: MOCK_TASKS.map(t => ({...t})), statuses: MOCK_STATUSES, now: new Date().toISOString()};
}
window.fetch = async (url, opts = {}) => {
  const respond = (obj, status = 200) =>
    new Response(JSON.stringify(obj), {status, headers: {"Content-Type": "application/json"}});
  url = String(url);
  let m;
  if ((m = url.match(/api\\/tasks\\/([^/]+)\\/status/))) {
    const id = decodeURIComponent(m[1]);
    const task = MOCK_TASKS.find(t => t.item_id === id);
    if (!task) return respond({detail: "not found"}, 400);
    const body = JSON.parse(opts.body);
    const old = (task.status||"").toLowerCase();
    task.status = body.status;
    const now = (body.status||"").toLowerCase();
    let event = null;
    if (now === "done" && old !== "done") { event = "done"; MOCK_MOOD.mood = Math.min(100, MOCK_MOOD.mood + 18); MOCK_MOOD.today_done++; }
    else if (old === "done" && now !== "done") { event = "undone"; MOCK_MOOD.mood = Math.max(0, MOCK_MOOD.mood - 10); }
    else if ((now === "in progress" || now === "review") && old !== "in progress" && old !== "review") {
      event = "started"; MOCK_MOOD.mood = Math.min(100, MOCK_MOOD.mood + 6); MOCK_MOOD.today_started++;
    }
    MOCK_MOOD.level = lvl(MOCK_MOOD.mood);
    return respond({ok: true, task: {...task}, event, mood: {...MOCK_MOOD}});
  }
  if (url.match(/api\\/tasks$/)) {
    const {title} = JSON.parse(opts.body);
    const task = {item_id: "new-" + Date.now(), number: null, title, repo: "", labels: [], status: "Todo", draft: true};
    MOCK_TASKS.push(task);
    return respond({ok: true, task});
  }
  if (url.includes("api/state")) return respond(stateNow());
  return new Response("", {status: 404});
};
"""


def strip_module(src: str) -> str:
    """import文とexportキーワードを除去する。"""
    src = re.sub(r"^import .*$", "", src, flags=re.M)
    src = re.sub(r"^export ", "", src, flags=re.M)
    return src


def wrap_iife(src: str, init_name: str) -> str:
    """モジュールをIIFEで包み、init関数だけをトップレベルに出す(名前衝突回避)。"""
    return f"const {init_name} = (() => {{\n{strip_module(src)}\nreturn {init_name};\n}})();\n"


def main(out_path: str):
    style = (STATIC / "style.css").read_text(encoding="utf-8")
    sprites = strip_module((STATIC / "sprites.js").read_text(encoding="utf-8"))
    classic = wrap_iife((STATIC / "classic.js").read_text(encoding="utf-8"), "initClassic")
    adventure = wrap_iife((STATIC / "adventure.js").read_text(encoding="utf-8"), "initAdventure")
    mapjs = wrap_iife((STATIC / "map.js").read_text(encoding="utf-8"), "initMap")
    app = strip_module((STATIC / "app.js").read_text(encoding="utf-8"))

    # index.htmlの<main>...とシート部分を流用
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    body = re.search(r"<main.*</div>\s*(?=<script)", index, re.S).group(0)

    html = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ワニ博士 UIプレビュー</title>
<style>
{style}
{NOTE_CSS}
</style>
{BANNER}
{body}
<script type="module">
{FETCH_SHIM}
{sprites}
{classic}
{adventure}
{mapjs}
{app}
</script>
"""
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"wrote {out_path} ({len(html)} chars)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "wani-preview.html")
