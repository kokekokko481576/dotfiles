// ワニ博士 PWA コア: 状態取得・API・モード切替・共通UI(タスクシート/追加)。
// 各モードの描画は classic.js / adventure.js / map.js に分離。
import { initClassic } from "./classic.js?v=12";
import { initAdventure } from "./adventure.js?v=12";
import { initMap } from "./map.js?v=12";

const $ = (id) => document.getElementById(id);

// フッターに出すバージョン。デプロイが端末に届いているかの確認用(更新時に上げる)
export const APP_VERSION = "v12";

export const STATUS_JA = {
  "waiting": "待ち", "todo": "未着手", "in progress": "進行中",
  "review": "レビュー", "done": "完了", "wish list": "後回し",
};
export const statusJa = (s) => STATUS_JA[(s || "").toLowerCase()] || s;
export const statusOf = (t) => (t.status || "").toLowerCase();
export const EXCLUDED = new Set(["waiting", "wish list"]);

let state = null;
// モードは ?mode=classic|adventure|map で直接指定もできる(指定は保存される)
const urlMode = new URLSearchParams(location.search).get("mode");
let currentMode = urlMode || localStorage.getItem("wani_ui") || "adventure";
const modes = {};

// ---- API ----
async function apiUpdateStatus(task, status) {
  const res = await fetch(`api/tasks/${encodeURIComponent(task.item_id)}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || res.statusText);
  return body; // {ok, task, event, mood}
}

async function apiMove(task, afterItemId) {
  const res = await fetch(`api/tasks/${encodeURIComponent(task.item_id)}/move`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ after_item_id: afterItemId }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || res.statusText);
  return body;
}

async function apiCreateTask(title) {
  const res = await fetch("api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || res.statusText);
  return body.task;
}

let editing = false; // インライン編集中は自動refreshでDOMを壊さない

async function refresh() {
  if (editing) return;
  try {
    const res = await fetch("api/state");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state = await res.json();
    renderShared();
    modes[currentMode]?.update(state);
    maybeAutoPlan();
  } catch (e) {
    showError(`サーバーに接続できません: ${e.message}`);
  }
}

function showError(msg) {
  $("error-banner").hidden = false;
  $("error-banner").textContent = msg;
}

function renderShared() {
  $("mock-badge").hidden = !state.mock;
  $("error-banner").hidden = !state.error;
  if (state.error) $("error-banner").textContent = `タスク取得エラー: ${state.error}`;
  $("streak").hidden = state.mood.streak <= 0;
  $("streak").querySelector("b").textContent = state.mood.streak;
  $("updated-at").textContent =
    `更新: ${new Date(state.now).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" })} · ${APP_VERSION}`;
}

// ---- 今日やるリスト ----
const todayApproved = () => !!state?.today?.approved;
const isToday = (t) => todayApproved() && state.today.item_ids.includes(t.item_id);

function allActive() {
  return state.tasks.filter(
    (t) => !EXCLUDED.has(statusOf(t)) && statusOf(t) !== "done");
}

// ---- タスク操作シート(ぼうけん/マップから使う共通UI) ----
function activeQueue() {
  // 冒険モードの敵の隊列と同じ並び(=Projectの手動順、Done/待ち/後回しを除く)。
  // 作戦会議で今日のリストを承認済みなら、今日のタスクだけに絞る
  const active = allActive();
  return todayApproved() ? active.filter(isToday) : active;
}

async function setTodayList(itemIds) {
  const res = await fetch("api/today", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_ids: itemIds }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || res.statusText);
  return body;
}

// ---- 朝の作戦会議 ----
let planShown = false;

async function openPlanning() {
  planShown = true;
  const backdrop = $("plan-backdrop");
  const list = $("plan-list");
  const comment = $("plan-comment");
  backdrop.hidden = false;
  list.replaceChildren();

  const active = allActive();
  const checked = new Set(todayApproved()
    ? state.today.item_ids.filter((id) => active.some((t) => t.item_id === id))
    : []);
  const reasons = new Map();

  const renderList = () => {
    list.replaceChildren();
    for (const t of active) {
      const label = document.createElement("label");
      label.className = "plan-item" + (checked.has(t.item_id) ? " checked" : "");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = checked.has(t.item_id);
      cb.onchange = () => {
        cb.checked ? checked.add(t.item_id) : checked.delete(t.item_id);
        label.classList.toggle("checked", cb.checked);
      };
      const body = document.createElement("div");
      const title = document.createElement("div");
      title.className = "plan-item-title";
      title.textContent = (t.number ? `#${t.number} ` : "") + t.title;
      body.appendChild(title);
      if (reasons.has(t.item_id)) {
        const r = document.createElement("div");
        r.className = "plan-item-reason";
        r.textContent = `🐊 ${reasons.get(t.item_id)}`;
        body.appendChild(r);
      }
      const meta = document.createElement("div");
      meta.className = "plan-item-meta";
      meta.textContent = [statusJa(t.status), t.draft ? "メモ" : t.repo].filter(Boolean).join(" · ");
      body.appendChild(meta);
      label.append(cb, body);
      list.appendChild(label);
    }
  };
  renderList();

  if (todayApproved()) {
    comment.textContent = "今日のリストを編集できます。";
  } else {
    comment.textContent = "🐊 ワニ博士が考え中…";
    try {
      const res = await fetch("api/today/recommend", { method: "POST" });
      const rec = await res.json();
      if (!res.ok) throw new Error(rec.detail || res.statusText);
      for (const p of rec.picks) {
        checked.add(p.item_id);
        reasons.set(p.item_id, p.reason);
      }
      comment.textContent = `🐊 ${rec.comment || "このあたりはどうでしょう。"}`;
      renderList();
    } catch (e) {
      comment.textContent = `提案の取得に失敗しました(自分で選んでください): ${e.message}`;
    }
  }

  $("plan-start").onclick = async () => {
    $("plan-start").disabled = true;
    try {
      await setTodayList([...checked]);
      backdrop.hidden = true;
      await refresh();
    } catch (e) {
      showError(`保存に失敗しました: ${e.message}`);
    } finally {
      $("plan-start").disabled = false;
    }
  };
}
$("plan-later").onclick = () => { $("plan-backdrop").hidden = true; };
$("plan-backdrop").onclick = (e) => { if (e.target === $("plan-backdrop")) $("plan-backdrop").hidden = true; };

function maybeAutoPlan() {
  if (planShown || todayApproved()) return;
  if (state.mood.sleeping || !allActive().length) return;
  openPlanning();
}

function showTaskSheet(task) {
  $("sheet-title").textContent = (task.number ? `#${task.number} ` : "") + task.title;
  $("sheet-meta").textContent =
    [task.draft ? "メモ(Draft)" : task.repo, ...(task.labels || [])].filter(Boolean).join(" · ");
  const actions = $("sheet-actions");
  actions.replaceChildren();
  for (const s of state.statuses) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "status-btn" + (s === task.status ? " active" : "");
    btn.textContent = statusJa(s);
    btn.onclick = async () => {
      if (s === task.status) return;
      btn.disabled = true;
      try {
        const result = await apiUpdateStatus(task, s);
        closeSheet();
        modes[currentMode]?.onTaskEvent?.(result);
        await refresh();
      } catch (e) {
        showError(`更新に失敗しました: ${e.message}`);
        btn.disabled = false;
      }
    };
    actions.appendChild(btn);
  }

  // 今日やる/やらないトグル(作戦会議承認後のみ)
  const orderEl = $("sheet-order");
  orderEl.replaceChildren();
  if (todayApproved() && !EXCLUDED.has(statusOf(task)) && statusOf(task) !== "done") {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "status-btn" + (isToday(task) ? " active" : "");
    btn.textContent = isToday(task) ? "⭐ きょうやる(解除する)" : "⭐ きょうやるに入れる";
    btn.onclick = async () => {
      btn.disabled = true;
      try {
        const ids = new Set(state.today.item_ids);
        isToday(task) ? ids.delete(task.item_id) : ids.add(task.item_id);
        await setTodayList([...ids]);
        closeSheet();
        await refresh();
      } catch (e) {
        showError(`更新に失敗しました: ${e.message}`);
      }
    };
    orderEl.appendChild(btn);
  }

  // 並び替え(たたかう順 = GitHub Projectの並び順にも反映される)
  const order = orderEl;
  const queue = activeQueue();
  const idx = queue.findIndex((t) => t.item_id === task.item_id);
  if (idx !== -1 && queue.length > 1) {
    const label = document.createElement("span");
    label.className = "sheet-order-label";
    label.textContent = `たたかう順: ${idx + 1}/${queue.length}`;
    order.appendChild(label);
    const moves = [
      ["⏫ せんとう", idx > 0 ? null : undefined, idx > 0],
      ["◀ まえへ", idx > 1 ? queue[idx - 2].item_id : null, idx > 0],
      ["▶ うしろへ", idx < queue.length - 1 ? queue[idx + 1].item_id : null, idx < queue.length - 1],
    ];
    for (const [text, afterId, enabled] of moves) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "status-btn";
      btn.textContent = text;
      btn.disabled = !enabled;
      btn.onclick = async () => {
        btn.disabled = true;
        try {
          await apiMove(task, afterId ?? null);
          closeSheet();
          await refresh();
        } catch (e) {
          showError(`並び替えに失敗しました: ${e.message}`);
        }
      };
      order.appendChild(btn);
    }
  }
  $("sheet-backdrop").hidden = false;
}

// (予定はタップで情報表示のみ。終了時刻になれば自動で飛び去るため操作は不要)
function closeSheet() { $("sheet-backdrop").hidden = true; }
$("sheet-close").onclick = closeSheet;
$("sheet-backdrop").onclick = (e) => { if (e.target === $("sheet-backdrop")) closeSheet(); };

// ---- タスク追加 ----
$("add-task").onclick = () => {
  $("add-backdrop").hidden = false;
  $("add-input").value = "";
  $("add-input").focus();
};
$("add-cancel").onclick = () => { $("add-backdrop").hidden = true; };
$("add-backdrop").onclick = (e) => { if (e.target === $("add-backdrop")) $("add-backdrop").hidden = true; };
async function submitAdd() {
  const title = $("add-input").value.trim();
  if (!title) return;
  $("add-submit").disabled = true;
  try {
    await apiCreateTask(title);
    $("add-backdrop").hidden = true;
    await refresh();
    modes[currentMode]?.onTaskAdded?.();
  } catch (e) {
    showError(`追加に失敗しました: ${e.message}`);
  } finally {
    $("add-submit").disabled = false;
  }
}
$("add-submit").onclick = submitAdd;
$("add-input").addEventListener("keydown", (e) => { if (e.key === "Enter") submitAdd(); });

// ---- モード切替 ----
const core = {
  getState: () => state,
  updateStatus: apiUpdateStatus,
  refresh,
  showTaskSheet,
  moveTask: apiMove,
  setEditing: (v) => { editing = v; },
  showError,
  openPlanning,
  isToday, todayApproved, allActive,
  statusJa, statusOf,
  EXCLUDED,
};

function switchMode(mode) {
  if (!modes[mode]) return;
  modes[currentMode]?.hide();
  currentMode = mode;
  localStorage.setItem("wani_ui", mode);
  for (const btn of document.querySelectorAll(".mode-tab")) {
    btn.classList.toggle("active", btn.dataset.mode === mode);
    btn.setAttribute("aria-selected", btn.dataset.mode === mode);
  }
  for (const [name, el] of [["classic", "view-classic"], ["adventure", "view-adventure"], ["map", "view-map"]]) {
    $(el).hidden = name !== mode;
  }
  modes[mode].show();
  if (state) modes[mode].update(state);
}

modes.classic = initClassic(core);
modes.adventure = initAdventure(core);
modes.map = initMap(core);

for (const btn of document.querySelectorAll(".mode-tab")) {
  btn.onclick = () => switchMode(btn.dataset.mode);
}

// ---- 起動 ----
$("refresh").onclick = refresh;
document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
window.addEventListener("resize", () => modes[currentMode]?.onResize?.());
window.addEventListener("orientationchange", () => setTimeout(() => modes[currentMode]?.onResize?.(), 200));
setInterval(refresh, 60_000);
switchMode(currentMode in modes ? currentMode : "adventure");
refresh();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
