// ワニ博士 PWA コア: 状態取得・API・モード切替・共通UI(タスクシート/追加)。
// 各モードの描画は classic.js / adventure.js / map.js に分離。
import { initClassic } from "./classic.js";
import { initAdventure } from "./adventure.js";
import { initMap } from "./map.js";

const $ = (id) => document.getElementById(id);

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

async function refresh() {
  try {
    const res = await fetch("api/state");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state = await res.json();
    renderShared();
    modes[currentMode]?.update(state);
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
    `更新: ${new Date(state.now).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" })}`;
}

// ---- タスク操作シート(ぼうけん/マップから使う共通UI) ----
function activeQueue() {
  // 冒険モードの敵の隊列と同じ並び(=Projectの手動順、Done/待ち/後回しを除く)
  return state.tasks.filter(
    (t) => !EXCLUDED.has(statusOf(t)) && statusOf(t) !== "done");
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

  // 並び替え(たたかう順 = GitHub Projectの並び順にも反映される)
  const order = $("sheet-order");
  order.replaceChildren();
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

// ---- 予定(カレンダー)シート: ぼうけんモードの割り込み敵用 ----
function showEventSheet(ev, onDone) {
  $("sheet-title").textContent = `📅 ${ev.title}`;
  const fmt = (iso) => new Date(iso).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" });
  $("sheet-meta").textContent =
    `Googleカレンダーの予定 ${fmt(ev.start)}${ev.end ? "〜" + fmt(ev.end) : ""}`;
  $("sheet-order").replaceChildren();
  const actions = $("sheet-actions");
  actions.replaceChildren();
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "status-btn active";
  btn.textContent = "すんだ！";
  btn.onclick = () => { closeSheet(); onDone?.(); };
  actions.appendChild(btn);
  $("sheet-backdrop").hidden = false;
}
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
  showEventSheet,
  showError,
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
setInterval(refresh, 60_000);
switchMode(currentMode in modes ? currentMode : "adventure");
refresh();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
