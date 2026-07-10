// リストモード: コンパクトな1行1タスクの一覧。
// - 行タップで共通タスクシート(状態変更・きょうやる・並び替え)
// - 表示順: ぼうけん同期(=Projectの手動順、デフォルト) / 期限順 / 番号順
// - ぼうけん同期のときだけ ≡ ハンドルのドラッグで並び替えできる(GitHubにも反映)
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

const SORTS = [
  ["adventure", "ぼうけん同期"],
  ["due", "期限順"],
  ["number", "番号順"],
];

export function initClassic(core) {
  const { statusJa, statusOf, EXCLUDED } = core;
  const stage = $("stage");
  const ctx = stage.getContext("2d");
  let state = null;
  let frameIndex = 0;
  let overrideSprite = null;
  let timer = null;
  let sortMode = localStorage.getItem("wani_sort") || "adventure";

  // ---- ワニ博士(気分表示) ----
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

  function celebrate() {
    overrideSprite = "excellent";
    stage.classList.add("pop");
    setTimeout(() => stage.classList.remove("pop"), 600);
    setTimeout(() => { overrideSprite = null; drawFrame(); }, 4000);
  }

  // ---- ソート ----
  function sorted(tasks) {
    const arr = [...tasks];
    if (sortMode === "due") {
      arr.sort((a, b) => (a.due || "9999") < (b.due || "9999") ? -1
        : (a.due || "9999") > (b.due || "9999") ? 1 : 0);
    } else if (sortMode === "number") {
      arr.sort((a, b) => (a.number ?? 1e9) - (b.number ?? 1e9));
    }
    // adventure = APIの並びのまま(Projectの手動順)
    return arr;
  }

  function dueChip(t) {
    const chip = document.createElement("span");
    const today = new Date().toISOString().slice(0, 10);
    if (t.due) {
      chip.className = "row-due" + (t.due < today ? " overdue" : t.due === today ? " today" : "");
      chip.textContent = t.due.slice(5).replace("-", "/");
    } else {
      chip.className = "row-due empty";
      chip.textContent = "期限";
    }
    chip.title = "タップで期限を編集";
    chip.addEventListener("click", (e) => {
      e.stopPropagation();
      openDueEditor(chip, t);
    });
    return chip;
  }

  // 期限チップのその場編集(date input + クリア)。GitHubの日付フィールドを書き換える
  function openDueEditor(anchor, t) {
    const wrap = document.createElement("span");
    wrap.className = "row-due-edit";
    const input = document.createElement("input");
    input.type = "date";
    input.value = t.due || "";
    wrap.appendChild(input);
    const clear = document.createElement("button");
    clear.type = "button";
    clear.textContent = "✕";
    clear.title = "期限をクリア";
    clear.hidden = !t.due;
    wrap.appendChild(clear);
    wrap.addEventListener("click", (e) => e.stopPropagation());
    anchor.replaceWith(wrap);

    // 確定はchangeイベント、キャンセルはエディタ外タップ。
    // (blurで消す方式はスマホの日付ピッカーが開いた瞬間にblurが飛び、
    //  選択を確定する前にエディタが破棄されてしまうためやめた)
    core.setEditing(true);
    let committed = false;
    const cleanup = () => {
      document.removeEventListener("pointerdown", onOutside, true);
      core.setEditing(false);
    };
    const post = async (due) => {
      if (committed) return;
      committed = true;
      cleanup();
      try {
        const res = await fetch(`api/tasks/${encodeURIComponent(t.item_id)}/due`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ due }),
        });
        if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
      } catch (e) {
        core.showError(`期限の更新に失敗しました: ${e.message}`);
      }
      await core.refresh();
    };
    input.addEventListener("change", () => {
      if (input.value && input.value !== t.due) post(input.value);
    });
    clear.onclick = () => post(null);
    const onOutside = (e) => {
      if (!wrap.contains(e.target)) {
        cleanup();
        if (!committed) core.refresh(); // 変更なしで閉じる
      }
    };
    setTimeout(() => document.addEventListener("pointerdown", onOutside, true), 0);
    input.focus();
    input.showPicker?.();
  }

  // ---- 行 ----
  function row(t, { draggable = false } = {}) {
    const el = document.createElement("div");
    el.className = "row" + (statusOf(t) === "done" ? " done" : "");
    el.dataset.itemId = t.item_id;

    if (draggable) {
      const handle = document.createElement("span");
      handle.className = "row-handle";
      handle.textContent = "≡";
      handle.addEventListener("pointerdown", (e) => startDrag(e, el));
      el.appendChild(handle);
    }
    const title = document.createElement("span");
    title.className = "row-title";
    title.textContent = (core.isToday(t) ? "⭐" : "") +
      (t.number ? `#${t.number} ` : "") + t.title;
    el.appendChild(title);

    const due = dueChip(t);
    if (due) el.appendChild(due);

    const chip = document.createElement("span");
    chip.className = `row-status st-${statusOf(t).replace(" ", "-")}`;
    chip.textContent = statusJa(t.status);
    el.appendChild(chip);

    el.addEventListener("click", (e) => {
      if (e.target.classList.contains("row-handle")) return;
      core.showTaskSheet(t);
    });
    return el;
  }

  // ---- ドラッグ並び替え(ぼうけん同期のときのみ) ----
  let drag = null;
  function startDrag(e, el) {
    e.preventDefault();
    const list = el.parentElement;
    el.setPointerCapture?.(e.pointerId);
    drag = { el, list, startY: e.clientY, moved: false };
    el.classList.add("dragging");

    const onMove = (ev) => {
      if (!drag) return;
      drag.moved = true;
      // ポインタ位置に対応するスロットへ行を差し込み直す(Doneの行より上まで)
      const y = ev.clientY;
      let placed = false;
      for (const sib of [...list.children]) {
        if (sib === el) continue;
        if (sib.classList.contains("done")) break;
        const r = sib.getBoundingClientRect();
        if (y < r.top + r.height / 2) {
          list.insertBefore(el, sib);
          placed = true;
          break;
        }
      }
      if (!placed) {
        const firstDone = [...list.children].find((c) => c !== el && c.classList.contains("done"));
        firstDone ? list.insertBefore(el, firstDone) : list.appendChild(el);
      }
    };
    const onUp = async () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
      if (!drag) return;
      const { el: dEl, list: dList, moved } = drag;
      drag = null;
      dEl.classList.remove("dragging");
      dEl.style.transform = "";
      if (!moved) return;
      const prev = dEl.previousElementSibling;
      try {
        await moveTask(dEl.dataset.itemId, prev ? prev.dataset.itemId : null);
        await core.refresh();
      } catch (err) {
        core.showError(`並び替えに失敗しました: ${err.message}`);
        await core.refresh();
      }
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
  }

  async function moveTask(itemId, afterItemId) {
    const res = await fetch(`api/tasks/${encodeURIComponent(itemId)}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ after_item_id: afterItemId }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
  }

  // ---- 描画 ----
  function update(s) {
    state = s;
    const m = state.mood;
    $("mood-label").textContent = m.sleeping ? "おやすみ中" : (LEVEL_TEXT[m.level] || m.level);
    $("mood-bar").style.width = `${m.mood}%`;
    const says = SAY[m.sleeping ? "sleeping" : m.level] || SAY.normal;
    $("wani-say").textContent = says[Math.floor(Math.random() * says.length)];

    const p = state.progress;
    $("progress-text").textContent = `${p.done} / ${p.total} 完了`;
    $("progress-bar").style.width = `${p.percent}%`;

    // ソート切替
    const toolbar = $("list-toolbar");
    toolbar.replaceChildren();
    const label = document.createElement("span");
    label.textContent = "表示順:";
    toolbar.appendChild(label);
    const select = document.createElement("select");
    select.className = "sort-select";
    for (const [value, text] of SORTS) {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = text;
      opt.selected = value === sortMode;
      select.appendChild(opt);
    }
    select.onchange = () => {
      sortMode = select.value;
      localStorage.setItem("wani_sort", sortMode);
      update(state);
    };
    toolbar.appendChild(select);
    if (sortMode === "adventure") {
      const hint = document.createElement("span");
      hint.className = "sort-hint";
      hint.textContent = "≡を掴んで並び替え";
      toolbar.appendChild(hint);
    }

    const list = $("task-list");
    list.replaceChildren();
    const active = [], waiting = [], wish = [], done = [];
    for (const t of state.tasks) {
      const st = statusOf(t);
      if (st === "waiting") waiting.push(t);
      else if (st === "wish list") wish.push(t);
      else if (st === "done") done.push(t);
      else active.push(t);
    }
    if (!active.length && !done.length) {
      const div = document.createElement("div");
      div.className = "tasks-empty";
      div.textContent = state.error ? "" : "アクティブなタスクがありません。＋で追加してください。";
      list.appendChild(div);
    }
    const draggable = sortMode === "adventure";
    for (const t of sorted(active)) list.appendChild(row(t, { draggable }));
    for (const t of done) list.appendChild(row(t));

    for (const [tasks, boxId, listId, countId] of [
      [waiting, "waiting-box", "waiting-list", "waiting-count"],
      [wish, "wish-box", "wish-list", "wish-count"],
    ]) {
      $(boxId).hidden = !tasks.length;
      $(countId).textContent = tasks.length ? `${tasks.length}件` : "";
      const el = $(listId);
      el.replaceChildren();
      for (const t of tasks) el.appendChild(row(t));
    }
    drawFrame();
  }

  return {
    update,
    show() { timer = setInterval(() => { frameIndex++; drawFrame(); }, 600); },
    hide() { clearInterval(timer); },
    onTaskEvent(result) { if (result.event === "done") celebrate(); },
  };
}
