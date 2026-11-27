// The game screen. It only DRAWS the village and passes on what the player does.
// Every fact (gold, bag, quests, the locked gate, what a character answers) comes from the Python side (run_game.py),
// exactly like in the terminal version. Nothing in this file can change the game by itself.

const $ = id => document.getElementById(id);
const canvas = $('map'), mapCtx = canvas.getContext('2d');
let ctx = mapCtx;  // what the drawing helpers draw on: the map, or for a moment the dialogue box's portrait
const W = canvas.width, H = canvas.height;

async function api(path, body) {
  const options = body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)};
  return (await fetch(path, options)).json();
}

// ───────────────────────── the map ─────────────────────────
const WALL_Y = 250;   // the village wall runs across the map; north of it are the woods and the mine
const ZONES = [       // which place of world.json you are standing in (anywhere else is the Village Square)
  {id: 'whispering_woods', x: 0, y: 0, w: 400, h: WALL_Y},
  {id: 'old_mine', x: 600, y: 0, w: 360, h: WALL_Y},
  {id: 'north_gate', x: 400, y: 0, w: 200, h: 360},
  {id: 'market', x: 0, y: WALL_Y, w: 400, h: H - WALL_Y},
];
const SPAWN = {village_square: [640, 545], market: [250, 530], north_gate: [480, 325], whispering_woods: [250, 160], old_mine: [720, 150]};
const STAND = {bram: [175, 426], roderic: [548, 312], mira: [775, 440], miku: [585, 440]};  // where each character stands
const HOUSES = [[790, 300, 130, 70], [30, 300, 120, 66], [820, 525, 110, 66]];
const SOLID = [       // [x, y, width, height]: things you cannot walk through
  [0, WALL_Y, 448, 26], [512, WALL_Y, 448, 26],  // the wall, with the North Gate between
  [596, 0, 8, 110], [596, 190, 8, 60],            // the fence around the mine, with its gate between
  [108, 432, 134, 30],                            // Bram's counter
  [646, 448, 68, 46],                             // the fountain
  [830, 20, 110, 80],                             // the rock of the mine
  ...HOUSES,
];
const TREES = [[40, 60], [95, 150], [150, 50], [60, 215], [215, 95], [180, 215], [300, 45], [340, 110], [130, 110], [370, 215], [270, 215],
               [940, 440], [580, 590], [40, 590], [330, 590]];
const LOOKS = {
  player: {body: '#3f7d4f', hair: '#5a3b22'},
  bram: {body: '#c9793a', hair: '#7a5230', hat: true},
  roderic: {body: '#5c6f91', hair: '#3a3a3a', helmet: true},
  mira: {body: '#8b5fa8', hair: '#f2f2f2', bun: true},
  miku: {body: '#4a4f57', hair: '#3fd0c9', tails: true},
};
const SPEED = 190, TALK_DISTANCE = 78;

const zoneAt = (x, y) => (ZONES.find(z => x >= z.x && x < z.x + z.w && y >= z.y && y < z.y + z.h) || {id: 'village_square'}).id;
const blocked = (x, y) => x < 10 || x > W - 10 || y < 14 || y > H - 4 ||
  SOLID.some(([sx, sy, sw, sh]) => x + 8 > sx && x - 8 < sx + sw && y > sy && y - 8 < sy + sh);  // the player's feet are 16 × 8

// ───────────────────────── what the screen remembers ─────────────────────────
let world;                 // names of places, items, quests and characters (never changes)
let S;                     // the game state from the server: {game, next, marks, moods, history, has_key}
const player = {x: 0, y: 0, moving: false};
const keys = new Set();
let talkingTo = null;      // the character whose dialogue box is open
let busy = false;          // waiting for the server: the player stands still
let skipType = false;      // a key or a click shows the rest of the line being typed at once
let refusedUntil = 0;      // after the game refuses a move, do not ask again for a moment
const happened = [];       // lines for "What happened" in the side panel
const PLACE_SPOT = {village_square: [680, 540], market: [175, 500], north_gate: [480, 330], whispering_woods: [200, 150], old_mine: [780, 150]};
const STILL = matchMedia('(prefers-reduced-motion: reduce)').matches;

const has = item => S.game.inventory.includes(item);
const sheetOpen = () => !$('intro').hidden || !$('ending').hidden;
const el = (tag, cls, text) => Object.assign(document.createElement(tag), cls ? {className: cls} : {}, text !== undefined ? {textContent: text} : {});

function setState(data) {
  const wasDone = S ? S.next.done : null;
  S = {game: data.game, next: data.next, marks: data.marks, moods: data.moods, history: data.history, has_key: data.has_key};
  renderSide();
  if (S.next.done && wasDone === false) showEnding();  // only the moment the last task is done, not on every load
}

function note(message) {
  happened.push(message);
  $('toast').textContent = message;
  $('toast').hidden = false;
  clearTimeout(note.timer);
  note.timer = setTimeout(() => { $('toast').hidden = true; }, 4000);
  renderSide();
}

// ───────────────────────── walking and searching ─────────────────────────
function update(dt) {
  player.moving = false;
  if (talkingTo || busy || sheetOpen()) return;
  const held = (...names) => names.some(k => keys.has(k));
  const dx = held('ArrowRight', 'd') - held('ArrowLeft', 'a'), dy = held('ArrowDown', 's') - held('ArrowUp', 'w');
  if (!dx && !dy) return;
  player.moving = true;
  const step = SPEED * dt / Math.hypot(dx, dy);
  let x = player.x, y = player.y;
  if (!blocked(x + dx * step, y)) x += dx * step;
  if (!blocked(x, y + dy * step)) y += dy * step;
  const zone = zoneAt(x, y);
  if (zone === S.game.place) { player.x = x; player.y = y; }
  else if (performance.now() > refusedUntil) enter(zone, x, y);
}

async function enter(zone, x, y) {  // stepping into another place: the game decides whether you may
  busy = true;
  const result = await api('/api/go', {place: zone});
  busy = false;
  setState(result);
  if (result.ok) { player.x = x; player.y = y; }
  else { refusedUntil = performance.now() + 1500; note(result.message); }
}

async function search() {
  if (busy || talkingTo) return;
  busy = true;
  const result = await api('/api/search', {});
  busy = false;
  setState(result);
  note(result.message);
}

const nearby = () => Object.keys(STAND).find(id => world.npcs[id].place === S.game.place &&
  Math.hypot(STAND[id][0] - player.x, STAND[id][1] - player.y) < TALK_DISTANCE);

// ───────────────────────── talking ─────────────────────────
function line(kind, text) {
  const p = document.createElement('p');
  p.className = kind;
  p.textContent = text;
  $('talk-log').append(p);
  $('talk-log').scrollTop = 1e6;
  return p;
}

function sayLine(name, say) {  // names the character put in [brackets] are shown in blue
  const p = line('npc', name + ': ');
  say.split(/\[([^\]]+)\]/).forEach((part, i) => p.append(i % 2 ? el('b', 'thing', part) : part));
}

function typeLine(name, say) {  // the same, letter by letter (quick; a key or a click shows it all)
  const p = line('npc', name + ': ');
  const parts = say.split(/\[([^\]]+)\]/).map((text, i) => {
    const node = i % 2 ? el('b', 'thing', '') : document.createTextNode('');
    p.append(node);
    return [node, text];
  });
  const total = parts.reduce((n, [, text]) => n + text.length, 0), ms = STILL ? 0 : Math.min(1100, total * 16), start = performance.now();
  skipType = false;
  return new Promise(done => {
    const step = now => {
      const end = skipType || now - start >= ms;
      let n = end ? total : Math.ceil(total * (now - start) / ms);
      for (const [node, text] of parts) { const k = Math.min(text.length, n); node.textContent = text.slice(0, k); n -= k; }
      $('talk-log').scrollTop = 1e6;
      if (end) done(); else requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

function portrait(id) {  // the character's head, drawn by the same code as on the map, twice as big
  const face = $('talk-face'), c = face.getContext('2d');
  c.clearRect(0, 0, face.width, face.height);
  c.save(); c.translate(28, 100); c.scale(1.8, 1.8);
  ctx = c; person(0, 0, LOOKS[id]); ctx = mapCtx;
  c.restore();
}

function ideas(id) {  // a few things to say, from the character sheet; typing anything else works just as well
  $('talk-ideas').replaceChildren(...world.npcs[id].try.map(text => {
    const b = el('button', '', text);
    b.type = 'button';
    b.onclick = () => { if (busy) return; $('talk-input').value = text; $('talk-form').requestSubmit(); };
    return b;
  }));
}

function openTalk(id) {
  talkingTo = id;
  keys.clear();
  $('talk-name').textContent = world.npcs[id].name;
  $('talk-role').textContent = world.npcs[id].role;
  $('talk-log').replaceChildren();
  for (const h of S.history[id]) { line('you', 'You: ' + h.player); sayLine(world.npcs[id].name, h.npc); }
  ideas(id);
  portrait(id);
  $('talk').hidden = false;
  $('talk-input').focus();
  renderSide();
}

function closeTalk() {
  if (busy) return;
  talkingTo = null;
  $('talk').hidden = true;
  renderSide();
}

$('talk-form').onsubmit = async event => {
  event.preventDefault();
  const input = $('talk-input'), text = input.value.trim(), id = talkingTo, name = world.npcs[id].name;
  if (!text || busy) return;
  input.value = '';
  line('you', 'You: ' + text);
  const waiting = line('meta thinking', name + ' is thinking');
  busy = input.disabled = true;
  try {
    const result = await api('/api/talk', {npc: id, text});
    const reply = result.reply;
    waiting.remove();
    await typeLine(name, reply.say);
    for (const e of reply.events) { line('event', '★ ' + e); note(e); }  // the stars are things the GAME did
    line('meta', reply.source === 'model' ? `AI model, ${reply.latency_ms} ms`
      : reply.source === 'fallback' ? `ready-made line: ${reply.problems.at(-1) || 'no answer'}`
      : 'safety filter: this was not sent to the AI');
    setState(result);
  } catch (error) {
    waiting.className = 'meta';
    waiting.textContent = 'The game is not answering. Is the terminal window with run_game.py still open?';
  }
  busy = input.disabled = false;
  input.focus();
};
$('talk-log').onclick = () => { skipType = true; };

// ───────────────────────── the side panel ─────────────────────────
function fill(id, lines, empty) {
  $(id).replaceChildren(...(lines.length ? lines : [empty]).map(text => {
    const li = document.createElement('li');
    li.append(...[].concat(text));
    return li;
  }));
}

function renderSide() {
  if (!world || !S) return;
  const g = S.game, place = world.places[g.place];
  $('no-key').hidden = S.has_key;
  $('place').replaceChildren('You are at the ', el('b', '', place.name), g.known_dangers.includes(g.place) ? ` (${place.danger})` : '', '.');
  $('goal-text').textContent = S.next.text;
  $('goal').classList.toggle('done', S.next.done);
  $('gold').textContent = g.gold;
  fill('bag', g.inventory.map(i => [el('b', '', world.items[i].name), el('small', '', world.items[i].about)]), 'empty');
  fill('quests', Object.entries(g.quests).map(([id, status]) => [
    el('span', 'chip ' + status, status.replace('_', ' ')), el('b', '', world.quests[id].name),
    el('small', '', status === 'active' ? world.quests[id].summary : status === 'done' ? `Reward paid: ${world.quests[id].reward} gold.` : '')]), 'none');
  fill('events', happened.slice(-5), 'Nothing yet.');
  $('mood-box').hidden = !talkingTo;
  if (talkingTo) {
    $('mood-title').textContent = world.npcs[talkingTo].name + "'s mood";
    $('mood').replaceChildren(...Object.entries(S.moods[talkingTo]).map(([name, value]) => {
      const row = el('div', 'bar'), bar = el('i'), fillBar = el('b');
      fillBar.style.width = `${Number(value) * 10}%`;
      bar.append(fillBar);
      row.append(el('span', '', name), bar, el('span', '', String(Number(value))));
      return row;
    }));
  }
}

function showEnding() {
  $('ending-gold').textContent = `You finish with ${S.game.gold} gold.`;
  $('ending').hidden = false;
  $('ending-ok').focus();
}

function closeSheet() {
  $('intro').hidden = $('ending').hidden = true;
  canvas.focus?.();
}

// ───────────────────────── keys and buttons ─────────────────────────
const keyName = e => e.key.length === 1 ? e.key.toLowerCase() : e.key;

addEventListener('keydown', e => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const key = keyName(e);
  if (sheetOpen()) { if (key === 'Enter' || key === ' ' || key === 'Escape' || key === 'e') { e.preventDefault(); closeSheet(); } return; }
  if (talkingTo) { if (busy) skipType = true; else if (key === 'Escape') closeTalk(); return; }
  if (key.startsWith('Arrow') || key === ' ') e.preventDefault();  // do not scroll the page
  if (key === 'e' && nearby()) { e.preventDefault(); openTalk(nearby()); }
  else if (key === 'f') search();
  else keys.add(key);
});
addEventListener('keyup', e => keys.delete(keyName(e)));
addEventListener('blur', () => keys.clear());
$('talk-close').onclick = closeTalk;
$('intro-go').onclick = closeSheet;
$('ending-ok').onclick = closeSheet;
$('search').onclick = e => { e.target.blur(); search(); };
$('reset').onclick = async e => {
  e.target.blur();
  if (busy || !confirm('Start a new game? Your gold, bag and quests are reset, and the characters forget you.')) return;
  closeTalk();
  happened.length = 0;
  setState(await api('/api/reset', {}));
  [player.x, player.y] = SPAWN[S.game.place];
  $('intro').hidden = false;
};

// ───────────────────────── drawing ─────────────────────────
const rect = (color, x, y, w, h) => { ctx.fillStyle = color; ctx.fillRect(x, y, w, h); };
const oval = (color, x, y, rx, ry = rx) => { ctx.fillStyle = color; ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, 7); ctx.fill(); };
const pill = (color, x, y, w, h, r) => { ctx.fillStyle = color; ctx.beginPath(); ctx.roundRect(x, y, w, h, r); ctx.fill(); };

function label(text, x, y, size = 13, color = '#fff') {
  ctx.font = `600 ${size}px system-ui, sans-serif`;
  ctx.textAlign = 'center';
  ctx.lineWidth = 3;
  ctx.strokeStyle = 'rgba(20, 24, 36, .8)';
  ctx.strokeText(text, x, y);
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
}

function road(...points) {
  ctx.strokeStyle = '#d8bd85'; ctx.lineWidth = 46; ctx.lineCap = ctx.lineJoin = 'round';
  ctx.beginPath();
  points.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  ctx.stroke();
}

function tree(x, y) {
  const leaves = y < WALL_Y ? '#2c6a3a' : '#3f9a4b';
  oval('rgba(0,0,0,.2)', x, y, 16, 5);
  rect('#6b4a2b', x - 4, y - 16, 8, 16);
  oval(leaves, x - 11, y - 26, 14); oval(leaves, x + 11, y - 26, 14); oval(leaves, x, y - 38, 18);
}

function house(x, y, w, h) {
  rect('#ead7ae', x, y, w, h);
  ctx.fillStyle = '#b5523b';
  ctx.beginPath(); ctx.moveTo(x - 10, y + 4); ctx.lineTo(x + w / 2, y - 38); ctx.lineTo(x + w + 10, y + 4); ctx.fill();
  rect('#7a4a1e', x + w / 2 - 9, y + h - 30, 18, 30);
  rect('#8fd0ee', x + 14, y + 20, 18, 16); rect('#8fd0ee', x + w - 32, y + 20, 18, 16);
}

function person(x, y, look, walk = 0) {  // x, y is the spot between the feet
  const bob = walk ? Math.round(Math.sin(walk * 2)) : 0, swing = walk ? Math.sin(walk) * 3 : 0;
  oval('rgba(0,0,0,.25)', x, y, 12, 5);
  rect('#4a3b2a', x - 7, y - 10, 5, 10 + swing); rect('#4a3b2a', x + 2, y - 10, 5, 10 - swing);
  if (look.tails) { pill(look.hair, x - 17, y - 44 + bob, 7, 30, 4); pill(look.hair, x + 10, y - 44 + bob, 7, 30, 4); }
  pill(look.body, x - 10, y - 29 + bob, 20, 21, 5);
  oval('#f3cfa8', x, y - 37 + bob, 9);
  ctx.fillStyle = look.hair; ctx.beginPath(); ctx.arc(x, y - 39 + bob, 9.5, Math.PI, 0); ctx.fill();
  rect('#2b2b2b', x - 4, y - 37 + bob, 2, 3); rect('#2b2b2b', x + 2, y - 37 + bob, 2, 3);
  if (look.hat) { oval('#e2c26b', x, y - 43, 14, 4); pill('#e2c26b', x - 7, y - 51, 14, 9, 4); rect('#f4efe2', x - 6, y - 22, 12, 13); }
  if (look.helmet) {
    ctx.fillStyle = '#aeb4bf'; ctx.beginPath(); ctx.arc(x, y - 39, 10.5, Math.PI, 0); ctx.fill();
    rect('#c0392b', x - 2, y - 55, 4, 7);
    rect('#6b4a2b', x + 14, y - 56, 3, 56); rect('#d5d9e0', x + 12, y - 62, 7, 8);  // his spear
  }
  if (look.bun) { oval(look.hair, x, y - 50, 5); rect('#6b4a2b', x - 16, y - 40, 3, 40); }  // and her walking stick
  if (look.tails) rect('#3fd0c9', x - 2, y - 28 + bob, 4, 10);
  if (look === LOOKS.player && has('torch')) { rect('#6b4a2b', x + 11, y - 30 + bob, 3, 14); oval('#ffb347', x + 12.5, y - 34 + bob, 4, 6); }
}

function draw(t) {
  const g = S.game, inWoods = g.place === 'whispering_woods';
  // the ground
  rect('#74b45c', 0, 0, W, H);
  rect('#4f8a4a', 0, 0, 400, WALL_Y);
  for (let i = 0; i < 160; i++) rect('rgba(0,0,0,.07)', (i * 211) % W, (i * 127 + (i * i * 31) % 90) % H, 3, 7);  // tufts of grass
  rect('#a39d93', 604, 0, 356, WALL_Y);
  road([480, 150], [480, 500]); road([200, 500], [760, 500]); road([230, 150], [870, 150]);
  // the mine: rock, entrance and the fence with its gate
  pill('#6f6a63', 825, 12, 120, 92, 26); pill('#1c1a18', 862, 44, 46, 60, [22, 22, 0, 0]);
  rect('#7a4a1e', 858, 40, 54, 6); rect('#7a4a1e', 858, 40, 6, 64); rect('#7a4a1e', 906, 40, 6, 64);
  for (let y = 4; y < WALL_Y; y += 18) if (y < 104 || y > 190) rect('#7a4a1e', 597, y, 6, 14);
  rect('#5b3d1e', 599, 0, 2, 110); rect('#5b3d1e', 599, 190, 2, 60);
  if (!has('gate_pass')) {  // the gate stays shut until the GAME says you carry the Gate Pass
    for (let y = 112; y < 190; y += 13) rect('#3d3d45', 597, y, 6, 10);
    rect('#3d3d45', 599, 110, 2, 80); pill('#d9a514', 593, 143, 14, 14, 3);
  }
  // the village wall and the North Gate
  rect('#8d8f98', 0, WALL_Y, 448, 26); rect('#8d8f98', 512, WALL_Y, 448, 26);
  for (let x = 0; x < W; x += 24) if (x < 432 || x >= 528) rect('#74767f', x + 4, WALL_Y, 12, 7);
  rect('#6f717a', 430, WALL_Y - 22, 20, 52); rect('#6f717a', 510, WALL_Y - 22, 20, 52);
  // the next step (worked out by the game, not the AI): a ring on the ground at a place; for a character, an arrow over
  // their head further down (Bram stands behind his counter, which would hide a ring)
  const pulse = STILL ? 0.5 : (Math.sin(t * 4) + 1) / 2;
  const spot = S.next.done || talkingTo || S.next.npc ? null : PLACE_SPOT[S.next.place];
  if (spot) {
    ctx.strokeStyle = `rgba(255, 216, 102, ${0.55 + 0.4 * pulse})`;
    ctx.lineWidth = 3;
    ctx.beginPath(); ctx.ellipse(spot[0], spot[1], 20 + 6 * pulse, 8 + 2 * pulse, 0, 0, 7); ctx.stroke();
  }

  // everything that stands on the ground, drawn from the back to the front so you can walk behind things
  const things = [
    ...TREES.map(([x, y]) => [y, () => tree(x, y)]),
    ...HOUSES.map(([x, y, w, h]) => [y + h, () => house(x, y, w, h)]),
    [400, () => {  // the roof of Bram's stall
      rect('#6b4a2b', 112, 362, 4, 72); rect('#6b4a2b', 234, 362, 4, 72);
      for (let i = 0; i < 7; i++) rect(i % 2 ? '#f4efe2' : '#c0392b', 108 + i * 19.2, 340, 19.2, 24);
    }],
    [462, () => {  // his counter, with a torch, a rope, a potion and a charm on it
      rect('#a8743c', 108, 432, 134, 30); rect('#c79a5e', 108, 432, 134, 8);
      rect('#6b4a2b', 124, 424, 3, 12); oval('#ffb347', 125.5, 421, 3, 5); oval('#c9a36a', 158, 430, 7, 5);
      pill('#e0527a', 186, 420, 9, 14, 3); oval('#8fd0ee', 220, 428, 5);
    }],
    [494, () => {  // the fountain
      oval('#b9bcc4', 680, 470, 36, 26); oval('#6ec3e8', 680, 470, 28, 19); oval('#b9bcc4', 680, 466, 6, 5);
      oval('rgba(255,255,255,.7)', 680, 458 - 3 * Math.abs(Math.sin(t * 3)), 3, 5);
    }],
    ...Object.entries(STAND).map(([id, [x, y]]) => [y, () => person(x, y, LOOKS[id])]),
    [player.y, () => person(player.x, player.y, LOOKS.player, player.moving ? t * 12 : 0)],
  ];
  things.sort((a, b) => a[0] - b[0]).forEach(([, paint]) => paint());

  // the woods are dark; a torch lights a circle around you
  ctx.save();
  ctx.beginPath(); ctx.rect(0, 0, 400, WALL_Y); ctx.clip();
  ctx.fillStyle = 'rgba(8, 16, 36, .55)';
  ctx.beginPath(); ctx.rect(0, 0, 400, WALL_Y);
  if (inWoods && has('torch')) ctx.arc(player.x, player.y - 20, 85, 0, 7);
  ctx.fill('evenodd');
  ctx.restore();

  // names of the places (over the woods' darkness, so they stay readable); a danger shows once someone has warned you
  for (const [id, x, y] of [['whispering_woods', 200, 240], ['old_mine', 780, 240], ['north_gate', 480, 302], ['market', 175, 592], ['village_square', 680, 592]]) {
    const known = g.known_dangers.includes(id), danger = world.places[id].danger;
    label(world.places[id].name + (known ? ` · ${danger}` : ''), x, y, 14,
      known && danger !== 'safe' ? (danger === 'deadly' ? '#ff9a8a' : '#ffd27a') : id === g.place ? '#ffe9a8' : 'rgba(255,255,255,.8)');
  }

  // name tags, the signs over heads ("!" a task for you, "?" you carry what their task asks for), and the hint to talk
  const close = talkingTo ? null : nearby();
  for (const [id, [x, y]] of Object.entries(STAND)) {
    label(world.npcs[id].name, x, y - 60);
    const mark = S.marks[id];
    if (mark && id !== close) {
      const bob = STILL ? 0 : Math.sin(t * 3 + x) * 2;
      oval('rgba(42, 33, 24, .9)', x, y - 84 + bob, 11);
      label(mark, x, y - 78 + bob, 17, mark === '!' ? '#ffd866' : '#8fd0ee');
    }
    if (id === close) { pill('rgba(42, 33, 24, .9)', x - 34, y - 96, 68, 22, 6); label('E  talk', x, y - 80, 13, '#ffe9a8'); }
    if (id === S.next.npc && !S.next.done && !talkingTo && id !== close) {  // the next step is to talk to them
      const top = y - (S.marks[id] ? 104 : 80) - 6 * pulse;
      ctx.fillStyle = '#ffd866'; ctx.strokeStyle = 'rgba(42, 33, 24, .9)'; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.moveTo(x - 9, top - 12); ctx.lineTo(x + 9, top - 12); ctx.lineTo(x, top); ctx.closePath(); ctx.stroke(); ctx.fill();
    }
  }
}

// ───────────────────────── start ─────────────────────────
let last = 0;
function frame(now) {
  update(Math.min(0.05, (now - last) / 1000));
  last = now;
  draw(now / 1000);
  requestAnimationFrame(frame);
}

(async () => {
  world = await api('/api/world');
  setState(await api('/api/state'));
  [player.x, player.y] = SPAWN[S.game.place];
  $('intro-go').textContent = Object.values(S.history).some(h => h.length) ? 'Continue' : 'Play';
  $('intro-go').focus();
  requestAnimationFrame(frame);
})();
