// ワニ博士 PWA 本体。/api/state を表示し、タスクの状態変更を /api/tasks/... にPOSTする。
import { PALETTE, SPRITES, SPRITE_W, SPRITE_H } from "./sprites.js";

const $ = (id) => document.getElementById(id);
const stage = $("stage");
const ctx = stage.getContext("2d");

let state = null;          // 最後に取得した /api/state
let frameIndex = 0;
let overrideSprite = null; // 完了直後の演出用(一時的にスプライトを差し替える)

const LEVEL_TEXT = {
  excellent: "エクセレント！",
  happy: "ごきげん",
  normal: "ふつう",
  tired: "ぐったり…",
};
const SAY = {
  excellent: ["ワニ、感動しました！", "この調子です、主人！", "研究がはかどりますね！"],
  happy: ["いい調子ですね", "その調子でいきましょう", "ふふ、順調です"],
  normal: ["今日は何をしますか？", "ひとつ着手してみませんか", "マイペースでいきましょう"],
  tired: ["進捗をください…", "1件だけでも…", "おなかがすきました…"],
  sleeping: ["すやすや…", "Zzz…"],
};

function currentSpriteName() {
  if (overrideSprite) return overrideSprite;
  if (!state) return "normal";
  if (state.mood.sleeping) return "sleeping";
  return state.mood.level;
}

function drawFrame() {
  const frames = SPRITES[currentSpriteName()] || SPRITES.normal;
  const rows = frames[frameIndex % frames.length];
  ctx.clearRect(0, 0, SPRITE_W, SPRITE_H);
  for (let y = 0; y < rows.length; y++) {
    const row = rows[y];
    for (let x = 0; x < row.length; x++) {
      const color = PALETTE[row[x]];
      if (!color) continue;
      ctx.fillStyle = color;
      ctx.fillRect(x, y, 1, 1);
    }
  }
}
setInterval(() => { frameIndex++; drawFrame(); }, 600);

function pickSay() {
  const key = currentSpriteName() === "sleeping" ? "sleeping" : state?.mood.level;
  const list = SAY[key] || SAY.normal;
  return list[Math.floor(Math.random() * list.length)];
}

function render() {
  if (!state) return;
  $("mock-badge").hidden = !state.mock;
  $("error-banner").hidden = !state.error;
  if (state.error) $("error-banner").textContent = `タスク取得エラー: ${state.error}`;

  const m = state.mood;
  $("mood-label").textContent = m.sleeping ? "おやすみ中" : (LEVEL_TEXT[m.level] || m.level);
  $("mood-bar").style.width = `${m.mood}%`;
  $("streak").hidden = m.streak <= 0;
  $("streak").querySelector("b").textContent = m.streak;
  $("wani-say").textContent = pickSay();

  const p = state.progress;
  $("progress-text").textContent = `${p.done} / ${p.total} 完了`;
  $("progress-bar").style.width = `${p.percent}%`;

  renderTasks();
  $("updated-at").textContent =
    `更新: ${new Date(state.now).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" })}`;
  drawFrame();
}

const STATUS_JA = {
  "waiting": "待ち", "todo": "未着手", "in progress": "進行中",
  "review": "レビュー", "done": "完了", "wish list": "後回し",
};
const statusJa = (s) => STATUS_JA[(s || "").toLowerCase()] || s;
const statusOf = (t) => (t.status || "").toLowerCase();

function taskCard(t) {
  const card = document.createElement("div");
  card.className = "task" + (statusOf(t) === "done" ? " done" : "");

  const title = document.createElement("div");
  title.className = "task-title";
  title.textContent = (t.number ? `#${t.number} ` : "") + t.title;
  card.appendChild(title);

  const meta = document.createElement("div");
  meta.className = "task-meta";
  meta.textContent =
    [t.draft ? "メモ(Draft)" : t.repo, ...(t.labels || [])].filter(Boolean).join(" · ");
  card.appendChild(meta);

  const actions = document.createElement("div");
  actions.className = "task-actions";
  for (const s of state.statuses) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "status-btn" + (s === t.status ? " active" : "");
    btn.textContent = statusJa(s);
    btn.onclick = () => updateStatus(t, s, btn);
    actions.appendChild(btn);
  }
  card.appendChild(actions);
  return card;
}

function renderTasks() {
  const list = $("task-list");
  list.replaceChildren();

  const active = [], waiting = [], wish = [];
  for (const t of state.tasks) {
    const s = statusOf(t);
    if (s === "waiting") waiting.push(t);
    else if (s === "wish list") wish.push(t);
    else active.push(t);
  }

  if (!active.length) {
    const div = document.createElement("div");
    div.className = "tasks-empty";
    div.textContent = state.error ? "" : "アクティブなタスクがありません。GitHub Projectに追加してください。";
    list.appendChild(div);
  } else {
    // Done を下に、それ以外は番号順(Draftは末尾)
    active.sort((a, b) =>
      (statusOf(a) === "done" ? 1 : 0) - (statusOf(b) === "done" ? 1 : 0)
      || (a.number ?? 1e9) - (b.number ?? 1e9));
    for (const t of active) list.appendChild(taskCard(t));
  }

  for (const [tasks, boxId, listId, countId] of [
    [waiting, "waiting-box", "waiting-list", "waiting-count"],
    [wish, "wish-box", "wish-list", "wish-count"],
  ]) {
    $(boxId).hidden = !tasks.length;
    $(countId).textContent = tasks.length ? `${tasks.length}件` : "";
    const el = $(listId);
    el.replaceChildren();
    for (const t of tasks) el.appendChild(taskCard(t));
  }
}

async function updateStatus(task, status, btn) {
  if (task.status === status) return;
  btn.disabled = true;
  try {
    const res = await fetch(`api/tasks/${encodeURIComponent(task.item_id)}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const result = await res.json();
    if (result.event === "done") celebrate();
    await refresh();
  } catch (e) {
    $("error-banner").hidden = false;
    $("error-banner").textContent = `更新に失敗しました: ${e.message}`;
    btn.disabled = false;
  }
}

function celebrate() {
  overrideSprite = "excellent";
  stage.classList.add("pop");
  setTimeout(() => stage.classList.remove("pop"), 600);
  setTimeout(() => { overrideSprite = null; drawFrame(); }, 4000);
}

async function refresh() {
  try {
    const res = await fetch("api/state");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state = await res.json();
    render();
  } catch (e) {
    $("error-banner").hidden = false;
    $("error-banner").textContent = `サーバーに接続できません: ${e.message}`;
  }
}

$("refresh").onclick = refresh;
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refresh();
});
setInterval(refresh, 60_000);
refresh();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
