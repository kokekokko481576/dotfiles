// ぼうけんモード v2: 縁日の射的/古いアーケード筐体風の「紙人形」ステージ。
// 全キャラは下から棒で突き出したパペットとして描画され、
//   ゆれ = 棒の先端を支点にした微回転
//   攻撃/被弾 = 紙をパタッと裏返すフリップ(scaleXアニメ)
//   討伐 = 棒ごと下に引っ込む
// タスク=敵の隊列(並び順はGitHub Projectの手動順)。Googleカレンダーの予定は
// 時間になると「じかんまじん」として最前列に割り込む。
import { PALETTE, SPRITES, OBJECTS, SPRITE_W, SPRITE_H } from "./sprites.js";

const $ = (id) => document.getElementById(id);
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

const CW = 640, CH = 220;          // 論理キャンバス(横長。スマホは横向き推奨)
const GROUND_Y = 186;              // ステージ床
const WANI_X = 86;
const BATTLE_X = 300;
const ENEMY_GAP = 92;

const ENEMY_TYPES = ["slime", "bat", "mushroom", "ghost", "golem"];
const ENEMY_NAMES = {
  slime: "タスクスライム", bat: "しめきりコウモリ", mushroom: "さきのばしダケ",
  ghost: "みえないおばけ", golem: "おもごしゴーレム", clock: "じかんまじん",
  chip: "バグったIC", bug: "バイナリむし", turtle: "あばれタートル",
};
// リポジトリ名 → 敵の見た目。部分一致(大文字小文字無視)で最初にマッチしたもの。
// マッチしなければタスクIDのハッシュでENEMY_TYPESから安定して選ぶ
const REPO_ENEMIES = [
  [/kicad|pcb|circuit/i, "chip"],      // 回路・基板系
  [/lowlayer|firm|embed/i, "bug"],     // ファームウェア・組込み系
  [/ros|ubuntu/i, "turtle"],           // ROS/Ubuntu系
];

function enemyTypeFor(task) {
  for (const [re, type] of REPO_ENEMIES) {
    if (re.test(task.repo || "")) return type;
  }
  return ENEMY_TYPES[hashStr(task.item_id) % ENEMY_TYPES.length];
}

// ---- ドット絵のオフスクリーンキャッシュ ----
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
const objSheet = (name, i = 0) => {
  const o = OBJECTS[name];
  return sheet(o.frames[i % o.frames.length], `o:${name}:${i % o.frames.length}`);
};

function hashStr(s) {
  let h = 0;
  for (const ch of String(s)) h = (h * 31 + ch.codePointAt(0)) >>> 0;
  return h;
}

// ================================================================
// ワニ博士の一枚絵(ドット絵ではない滑らかなカートゥーン)。
// /assets/wani.png をユーザーが置いていればそちらを優先する
// (公式画像は再配布できないためリポジトリには含めない。guide/13参照)。
// ================================================================
const WANI_W = 130, WANI_H = 150;
let customWani = null;
{
  const img = new Image();
  img.onload = () => { customWani = img; };
  img.src = "assets/wani.png";
}

function drawWaniCutout(g, face) {
  const OUT = "#143d20", BODY = "#359e58", BELLY = "#f7f4e6",
        EYE = "#ffd22d", PUPIL = "#181818", MOUTH = "#e85888";
  g.lineWidth = 4;
  g.strokeStyle = OUT;
  g.lineJoin = "round";

  // 尻尾(左後ろにちょこん)
  g.fillStyle = BODY;
  g.beginPath();
  g.moveTo(30, 128);
  g.quadraticCurveTo(2, 132, 8, 112);
  g.quadraticCurveTo(26, 104, 42, 116);
  g.closePath(); g.fill(); g.stroke();

  // 脚
  for (const lx of [46, 76]) {
    g.beginPath();
    g.roundRect(lx, 122, 22, 24, 7);
    g.fillStyle = BODY; g.fill(); g.stroke();
  }
  // 体
  g.beginPath();
  g.ellipse(66, 100, 38, 34, 0, 0, Math.PI * 2);
  g.fillStyle = BODY; g.fill(); g.stroke();
  // 腹(横線入り)
  g.beginPath();
  g.ellipse(66, 106, 24, 24, 0, 0, Math.PI * 2);
  g.fillStyle = BELLY; g.fill();
  g.save();
  g.clip();
  g.lineWidth = 2.5;
  for (const yy of [98, 108, 118]) {
    g.beginPath(); g.moveTo(44, yy); g.lineTo(88, yy); g.stroke();
  }
  g.restore();
  g.lineWidth = 4;

  // 腕
  for (const [ax, rot] of [[26, 0.5], [104, -0.5]]) {
    g.save();
    g.translate(ax, 92); g.rotate(rot);
    g.beginPath(); g.roundRect(-8, -6, 16, 26, 8);
    g.fillStyle = BODY; g.fill(); g.stroke();
    g.restore();
  }

  // 頭(鼻先が右へ長い)
  g.beginPath();
  g.moveTo(20, 62);
  g.quadraticCurveTo(18, 30, 52, 26);
  g.quadraticCurveTo(88, 22, 106, 38);
  g.quadraticCurveTo(126, 52, 122, 62);
  g.quadraticCurveTo(118, 76, 92, 78);
  g.quadraticCurveTo(50, 82, 30, 76);
  g.quadraticCurveTo(20, 72, 20, 62);
  g.closePath();
  g.fillStyle = BODY; g.fill(); g.stroke();

  // 鼻の穴
  g.fillStyle = OUT;
  g.beginPath(); g.ellipse(108, 44, 2.5, 2, 0, 0, Math.PI * 2); g.fill();
  g.beginPath(); g.ellipse(116, 50, 2.5, 2, 0, 0, Math.PI * 2); g.fill();

  // 口(表情で切替)
  if (face === "happy" || face === "excellent") {
    g.beginPath();
    g.moveTo(38, 66);
    g.quadraticCurveTo(80, 88, 118, 60);
    g.quadraticCurveTo(102, 84, 66, 82);
    g.quadraticCurveTo(46, 80, 38, 66);
    g.closePath();
    g.fillStyle = MOUTH; g.fill();
    g.lineWidth = 3; g.stroke();
    // 歯
    g.fillStyle = "#fff";
    for (const [tx, ty] of [[52, 71], [72, 77], [94, 74]]) {
      g.beginPath();
      g.moveTo(tx, ty); g.lineTo(tx + 9, ty - 2); g.lineTo(tx + 5, ty + 6);
      g.closePath(); g.fill();
    }
    g.lineWidth = 4;
  } else if (face === "tired") {
    g.beginPath();
    g.moveTo(44, 72); g.quadraticCurveTo(78, 64, 112, 60);
    g.lineWidth = 3; g.stroke(); g.lineWidth = 4;
  } else {
    g.beginPath();
    g.moveTo(40, 66); g.quadraticCurveTo(80, 78, 116, 56);
    g.lineWidth = 3; g.stroke(); g.lineWidth = 4;
  }

  // 目(頭の上のバンプ)
  for (const ex of [44, 78]) {
    g.beginPath();
    g.ellipse(ex, 24, 15, 16, 0, 0, Math.PI * 2);
    g.fillStyle = BODY; g.fill(); g.stroke();
    if (face === "sleeping") {
      g.beginPath();
      g.moveTo(ex - 9, 26); g.quadraticCurveTo(ex, 32, ex + 9, 26);
      g.lineWidth = 3; g.stroke(); g.lineWidth = 4;
    } else {
      g.beginPath();
      g.ellipse(ex, 25, 10, 11, 0, 0, Math.PI * 2);
      g.fillStyle = EYE; g.fill();
      g.lineWidth = 2.5; g.stroke(); g.lineWidth = 4;
      const lid = face === "tired" ? 6 : 0;
      g.beginPath();
      g.ellipse(ex + 2, 26 + lid / 2, 4.5, 5.5 - lid * 0.3, 0, 0, Math.PI * 2);
      g.fillStyle = PUPIL; g.fill();
      if (face === "tired") {
        g.beginPath();
        g.moveTo(ex - 11, 20); g.lineTo(ex + 11, 20);
        g.lineWidth = 5; g.strokeStyle = "#2c7a44"; g.stroke();
        g.strokeStyle = "#143d20"; g.lineWidth = 4;
      }
    }
  }
}

const waniCutouts = new Map();
function waniCutout(face) {
  if (customWani) return customWani;
  if (waniCutouts.has(face)) return waniCutouts.get(face);
  const c = document.createElement("canvas");
  c.width = WANI_W; c.height = WANI_H;
  drawWaniCutout(c.getContext("2d"), face);
  waniCutouts.set(face, c);
  return c;
}

export function initAdventure(core) {
  const { statusOf, EXCLUDED } = core;
  const canvas = $("adv-canvas");
  const ctx = canvas.getContext("2d");

  let state = null;
  let visible = false;
  let raf = null;
  let t = 0;
  let scrollX = 0, scrollTarget = 0;
  let actors = [];            // 敵パペット [{kind:"task"|"event", ...}]
  let waniFx = null;          // ワニ博士のフリップ演出 {t, life, toFace}
  let effects = [];
  let msg = "", msgUntil = 0;
  let knownEventKeys = new Set();

  const short = (s, n = 14) => (s.length > n ? s.slice(0, n) + "…" : s);
  const dismissKey = (ev) => `wani_ev_${(ev.start || "").slice(0, 10)}_${ev.title}_${ev.start}`;

  // ---- 予定 → 割り込み判定 ----
  function activeEvents() {
    if (!state?.events) return [];
    const now = new Date();
    return state.events.filter((ev) => {
      if (ev.all_day || !ev.start) return false;
      if (localStorage.getItem(dismissKey(ev))) return false;
      const start = new Date(ev.start);
      const end = ev.end ? new Date(ev.end) : new Date(start.getTime() + 3600_000);
      return start <= now && now <= end;
    });
  }

  function upcomingEvents() {
    if (!state?.events) return [];
    const now = new Date();
    return state.events.filter((ev) =>
      !ev.all_day && ev.start && new Date(ev.start) > now);
  }

  // ---- タスク+割込予定 → パペット隊列 ----
  function rebuildActors() {
    const evs = activeEvents().map((ev) => ({
      kind: "event", ev, type: "clock",
      key: dismissKey(ev), seed: hashStr(ev.title),
    }));
    // 敵の順番 = Projectの並び順(手動で変更可能)。in progress等での並べ替えはしない
    const tasks = state.tasks
      .filter((tk) => !EXCLUDED.has(statusOf(tk)) && statusOf(tk) !== "done")
      .map((task) => ({
        kind: "task", task,
        type: enemyTypeFor(task),
        key: task.item_id, seed: hashStr(task.item_id),
      }));
    const next = [...evs, ...tasks];
    // 位置は既存のものを引き継ぐ(新入りは右端から歩いてくる)
    const old = new Map(actors.map((a) => [a.key, a]));
    actors = next.map((a, i) => {
      const prev = old.get(a.key);
      return { ...a, x: prev ? prev.x : CW + 40, sink: prev ? prev.sink : 0, flip: prev?.flip };
    });
    // 予定の割り込みを検知してメッセージ
    for (const a of actors) {
      if (a.kind === "event" && !knownEventKeys.has(a.key)) {
        say(`じかんまじんが あらわれた！『${short(a.ev.title, 16)}』のじかんだ！`, 6000);
      }
    }
    knownEventKeys = new Set(actors.filter((a) => a.kind === "event").map((a) => a.key));
  }

  function say(text, ms = 4000) {
    msg = text;
    msgUntil = Date.now() + ms;
    $("adv-msg").textContent = text;
  }

  function defaultMsg() {
    if (!state) return "";
    if (state.mood.sleeping) return "ワニ博士は やすんでいる… Zzz";
    const a = actors[0];
    if (!a) return "あたりは しずかだ。＋でタスクを よびだせる。";
    if (a.kind === "event") {
      const time = new Date(a.ev.start).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" });
      return `${time}『${short(a.ev.title, 16)}』のじかん！おわったら タップして「すんだ！」`;
    }
    const st = statusOf(a.task);
    if (st === "in progress") return `${ENEMY_NAMES[a.type]}と たたかっている！(${short(a.task.title)})`;
    if (st === "review") return `${ENEMY_NAMES[a.type]}は ひんしだ！あとひといき！`;
    return `${ENEMY_NAMES[a.type]}が ゆくてを ふさいでいる！(${short(a.task.title)})`;
  }

  // ---- 演出 ----
  function spawnBurst(x, y, color) {
    for (let i = 0; i < 10; i++) {
      effects.push({
        kind: "particle", x, y,
        vx: (Math.random() - 0.5) * 3.4, vy: -Math.random() * 3.4 - 1,
        color, t: 0, life: 26,
      });
    }
  }
  function spawnDrop(x, y) {
    for (const [name, dx] of [["coin", -12], ["herb", 10]]) {
      effects.push({ kind: "drop", sprite: name, x: x + dx, y, vy: -2.8, t: 0, life: 50 });
    }
  }

  // フリップはゆっくり1回転(約0.8秒)。裏面(=別の表情)がしっかり見えるように
  function flipWani(toFace, ms = 0) {
    setTimeout(() => { waniFx = { t: 0, life: 50, toFace, until: Date.now() + 3200 }; }, ms);
  }

  function playKill(targetKey) {
    const a = actors.find((x) => x.key === targetKey) || actors[0];
    const x = a ? a.x : BATTLE_X;
    if (REDUCED) { say("たおした！"); return; }
    const crit = Math.random() < 0.3;
    const symbols = ["coin", "herb", "slime"];
    const reels = crit
      ? Array(3).fill(symbols[(Math.random() * 3) | 0])
      : [symbols[0], symbols[1], symbols[(Math.random() * 3) | 0]];
    effects.push({ kind: "slot", reels, crit, t: 0, life: 66 });
    setTimeout(() => {
      say(crit ? "かいしんの いちげき！！" : "こうげき！ たおした！");
      flipWani("excellent");
      if (a) { a.dying = true; a.flipHit = { t: 0, life: 34 }; }
      spawnBurst(x, GROUND_Y - 40, crit ? "#ffd447" : "#ffffff");
      spawnDrop(x, GROUND_Y - 30);
      scrollTarget += 80;
    }, 1100);
  }

  function playStarted(targetKey) {
    const a = actors.find((x) => x.key === targetKey);
    say("たたかいを いどんだ！");
    if (REDUCED) return;
    flipWani("happy");
    if (a) a.flipHit = { t: 0, life: 34 };
    effects.push({ kind: "potbreak", x: WANI_X + 80, y: GROUND_Y, t: 0, life: 40 });
    effects.push({ kind: "drop", sprite: "herb", x: WANI_X + 86, y: GROUND_Y - 10, vy: -2.4, t: 0, life: 46 });
  }

  function onTaskEvent(result) {
    const key = result.task?.item_id;
    if (result.event === "done") playKill(key);
    else if (result.event === "started") playStarted(key);
    else if (result.event === "undone") say("たおしたはずの敵が よみがえった…！");
    else say("じんけいを たてなおした。");
  }

  function onTaskAdded() {
    say("あたらしい モンスターのけはいがする…！");
  }

  // ---- 描画 ----
  function drawScene() {
    const sleeping = state?.mood.sleeping;
    const sky = ctx.createLinearGradient(0, 0, 0, CH);
    if (sleeping) { sky.addColorStop(0, "#101a33"); sky.addColorStop(1, "#26324f"); }
    else { sky.addColorStop(0, "#8fd4ff"); sky.addColorStop(1, "#d8f2c9"); }
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, CW, CH);

    if (sleeping) {
      ctx.fillStyle = "#f4f0d8";
      for (let i = 0; i < 34; i++) {
        ctx.globalAlpha = 0.4 + ((i + (t >> 4)) % 3) * 0.3;
        ctx.fillRect(hashStr(i + "s") % CW, hashStr(i + "y") % 100, 2, 2);
      }
      ctx.globalAlpha = 1;
      ctx.beginPath(); ctx.arc(560, 44, 18, 0, Math.PI * 2); ctx.fill();
    } else {
      ctx.fillStyle = "#ffe08a";
      ctx.beginPath(); ctx.arc(560, 42, 17, 0, Math.PI * 2); ctx.fill();
    }

    // 遠景の山(書き割り。パララックス0.25x)
    ctx.fillStyle = sleeping ? "#1d2c45" : "#a5cf8d";
    const far = -((scrollX * 0.25) % 200);
    for (let x = far - 200; x < CW + 200; x += 200) {
      ctx.beginPath();
      ctx.moveTo(x, 150);
      ctx.quadraticCurveTo(x + 50, 82, x + 100, 150);
      ctx.quadraticCurveTo(x + 150, 100, x + 200, 150);
      ctx.fill();
    }

    // 草原
    ctx.fillStyle = sleeping ? "#20372a" : "#63b466";
    ctx.fillRect(0, 150, CW, CH - 150);

    // 道端のツボ(書き割り装飾)
    const deco = -(scrollX % 240);
    for (let x = deco - 240; x < CW + 240; x += 240) {
      const broken = (x + 150) < WANI_X;
      const potImg = objSheet(broken ? "pot_broken" : "pot");
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(potImg, x + 150, GROUND_Y - potImg.height * 2 + 6, potImg.width * 2, potImg.height * 2);
    }

    // 手前のステージ床(アーケード筐体の台。パペットの棒がここに刺さっている)
    const stage_h = CH - GROUND_Y;
    ctx.fillStyle = sleeping ? "#241a10" : "#7a5a38";
    ctx.fillRect(0, GROUND_Y, CW, stage_h);
    ctx.fillStyle = sleeping ? "#38291a" : "#96744c";
    ctx.fillRect(0, GROUND_Y, CW, 5);
  }

  // パペット共通描画: 棒+紙人形。rock=ゆれ角、flipX=横反転スケール、sink=引っ込み量
  function drawPuppet(img, cx, footY, w, h, { rock = 0, flipX = 1, sink = 0, pixel = false }) {
    const topY = footY + sink;
    // 棒
    ctx.fillStyle = "#5d4426";
    ctx.fillRect(cx - 3, Math.min(topY - 4, CH), 6, CH - topY + 6);
    ctx.fillStyle = "#8a6a42";
    ctx.fillRect(cx - 1, Math.min(topY - 4, CH), 2, CH - topY + 6);
    // 紙人形(足元を支点に揺れ・反転)
    ctx.save();
    ctx.translate(cx, topY);
    ctx.rotate(rock);
    ctx.scale(flipX, 1);
    ctx.imageSmoothingEnabled = !pixel;
    ctx.drawImage(img, -w / 2, -h, w, h);
    // 紙が薄くなった瞬間の縁
    if (Math.abs(flipX) < 0.25) {
      ctx.fillStyle = "rgba(255,255,255,.85)";
      ctx.fillRect(-2, -h, 4, h);
    }
    ctx.restore();
    ctx.imageSmoothingEnabled = false;
  }

  function drawWani() {
    const sleeping = state?.mood.sleeping;
    let face = sleeping ? "sleeping" : (state?.mood.level || "normal");
    if (face === "happy") face = "normal";
    let flipX = 1;
    if (waniFx) {
      waniFx.t++;
      const p = waniFx.t / waniFx.life;
      flipX = Math.cos(p * Math.PI * 2);           // 1回転(パタッ)
      if (p >= 0.25 && p <= 0.75) face = waniFx.toFace; // 裏面は別の表情
      if (waniFx.t >= waniFx.life) {
        if (Date.now() < waniFx.until) { waniFx.t = waniFx.life; flipX = 1; face = waniFx.toFace; }
        else waniFx = null;
      }
    }
    const rock = REDUCED ? 0 : Math.sin(t / 16) * 0.045;
    const img = waniCutout(face);
    const scale = 0.78;
    drawPuppet(img, WANI_X, GROUND_Y, WANI_W * scale * (img === customWani ? (img.width / img.height) * (WANI_H / WANI_W) : 1), WANI_H * scale, { rock, flipX });

    if (sleeping && !REDUCED) {
      const fx = WANI_X + 90, fy = GROUND_Y - 2;
      ctx.fillStyle = "#6b4a2b";
      ctx.fillRect(fx - 9, fy - 4, 18, 4);
      const flame = 5 + Math.sin(t / 5) * 2;
      ctx.fillStyle = "#ff9a3d";
      ctx.beginPath();
      ctx.moveTo(fx - 6, fy - 4);
      ctx.quadraticCurveTo(fx, fy - 16 - flame, fx + 6, fy - 4);
      ctx.fill();
    }
  }

  function drawActors() {
    for (let i = 0; i < actors.length; i++) {
      const a = actors[i];
      const target = BATTLE_X + i * ENEMY_GAP;
      a.x += (target - a.x) * (REDUCED ? 1 : 0.1);
      if (a.dying) {
        a.sink = (a.sink || 0) + 5;   // 討伐: 棒ごと下に引っ込む
        if (a.sink > 130) { a.gone = true; continue; }
      }
      if (a.x > CW + 30) continue;

      let flipX = 1;
      if (a.flipHit) {
        a.flipHit.t++;
        flipX = Math.cos((a.flipHit.t / a.flipHit.life) * Math.PI * 2);
        if (a.flipHit.t >= a.flipHit.life) a.flipHit = null;
      }
      const img = objSheet(a.type, ((t + a.seed) / 16) | 0);
      const scale = (i === 0 ? 3.4 : 2.8) * (a.kind === "event" ? 1.1 : 1);
      const rock = REDUCED ? 0 : Math.sin((t + a.seed) / 13) * 0.07;
      const w = img.width * scale, h = img.height * scale;
      drawPuppet(img, a.x, GROUND_Y, w, h, { rock, flipX, sink: a.sink || 0, pixel: true });
      a.hitbox = { x: a.x - w / 2, y: GROUND_Y - h, w, h };

      if (a.sink) continue;
      // HPバー(タスクのみ)
      if (a.kind === "task") {
        const st = statusOf(a.task);
        const hp = st === "review" ? 1 / 3 : st === "in progress" ? 2 / 3 : 1;
        ctx.fillStyle = "rgba(0,0,0,.45)";
        ctx.fillRect(a.x - 20, GROUND_Y - h - 12, 40, 6);
        ctx.fillStyle = hp > 0.5 ? "#e5484d" : "#ff9a3d";
        ctx.fillRect(a.x - 19, GROUND_Y - h - 11, 38 * hp, 4);
      } else {
        // 予定は時刻表示
        ctx.font = "bold 11px sans-serif";
        ctx.textAlign = "center";
        const tm = new Date(a.ev.start).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" });
        ctx.lineWidth = 3; ctx.strokeStyle = "rgba(0,0,0,.55)";
        ctx.strokeText(`⏰${tm}`, a.x, GROUND_Y - h - 14);
        ctx.fillStyle = "#ffd447";
        ctx.fillText(`⏰${tm}`, a.x, GROUND_Y - h - 14);
      }
      // 名前
      ctx.font = "11px sans-serif";
      ctx.textAlign = "center";
      const label = short(a.kind === "task" ? a.task.title : a.ev.title, i === 0 ? 16 : 9);
      ctx.lineWidth = 3; ctx.strokeStyle = "rgba(0,0,0,.55)";
      ctx.strokeText(label, a.x, GROUND_Y - h - 20);
      ctx.fillStyle = "#fff";
      ctx.fillText(label, a.x, GROUND_Y - h - 20);
    }
    const gone = actors.filter((a) => a.gone);
    if (gone.length) actors = actors.filter((a) => !a.gone);
    // 画面外の敵の数
    const offscreen = actors.filter((a) => BATTLE_X + actors.indexOf(a) * ENEMY_GAP > CW - 30).length;
    if (offscreen > 0) {
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "right";
      ctx.lineWidth = 3; ctx.strokeStyle = "rgba(0,0,0,.55)";
      ctx.strokeText(`→ あと${offscreen}体`, CW - 10, GROUND_Y - 8);
      ctx.fillStyle = "#fff";
      ctx.fillText(`→ あと${offscreen}体`, CW - 10, GROUND_Y - 8);
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
      } else if (e.kind === "potbreak") {
        const img = objSheet(e.t < 12 ? "pot" : "pot_broken");
        ctx.drawImage(img, e.x, e.y - img.height * 2 + 6, img.width * 2, img.height * 2);
      } else if (e.kind === "slot") {
        drawSlot(e);
      }
    }
  }

  function drawSlot(e) {
    const w = 170, h = 56;
    const x = CW / 2 - w / 2, y = 34;
    ctx.fillStyle = "rgba(8,8,16,.88)";
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.strokeRect(x + 2, y + 2, w - 4, h - 4);
    const symbols = ["coin", "herb", "slime"];
    for (let i = 0; i < 3; i++) {
      const stopAt = 16 + i * 14;
      const spinning = e.t < stopAt;
      const name = spinning ? symbols[(e.t + i) % 3] : e.reels[i];
      const img = objSheet(name);
      const cx = x + 32 + i * 53, cy = y + h / 2;
      const s = 26 / Math.max(img.width, img.height);
      if (spinning) ctx.globalAlpha = 0.7;
      ctx.drawImage(img, cx - (img.width * s) / 2, cy - (img.height * s) / 2,
        img.width * s, img.height * s);
      ctx.globalAlpha = 1;
    }
    if (e.crit && e.t > 46 && (e.t >> 2) % 2) {
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
    if (!state?.mood.sleeping) drawActors();
    drawEffects();
    if (Date.now() > msgUntil) $("adv-msg").textContent = defaultMsg();
    if (visible && !REDUCED) raf = requestAnimationFrame(frame);
  }

  canvas.addEventListener("click", (ev) => {
    const rect = canvas.getBoundingClientRect();
    const x = (ev.clientX - rect.left) * (CW / rect.width);
    const y = (ev.clientY - rect.top) * (CH / rect.height);
    for (const a of actors) {
      const hb = a.hitbox;
      if (hb && x >= hb.x - 8 && x <= hb.x + hb.w + 8 && y >= hb.y - 22 && y <= hb.y + hb.h + 8) {
        if (a.kind === "task") core.showTaskSheet(a.task);
        else core.showEventSheet(a.ev, () => {
          localStorage.setItem(a.key, "1");
          say("よていを こなした！えらい！");
          rebuildActors();
        });
        return;
      }
    }
    if (x < WANI_X + 60) say(defaultMsg());
  });

  // ---- 脇道(待ち/後回し/きょうのよてい) ----
  function renderSide() {
    const side = $("adv-side");
    side.replaceChildren();
    const waiting = state.tasks.filter((tk) => statusOf(tk) === "waiting");
    const wish = state.tasks.filter((tk) => statusOf(tk) === "wish list");
    const upcoming = upcomingEvents();
    const boxes = [
      ["📅 きょうのよてい ", upcoming.map((ev) => ({
        label: `${ev.all_day ? "終日" : new Date(ev.start).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" })} ${ev.title}`,
        onClick: null,
      }))],
      ["⛺ 待機 ", waiting.map((tk) => ({
        label: (tk.number ? `#${tk.number} ` : "") + short(tk.title, 22),
        onClick: () => core.showTaskSheet(tk),
      }))],
      ["🧰 後回し ", wish.map((tk) => ({
        label: (tk.number ? `#${tk.number} ` : "") + short(tk.title, 22),
        onClick: () => core.showTaskSheet(tk),
      }))],
    ];
    for (const [label, items] of boxes) {
      if (!items.length) continue;
      const details = document.createElement("details");
      details.className = "adv-side-box";
      const summary = document.createElement("summary");
      summary.textContent = `${label}${items.length}件`;
      details.appendChild(summary);
      for (const item of items) {
        const el = document.createElement(item.onClick ? "button" : "div");
        if (item.onClick) { el.type = "button"; el.onclick = item.onClick; }
        el.className = "adv-side-item";
        el.textContent = item.label;
        details.appendChild(el);
      }
      side.appendChild(details);
    }
  }

  return {
    update(s) {
      state = s;
      rebuildActors();
      renderSide();
      drawHud();
      if (REDUCED) { drawScene(); drawWani(); if (!state.mood.sleeping) drawActors(); }
      if (Date.now() > msgUntil) $("adv-msg").textContent = defaultMsg();
    },
    show() {
      visible = true;
      if (!REDUCED) raf = requestAnimationFrame(frame);
      else if (state) { drawScene(); drawWani(); if (!state.mood.sleeping) drawActors(); }
    },
    hide() {
      visible = false;
      cancelAnimationFrame(raf);
    },
    onTaskEvent,
    onTaskAdded,
  };
}
