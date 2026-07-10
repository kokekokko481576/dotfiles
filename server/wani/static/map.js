// マップモード: 今日の道のりをすごろく風の俯瞰マップで表示。
// 討伐済み(Done)は旗、現在地にワニ博士、先のマスは未踏。タップでタスクシート。
import { PALETTE, SPRITES } from "./sprites.js";

const $ = (id) => document.getElementById(id);
const NODE_R = 17;
const COLS = 3;
const STEP_X = 104, STEP_Y = 86, PAD = 36;

export function initMap(core) {
  const { statusOf, statusJa, EXCLUDED } = core;
  let state = null;

  // ワニ博士の顔(目〜口)だけを切り出したdata URL。すごろくのコマとして
  // 現在地のマスにそのまま乗せる
  const FACE = { x0: 3, y0: 1, w: 26, h: 18 };
  let waniIcon = null;
  function makeWaniIcon() {
    const rows = SPRITES.normal[0];
    const c = document.createElement("canvas");
    c.width = FACE.w; c.height = FACE.h;
    const g = c.getContext("2d");
    for (let y = 0; y < FACE.h; y++) {
      for (let x = 0; x < FACE.w; x++) {
        const col = PALETTE[rows[y + FACE.y0]?.[x + FACE.x0]];
        if (!col) continue;
        g.fillStyle = col;
        g.fillRect(x, y, 1, 1);
      }
    }
    return c.toDataURL();
  }

  function nodePos(i) {
    const row = Math.floor(i / COLS);
    const col = i % COLS;
    const x = PAD + (row % 2 === 0 ? col : COLS - 1 - col) * STEP_X;
    return { x, y: PAD + row * STEP_Y };
  }

  function render() {
    waniIcon = waniIcon || makeWaniIcon();
    const root = $("map-root");
    // 作戦会議承認後は「今日の道のり」= 今日やるリストだけ
    // (完了してもリストに残るので、通過済みマスとして表示され続ける)
    const active = state.tasks.filter((t) =>
      !EXCLUDED.has(statusOf(t)) && (!core.todayApproved() || core.isToday(t)));
    // 討伐済みを道の先頭(通過済み)に、残りはProjectの手動順
    active.sort((a, b) =>
      (statusOf(a) === "done" ? 0 : 1) - (statusOf(b) === "done" ? 0 : 1));

    $("map-progress").textContent = `${state.progress.done} / ${state.progress.total}`;

    const n = active.length;
    if (!n) {
      root.innerHTML = '<div class="tasks-empty">タスクがありません。＋で追加してください。</div>';
      return;
    }
    // 現在地 = 最初の未討伐ノード
    let current = active.findIndex((t) => statusOf(t) !== "done");
    if (current === -1) current = n - 1;

    const rows = Math.ceil(n / COLS);
    const wsvg = PAD * 2 + (COLS - 1) * STEP_X;
    const hsvg = PAD * 2 + (rows - 1) * STEP_Y + 20;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", `0 0 ${wsvg} ${hsvg}`);
    svg.classList.add("map-svg");

    // 道(ノードを順に結ぶ)
    let d = "";
    for (let i = 0; i < n; i++) {
      const p = nodePos(i);
      d += (i === 0 ? `M${p.x},${p.y}` : ` L${p.x},${p.y}`);
    }
    for (const [cls, dash] of [["map-road-outline", ""], ["map-road", "1 10"]]) {
      const path = document.createElementNS(svg.namespaceURI, "path");
      path.setAttribute("d", d);
      path.setAttribute("class", cls);
      if (dash) path.setAttribute("stroke-dasharray", dash);
      svg.appendChild(path);
    }

    for (let i = 0; i < n; i++) {
      const t = active[i];
      const p = nodePos(i);
      const st = statusOf(t);
      const g = document.createElementNS(svg.namespaceURI, "g");
      g.setAttribute("transform", `translate(${p.x},${p.y})`);
      g.classList.add("map-node", `map-${st.replace(" ", "-")}`);
      g.setAttribute("role", "button");
      g.setAttribute("tabindex", "0");

      const isCurrent = i === current && st !== "done";

      const circle = document.createElementNS(svg.namespaceURI, "circle");
      circle.setAttribute("r", NODE_R);
      g.appendChild(circle);

      if (!isCurrent) {
        const label = document.createElementNS(svg.namespaceURI, "text");
        label.setAttribute("class", "map-node-num");
        label.setAttribute("dy", "4");
        label.textContent = st === "done" ? "✓" : (t.number ?? "メ");
        g.appendChild(label);
      }

      const title = document.createElementNS(svg.namespaceURI, "text");
      title.setAttribute("class", "map-node-title");
      title.setAttribute("y", NODE_R + 13);
      title.textContent = t.title.length > 8 ? t.title.slice(0, 8) + "…" : t.title;
      g.appendChild(title);

      if (st === "done") {
        const flag = document.createElementNS(svg.namespaceURI, "text");
        flag.setAttribute("y", -NODE_R - 3);
        flag.setAttribute("class", "map-flag");
        flag.textContent = "🚩";
        g.appendChild(flag);
      }
      if (isCurrent) {
        // 現在地のマスはワニ博士の顔で埋める(すごろくのコマ)
        const w = NODE_R * 2.5;
        const h = w * (FACE.h / FACE.w);
        const img = document.createElementNS(svg.namespaceURI, "image");
        img.setAttribute("href", waniIcon);
        img.setAttribute("x", -w / 2);
        img.setAttribute("y", -h / 2 - 2);
        img.setAttribute("width", w);
        img.setAttribute("height", h);
        img.style.imageRendering = "pixelated";
        g.appendChild(img);
      }
      const open = () => core.showTaskSheet(t);
      g.addEventListener("click", open);
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") open(); });
      svg.appendChild(g);
    }

    // ゴール
    const goal = document.createElementNS(svg.namespaceURI, "text");
    const gp = nodePos(n - 1);
    goal.setAttribute("x", gp.x);
    goal.setAttribute("y", gp.y + NODE_R + 30);
    goal.setAttribute("class", "map-goal");
    goal.textContent = state.progress.done >= state.progress.total && state.progress.total > 0
      ? "🏰 ぜんぶ討伐！おみごと！" : "🏰 ゴール";
    svg.appendChild(goal);

    root.replaceChildren(svg);

    // 脇道(待ち/後回し)
    const side = document.createElement("div");
    side.className = "map-side";
    const waiting = state.tasks.filter((t) => statusOf(t) === "waiting");
    const wish = state.tasks.filter((t) => statusOf(t) === "wish list");
    for (const [label, tasks] of [["⛺ 待機中", waiting], ["🧰 後回しBOX", wish]]) {
      if (!tasks.length) continue;
      const box = document.createElement("div");
      box.className = "map-side-box";
      const head = document.createElement("div");
      head.className = "map-side-head";
      head.textContent = `${label} ${tasks.length}件`;
      box.appendChild(head);
      for (const t of tasks) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "adv-side-item";
        btn.textContent = (t.number ? `#${t.number} ` : "") +
          (t.title.length > 22 ? t.title.slice(0, 22) + "…" : t.title);
        btn.onclick = () => core.showTaskSheet(t);
        box.appendChild(btn);
      }
      side.appendChild(box);
    }
    root.appendChild(side);
  }

  return {
    update(s) { state = s; render(); },
    show() {},
    hide() {},
  };
}
