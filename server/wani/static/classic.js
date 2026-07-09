// クラシック(リスト)モード: カード型のタスク一覧+気分表示。初代UI。
import { PALETTE, SPRITES, SPRITE_W, SPRITE_H } from "./sprites.js";

const $ = (id) => document.getElementById(id);

const LEVEL_TEXT = {
  excellent: "エクセレント！", happy: "ごきげん", normal: "ふつう", tired: "ぐったり…",
};
const SAY = {
  excellent: ["ワニ、感動しました！", "この調子です、主人！", "研究がはかどりますね！"],
  happy: ["いい調子ですね", "その調子でいきましょう", "ふふ、順調です"],
  normal: ["今日は何をしますか？", "ひとつ着手してみませんか", "マイペースでいきましょう"],
  tired: ["進捗をください…", "1件だけでも…", "おなかがすきました…"],
  sleeping: ["すやすや…", "Zzz…"],
};

export function initClassic(core) {
  const { statusJa, statusOf, EXCLUDED } = core;
  const stage = $("stage");
  const ctx = stage.getContext("2d");
  let state = null;
  let frameIndex = 0;
  let overrideSprite = null;
  let timer = null;

  function spriteName() {
    if (overrideSprite) return overrideSprite;
    if (!state) return "normal";
    if (state.mood.sleeping) return "sleeping";
    return state.mood.level;
  }

  function drawFrame() {
    const frames = SPRITES[spriteName()] || SPRITES.normal;
    const rows = frames[frameIndex % frames.length];
    ctx.clearRect(0, 0, SPRITE_W, SPRITE_H);
    for (let y = 0; y < rows.length; y++) {
      for (let x = 0; x < rows[y].length; x++) {
        const c = PALETTE[rows[y][x]];
        if (!c) continue;
        ctx.fillStyle = c;
        ctx.fillRect(x, y, 1, 1);
      }
    }
  }

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
      btn.onclick = async () => {
        if (s === t.status) return;
        btn.disabled = true;
        try {
          const result = await core.updateStatus(t, s);
          if (result.event === "done") celebrate();
          await core.refresh();
        } catch (e) {
          core.showError(`更新に失敗しました: ${e.message}`);
          btn.disabled = false;
        }
      };
      actions.appendChild(btn);
    }
    card.appendChild(actions);
    return card;
  }

  function celebrate() {
    overrideSprite = "excellent";
    stage.classList.add("pop");
    setTimeout(() => stage.classList.remove("pop"), 600);
    setTimeout(() => { overrideSprite = null; drawFrame(); }, 4000);
  }

  function update(s) {
    state = s;
    const m = state.mood;
    $("mood-label").textContent = m.sleeping ? "おやすみ中" : (LEVEL_TEXT[m.level] || m.level);
    $("mood-bar").style.width = `${m.mood}%`;
    const sayKey = m.sleeping ? "sleeping" : m.level;
    const says = SAY[sayKey] || SAY.normal;
    $("wani-say").textContent = says[Math.floor(Math.random() * says.length)];

    const p = state.progress;
    $("progress-text").textContent = `${p.done} / ${p.total} 完了`;
    $("progress-bar").style.width = `${p.percent}%`;

    const list = $("task-list");
    list.replaceChildren();
    const active = [], waiting = [], wish = [];
    for (const t of state.tasks) {
      const st = statusOf(t);
      if (st === "waiting") waiting.push(t);
      else if (st === "wish list") wish.push(t);
      else active.push(t);
    }
    if (!active.length) {
      const div = document.createElement("div");
      div.className = "tasks-empty";
      div.textContent = state.error ? "" : "アクティブなタスクがありません。＋で追加してください。";
      list.appendChild(div);
    } else {
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
    drawFrame();
  }

  return {
    update,
    show() { timer = setInterval(() => { frameIndex++; drawFrame(); }, 600); },
    hide() { clearInterval(timer); },
  };
}
