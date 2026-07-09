// ぼうけんモード: DQウォークのストーリーモード風の横スクロール一枚絵。
// 左にワニ博士、右へ進む道。アクティブなタスク=道中の敵モンスター。
//   着手/レビュー = たたかう(敵と交戦中)
//   完了        = とどめ(スロット演出→討伐→ドロップ→前進)
//   後回し/待ち  = にげる/様子見(敵が道端に退く)
// タスクの状態変更はすべて共通のタスクシート(core.showTaskSheet)経由。
import { PALETTE, SPRITES, OBJECTS, SPRITE_W, SPRITE_H } from "./sprites.js";

const $ = (id) => document.getElementById(id);
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

const CW = 360, CH = 200;          // 論理キャンバスサイズ
const GROUND_Y = 172;              // 地面(足元)のy
const WANI_X = 52;                 // ワニ博士の立ち位置
const BATTLE_X = 240;              // 先頭の敵の立ち位置
const ENEMY_GAP = 64;              // 後続の敵の間隔

const ENEMY_TYPES = ["slime", "bat", "mushroom", "ghost", "golem"];
const ENEMY_NAMES = {
  slime: "タスクスライム", bat: "しめきりコウモリ", mushroom: "さきのばしダケ",
  ghost: "みえないおばけ", golem: "おもごしゴーレム",
};

// ---- スプライトのオフスクリーン描画キャッシュ ----
const cache = new Map();
function sheet(rows, key) {
  if (cache.has(key)) return cache.get(key);
  const w = Math.max(...rows.map((r) => r.length), 1);
  const c = document.createElement("canvas");
  c.width = w; c.height = rows.length;
  const g = c.getContext("2d");
  for (let y = 0; y < rows.length; y++) {
    for (let x = 0; x < rows[y].length; x++) {
      const col = PALETTE[rows[y][x]];
      if (!col) continue;
      g.fillStyle = col;
      g.fillRect(x, y, 1, 1);
    }
  }
  cache.set(key, c);
  return c;
}
const waniSheet = (name, i) => {
  const frames = SPRITES[name] || SPRITES.normal;
  return sheet(frames[i % frames.length], `w:${name}:${i % frames.length}`);
};
const objSheet = (name, i = 0) => {
  const o = OBJECTS[name];
  return sheet(o.frames[i % o.frames.length], `o:${name}:${i % o.frames.length}`);
};

function hashStr(s) {
  let h = 0;
  for (const ch of String(s)) h = (h * 31 + ch.codePointAt(0)) >>> 0;
  return h;
}

export function initAdventure(core) {
  const { statusOf, EXCLUDED } = core;
  const canvas = $("adv-canvas");
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;

  let state = null;
  let visible = false;
  let raf = null;
  let t = 0;                 // フレームカウンタ
  let scrollX = 0;           // 背景スクロール量(討伐で前進)
  let scrollTarget = 0;
  let enemies = [];          // 表示中の敵 [{task, type, x, dead}]
  let effects = [];          // 一時演出 [{kind, x, y, t, ...}]
  let msg = "";
  let msgUntil = 0;

  // ---- タスク→敵の対応 ----
  function rebuildEnemies() {
    const active = state.tasks
      .filter((tk) => !EXCLUDED.has(statusOf(tk)) && statusOf(tk) !== "done");
    const order = { "in progress": 0, "review": 1, "todo": 2 };
    active.sort((a, b) =>
      (order[statusOf(a)] ?? 3) - (order[statusOf(b)] ?? 3)
      || (a.number ?? 1e9) - (b.number ?? 1e9));
    enemies = active.map((task, i) => ({
      task,
      type: ENEMY_TYPES[hashStr(task.item_id) % ENEMY_TYPES.length],
      x: BATTLE_X + i * ENEMY_GAP,
      seed: hashStr(task.item_id),
    }));
  }

  function say(text, ms = 4000) {
    msg = text;
    msgUntil = Date.now() + ms;
    $("adv-msg").textContent = text;
  }

  function defaultMsg() {
    if (!state) return "";
    if (state.mood.sleeping) return "ワニ博士は やすんでいる… Zzz";
    if (!enemies.length) return "あたりは しずかだ。＋でタスクを よびだせる。";
    const e = enemies[0];
    const st = statusOf(e.task);
    if (st === "in progress") return `${ENEMY_NAMES[e.type]}と たたかっている！(${short(e.task.title)})`;
    if (st === "review") return `${ENEMY_NAMES[e.type]}は ひんしだ！あとひといき！`;
    return `${ENEMY_NAMES[e.type]}が ゆくてを ふさいでいる！(${short(e.task.title)})`;
  }

  const short = (s, n = 12) => (s.length > n ? s.slice(0, n) + "…" : s);

  // ---- 演出 ----
  function spawnBurst(x, y, kind) {
    for (let i = 0; i < 8; i++) {
      effects.push({
        kind: "particle", x, y,
        vx: (Math.random() - 0.5) * 3, vy: -Math.random() * 3 - 1,
        color: kind === "crit" ? "#ffd447" : "#ffffff",
        t: 0, life: 24,
      });
    }
  }
  function spawnDrop(x, y) {
    for (const [name, dx] of [["coin", -10], ["herb", 8]]) {
      effects.push({ kind: "drop", sprite: name, x: x + dx, y, vy: -2.6, t: 0, life: 46 });
    }
  }

  // スロット演出 → 討伐。完了操作の後に呼ばれる(結果は演出のみ、データは確定済み)
  function playKill() {
    const e = enemies[0];
    const x = e ? e.x : BATTLE_X;
    if (REDUCED) { say("たおした！"); return; }
    const symbols = ["coin", "herb", "slime"];
    const crit = Math.random() < 0.3;
    const reels = crit
      ? [0, 0, 0].map(() => symbols[(Math.random() * 3) | 0]).fill(symbols[(Math.random() * 3) | 0])
      : [symbols[0], symbols[1], symbols[(Math.random() * 3) | 0]];
    effects.push({ kind: "slot", reels, crit, t: 0, life: 70, x });
    setTimeout(() => {
      say(crit ? "かいしんの いちげき！！" : "こうげき！ たおした！");
      effects.push({ kind: "slash", x, y: GROUND_Y - 24, t: 0, life: 14 });
      spawnBurst(x, GROUND_Y - 24, crit ? "crit" : "hit");
      spawnDrop(x, GROUND_Y - 20);
      scrollTarget += 72;   // 討伐で前進
    }, REDUCED ? 0 : 1200);
  }

  function playStarted() {
    if (REDUCED) { say("たたかいを いどんだ！"); return; }
    say("たたかいを いどんだ！ ツボが われて やくそうが でてきた！");
    effects.push({ kind: "lunge", t: 0, life: 20 });
    effects.push({ kind: "potbreak", x: WANI_X + 60, y: GROUND_Y, t: 0, life: 40 });
    effects.push({ kind: "drop", sprite: "herb", x: WANI_X + 66, y: GROUND_Y - 8, vy: -2.4, t: 0, life: 46 });
  }

  // core経由: タスクシートでの操作結果を受けて演出を出す
  function onTaskEvent(result) {
    if (result.event === "done") playKill();
    else if (result.event === "started") playStarted();
    else if (result.event === "undone") say("たおしたはずの敵が よみがえった…！");
    else say("じんけいを たてなおした。");
  }

  function onTaskAdded() {
    say("あたらしい モンスターのけはいがする…！");
  }

  // ---- 背景・シーン描画 ----
  function drawScene() {
    const sleeping = state?.mood.sleeping;
    // 空
    const sky = ctx.createLinearGradient(0, 0, 0, CH);
    if (sleeping) { sky.addColorStop(0, "#101a33"); sky.addColorStop(1, "#26324f"); }
    else { sky.addColorStop(0, "#8fd4ff"); sky.addColorStop(1, "#d8f2c9"); }
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, CW, CH);

    if (sleeping) {
      // 星と月
      ctx.fillStyle = "#f4f0d8";
      const seed = 12345;
      for (let i = 0; i < 26; i++) {
        const sx = (hashStr(i + "s") % CW);
        const sy = (hashStr(i + "y") % 90);
        ctx.globalAlpha = 0.4 + ((i + (t >> 4)) % 3) * 0.3;
        ctx.fillRect(sx, sy, 2, 2);
      }
      ctx.globalAlpha = 1;
      ctx.beginPath();
      ctx.arc(300, 40, 16, 0, Math.PI * 2);
      ctx.fill();
    } else {
      // 太陽
      ctx.fillStyle = "#ffe08a";
      ctx.beginPath();
      ctx.arc(300, 38, 15, 0, Math.PI * 2);
      ctx.fill();
    }

    // 遠景の山(パララックス 0.25x)
    ctx.fillStyle = sleeping ? "#1d2c45" : "#a5cf8d";
    const far = -((scrollX * 0.25) % 180);
    for (let x = far - 180; x < CW + 180; x += 180) {
      ctx.beginPath();
      ctx.moveTo(x, 130);
      ctx.quadraticCurveTo(x + 45, 70, x + 90, 130);
      ctx.quadraticCurveTo(x + 135, 88, x + 180, 130);
      ctx.fill();
    }

    // 草原と道
    ctx.fillStyle = sleeping ? "#20372a" : "#63b466";
    ctx.fillRect(0, 130, CW, CH - 130);
    ctx.fillStyle = sleeping ? "#3a2f24" : "#c8a06a";
    ctx.fillRect(0, GROUND_Y - 6, CW, 26);
    // 道の轍
    ctx.fillStyle = sleeping ? "#2c2419" : "#b58c58";
    const rut = -(scrollX % 34);
    for (let x = rut - 34; x < CW + 34; x += 34) {
      ctx.fillRect(x, GROUND_Y + 4, 16, 3);
    }

    // 道端のツボと草(1xパララックス、装飾)
    const deco = -(scrollX % 220);
    for (let x = deco - 220; x < CW + 220; x += 220) {
      const worldIdx = Math.round((x + scrollX) / 220);
      const broken = (x + 110) < WANI_X; // ワニ博士が通過済みのツボは割れている
      const potImg = objSheet(broken ? "pot_broken" : "pot");
      ctx.drawImage(potImg, x + 110, GROUND_Y - potImg.height * 2 + 8, potImg.width * 2, potImg.height * 2);
      ctx.fillStyle = sleeping ? "#2c4a34" : "#4d9b53";
      ctx.fillRect(x + 30, GROUND_Y - 8, 3, 8);
      ctx.fillRect(x + 36, GROUND_Y - 11, 3, 11);
    }
  }

  function drawWani() {
    const sleeping = state?.mood.sleeping;
    let name = sleeping ? "sleeping" : (state?.mood.level || "normal");
    if (name === "happy") name = "normal"; // 歩き姿はnormal、演出時のみhappy/excellent
    const lunge = effects.find((e) => e.kind === "lunge");
    const slash = effects.find((e) => e.kind === "slash");
    if (slash) name = "excellent";
    const bob = REDUCED ? 0 : Math.sin(t / 9) * 1.6;
    const dx = lunge ? Math.sin((lunge.t / lunge.life) * Math.PI) * 46 : 0;
    const img = waniSheet(name, (t / 18) | 0);
    const scale = 2;
    ctx.drawImage(img, WANI_X + dx - (SPRITE_W * scale) / 2,
      GROUND_Y - SPRITE_H * scale + 2 + (sleeping ? 0 : bob),
      SPRITE_W * scale, SPRITE_H * scale);

    if (sleeping && !REDUCED) {
      // たき火
      const fx = WANI_X + 52, fy = GROUND_Y - 2;
      ctx.fillStyle = "#6b4a2b";
      ctx.fillRect(fx - 8, fy - 3, 16, 4);
      const flame = 4 + Math.sin(t / 5) * 2;
      ctx.fillStyle = "#ff9a3d";
      ctx.beginPath();
      ctx.moveTo(fx - 5, fy - 3);
      ctx.quadraticCurveTo(fx, fy - 14 - flame, fx + 5, fy - 3);
      ctx.fill();
      ctx.fillStyle = "#ffd447";
      ctx.beginPath();
      ctx.moveTo(fx - 2.5, fy - 3);
      ctx.quadraticCurveTo(fx, fy - 8 - flame / 2, fx + 2.5, fy - 3);
      ctx.fill();
    }
  }

  function drawEnemies() {
    for (let i = 0; i < enemies.length; i++) {
      const e = enemies[i];
      const target = BATTLE_X + i * ENEMY_GAP;
      e.x += (target - e.x) * (REDUCED ? 1 : 0.12); // 前が倒れたらつめる
      if (e.x > CW + 20) continue;
      const img = objSheet(e.type, ((t + e.seed) / 16) | 0);
      const scale = i === 0 ? 2.4 : 2;
      const hop = REDUCED ? 0 : Math.sin((t + e.seed) / 11) * (i === 0 ? 2.4 : 1.2);
      const w = img.width * scale, h = img.height * scale;
      const y = GROUND_Y - h + 4 + hop;
      ctx.globalAlpha = i === 0 ? 1 : 0.85;
      ctx.drawImage(img, e.x - w / 2, y, w, h);
      ctx.globalAlpha = 1;
      e.hitbox = { x: e.x - w / 2, y, w, h };

      // HPバー(状態を表す): Todo=満タン, In Progress=2/3, Review=1/3
      const st = statusOf(e.task);
      const hp = st === "review" ? 1 / 3 : st === "in progress" ? 2 / 3 : 1;
      ctx.fillStyle = "rgba(0,0,0,.45)";
      ctx.fillRect(e.x - 16, y - 10, 32, 5);
      ctx.fillStyle = hp > 0.5 ? "#e5484d" : "#ff9a3d";
      ctx.fillRect(e.x - 15, y - 9, 30 * hp, 3);

      // 名前(タスク名)
      if (i < 3) {
        ctx.font = "9px sans-serif";
        ctx.textAlign = "center";
        const label = short(e.task.title, i === 0 ? 14 : 8);
        ctx.lineWidth = 3;
        ctx.strokeStyle = "rgba(0,0,0,.55)";
        ctx.strokeText(label, e.x, y - 14);
        ctx.fillStyle = "#fff";
        ctx.fillText(label, e.x, y - 14);
      }
    }
  }

  function drawEffects() {
    effects = effects.filter((e) => e.t <= e.life);
    for (const e of effects) {
      e.t++;
      if (e.kind === "particle") {
        e.x += e.vx; e.y += e.vy; e.vy += 0.15;
        ctx.globalAlpha = 1 - e.t / e.life;
        ctx.fillStyle = e.color;
        ctx.fillRect(e.x, e.y, 3, 3);
        ctx.globalAlpha = 1;
      } else if (e.kind === "drop") {
        e.y += e.vy; e.vy += 0.12;
        const img = objSheet(e.sprite);
        ctx.globalAlpha = e.t > e.life - 10 ? (e.life - e.t) / 10 : 1;
        ctx.drawImage(img, e.x, e.y, img.width * 2, img.height * 2);
        ctx.globalAlpha = 1;
      } else if (e.kind === "slash") {
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 3;
        const p = e.t / e.life;
        ctx.beginPath();
        ctx.moveTo(e.x - 22 + p * 10, e.y - 20);
        ctx.lineTo(e.x + 14 + p * 10, e.y + 14);
        ctx.stroke();
      } else if (e.kind === "potbreak") {
        const img = objSheet(e.t < 12 ? "pot" : "pot_broken");
        ctx.drawImage(img, e.x, e.y - img.height * 2 + 8, img.width * 2, img.height * 2);
      } else if (e.kind === "slot") {
        drawSlot(e);
      }
    }
  }

  // DQ風ウィンドウのスロット(とどめ演出)
  function drawSlot(e) {
    const w = 150, h = 52;
    const x = CW / 2 - w / 2, y = 40;
    ctx.fillStyle = "rgba(8,8,16,.88)";
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.strokeRect(x + 2, y + 2, w - 4, h - 4);
    const symbols = ["coin", "herb", "slime"];
    for (let i = 0; i < 3; i++) {
      const stopAt = 18 + i * 14;
      const spinning = e.t < stopAt;
      const name = spinning ? symbols[(e.t + i) % 3] : e.reels[i];
      const img = objSheet(name);
      const cx = x + 26 + i * 46, cy = y + h / 2;
      const s = 22 / Math.max(img.width, img.height);
      ctx.save();
      if (spinning) ctx.globalAlpha = 0.7;
      ctx.drawImage(img, cx - (img.width * s) / 2, cy - (img.height * s) / 2,
        img.width * s, img.height * s);
      ctx.restore();
    }
    if (e.crit && e.t > 50 && (e.t >> 2) % 2) {
      ctx.fillStyle = "rgba(255,212,71,.25)";
      ctx.fillRect(0, 0, CW, CH);
    }
  }

  function drawHud() {
    if (!state) return;
    $("adv-stage").textContent = `ステージ ${Math.max(1, state.mood.streak)}`;
    $("adv-kills").textContent = `討伐 ${state.progress.done}/${state.progress.total}`;
    $("adv-mood").textContent = `気分 ${Math.round(state.mood.mood)}`;
  }

  function frame() {
    t++;
    scrollX += (scrollTarget - scrollX) * 0.06;
    drawScene();
    drawWani();
    if (!state?.mood.sleeping) drawEnemies();
    drawEffects();
    if (Date.now() > msgUntil) $("adv-msg").textContent = defaultMsg();
    if (visible && !REDUCED) raf = requestAnimationFrame(frame);
  }

  // ---- タップ判定 ----
  canvas.addEventListener("click", (ev) => {
    const rect = canvas.getBoundingClientRect();
    const x = (ev.clientX - rect.left) * (CW / rect.width);
    const y = (ev.clientY - rect.top) * (CH / rect.height);
    for (const e of enemies) {
      const hb = e.hitbox;
      if (hb && x >= hb.x - 6 && x <= hb.x + hb.w + 6 && y >= hb.y - 16 && y <= hb.y + hb.h + 6) {
        core.showTaskSheet(e.task);
        return;
      }
    }
    // ワニ博士タップ → ひとこと
    if (x < WANI_X + 40) say(defaultMsg());
  });

  // ---- 待ち/後回しの脇道表示 ----
  function renderSide() {
    const side = $("adv-side");
    side.replaceChildren();
    const waiting = state.tasks.filter((tk) => statusOf(tk) === "waiting");
    const wish = state.tasks.filter((tk) => statusOf(tk) === "wish list");
    for (const [label, tasks] of [["⛺ 待機 ", waiting], ["🧰 後回し ", wish]]) {
      if (!tasks.length) continue;
      const details = document.createElement("details");
      details.className = "adv-side-box";
      const summary = document.createElement("summary");
      summary.textContent = `${label}${tasks.length}件`;
      details.appendChild(summary);
      for (const tk of tasks) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "adv-side-item";
        btn.textContent = (tk.number ? `#${tk.number} ` : "") + short(tk.title, 20);
        btn.onclick = () => core.showTaskSheet(tk);
        details.appendChild(btn);
      }
      side.appendChild(details);
    }
  }

  return {
    update(s) {
      state = s;
      rebuildEnemies();
      renderSide();
      drawHud();
      if (REDUCED) { drawScene(); drawWani(); if (!state.mood.sleeping) drawEnemies(); }
      if (Date.now() > msgUntil) $("adv-msg").textContent = defaultMsg();
    },
    show() {
      visible = true;
      if (!REDUCED) raf = requestAnimationFrame(frame);
      else if (state) { drawScene(); drawWani(); drawEnemies(); }
    },
    hide() {
      visible = false;
      cancelAnimationFrame(raf);
    },
    onTaskEvent,
    onTaskAdded,
  };
}
