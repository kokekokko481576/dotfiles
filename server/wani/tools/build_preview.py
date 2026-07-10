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
  {item_id: "d1", number: 10, title: "BLDC試運転", repo: "azimuth_lowlayer", labels: ["hw"], status: "In Progress", draft: false},
  {item_id: "d2", number: 15, title: "基板の配線見直し", repo: "azimuth_kicad", labels: ["hw"], status: "In Progress", draft: false},
  {item_id: "d3", number: 4, title: "ナビゲーションノード作成", repo: "azimuth_ros", labels: [], status: "Todo", draft: false},
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
function mockEvents() {
  // 「いま割り込み中の予定」1件 + 後の予定1件をデモ表示する
  const now = new Date();
  const mk = (offsetMin, durMin, title) => {
    const s = new Date(now.getTime() + offsetMin * 60000);
    const e = new Date(s.getTime() + durMin * 60000);
    return {title, start: s.toISOString(), end: e.toISOString(), all_day: false};
  };
  return [mk(-10, 60, "ゼミ"), mk(120, 60, "実験装置の予約")];
}
const MOCK_TODAY = {date: new Date().toISOString().slice(0,10), item_ids: [], approved: false};
function stateNow() {
  MOCK_MOOD.level = lvl(MOCK_MOOD.mood);
  return {mock: true, error: null, mood: {...MOCK_MOOD}, progress: progressOf(),
          tasks: MOCK_TASKS.map(t => ({...t})), statuses: MOCK_STATUSES,
          events: mockEvents(), today: {...MOCK_TODAY, item_ids: [...MOCK_TODAY.item_ids]},
          now: new Date().toISOString()};
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
  if ((m = url.match(/api\\/tasks\\/([^/]+)\\/due/))) {
    const id = decodeURIComponent(m[1]);
    const task = MOCK_TASKS.find(t => t.item_id === id);
    if (!task) return respond({detail: "not found"}, 400);
    task.due = JSON.parse(opts.body).due;
    return respond({ok: true, task: {...task}});
  }
  if ((m = url.match(/api\\/tasks\\/([^/]+)\\/move/))) {
    const id = decodeURIComponent(m[1]);
    const {after_item_id} = JSON.parse(opts.body);
    const i = MOCK_TASKS.findIndex(t => t.item_id === id);
    if (i === -1) return respond({detail: "not found"}, 400);
    const [moving] = MOCK_TASKS.splice(i, 1);
    if (after_item_id == null) MOCK_TASKS.unshift(moving);
    else MOCK_TASKS.splice(MOCK_TASKS.findIndex(t => t.item_id === after_item_id) + 1, 0, moving);
    return respond({ok: true});
  }
  if (url.match(/api\\/today\\/recommend$/)) {
    const picks = MOCK_TASKS.filter(t => !EXCLUDED_P.has((t.status||"").toLowerCase()))
      .slice(0, 3).map((t, i) => ({item_id: t.item_id,
        reason: ["予定の合間にちょうどよい", "着手済みなので今日で倒せる", "軽いので勢いがつく"][i]}));
    return respond({picks, comment: "午後の予定が多めなので、午前に重いのを片付けましょう！"});
  }
  if (url.match(/api\\/today$/)) {
    const {item_ids} = JSON.parse(opts.body);
    MOCK_TODAY.item_ids = item_ids;
    MOCK_TODAY.approved = true;
    return respond({ok: true, today: {...MOCK_TODAY}});
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
