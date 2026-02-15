const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
if (!ctx) throw new Error('Canvas 2D not supported in this browser');
const mineralsEl = document.getElementById('minerals');
const supplyEl = document.getElementById('supply');
const enemyCountEl = document.getElementById('enemyCount');
const selectionTitleEl = document.getElementById('selectionTitle');
const actionsEl = document.getElementById('actions');
const statusBannerEl = document.getElementById('statusBanner');

function uid() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `id-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}


const WORLD = { width: 2400, height: 1600 };
const COSTS = { worker: 50, soldier: 100, barracks: 180, supply: 120 };
const NAMES = {
  worker: 'Рабочий',
  soldier: 'Солдат',
  bug: 'Жук',
  command: 'Командный центр',
  barracks: 'Казарма',
  supply: 'Склад',
  hive: 'Улей',
  spawner: 'Гнездо',
};

const state = {
  camera: { x: 0, y: 0, drag: false, moved: 0, lastX: 0, lastY: 0 },
  selected: null,
  minerals: 300,
  supplyUsed: 0,
  supplyMax: 8,
  tick: 0,
  playerUnits: [],
  enemyUnits: [],
  structures: [],
  resources: [],
  shots: [],
  particles: [],
  decor: [],
  gameOver: false,
  bannerTimer: 0,
};

function addEntity(arr, entity) {
  arr.push(entity);
  return entity;
}

function spawnInitial() {
  addEntity(state.structures, makeStructure('command', 260, 260, true));
  addEntity(state.structures, makeStructure('supply', 460, 300, true));
  for (let i = 0; i < 4; i++) addEntity(state.playerUnits, makeUnit('worker', 300 + i * 24, 358, true));

  addEntity(state.structures, makeStructure('hive', 1900, 1240, false));
  addEntity(state.structures, makeStructure('spawner', 1730, 1210, false));
  addEntity(state.structures, makeStructure('spawner', 1880, 1110, false));
  for (let i = 0; i < 6; i++) addEntity(state.enemyUnits, makeUnit('bug', 1810 + Math.random() * 110, 1270 + Math.random() * 100, false));

  for (let i = 0; i < 10; i++) {
    addEntity(state.resources, {
      id: uid(),
      entity: 'resource',
      x: 520 + (i % 5) * 34,
      y: 190 + Math.floor(i / 5) * 34,
      amount: 500,
      radius: 13,
      type: 'minerals',
    });
  }

  for (let i = 0; i < 140; i++) {
    state.decor.push({
      x: Math.random() * WORLD.width,
      y: Math.random() * WORLD.height,
      size: 1 + Math.random() * 3,
      tone: Math.random() > 0.5 ? 'grass' : 'rock',
    });
  }
}

function makeUnit(type, x, y, player) {
  const data = {
    worker: { hp: 40, speed: 1.22, atk: 5, range: 18, color: '#79ccff', supply: 1 },
    soldier: { hp: 70, speed: 1.05, atk: 11, range: 25, color: '#52ebbb', supply: 2 },
    bug: { hp: 55, speed: 1.02, atk: 8, range: 20, color: '#ff6b93', supply: 0 },
  }[type];

  if (player) state.supplyUsed += data.supply;

  return {
    id: uid(),
    entity: 'unit',
    type,
    x,
    y,
    hp: data.hp,
    maxHp: data.hp,
    speed: data.speed,
    atk: data.atk,
    range: data.range,
    color: data.color,
    heading: 0,
    target: null,
    moveTarget: null,
    gatherTarget: null,
    player,
  };
}

function makeStructure(type, x, y, player) {
  const data = {
    command: { hp: 500, w: 86, h: 86, color: '#76adff' },
    barracks: { hp: 320, w: 74, h: 74, color: '#75d5b5' },
    supply: { hp: 210, w: 60, h: 60, color: '#f0d37d' },
    hive: { hp: 520, w: 92, h: 92, color: '#d65e86' },
    spawner: { hp: 280, w: 66, h: 66, color: '#cb7b98' },
  }[type];

  return {
    id: uid(),
    entity: 'structure',
    type,
    x,
    y,
    hp: data.hp,
    maxHp: data.hp,
    w: data.w,
    h: data.h,
    color: data.color,
    player,
    rally: { x: x + 96, y: y + 32 },
  };
}

function resizeCanvas() {
  const topH = document.querySelector('.top-bar').offsetHeight;
  const panelH = document.querySelector('.panel').offsetHeight;
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight - topH - panelH;
}

function screenToWorld(x, y) {
  return { x: x + state.camera.x, y: y + state.camera.y };
}
function worldToScreen(x, y) {
  return { x: x - state.camera.x, y: y - state.camera.y };
}

function setSelection(entity) {
  state.selected = entity;
  renderActions();
}

function renderActions() {
  actionsEl.innerHTML = '';
  const s = state.selected;
  if (!s) {
    selectionTitleEl.textContent = 'Ничего не выбрано';
    return;
  }

  selectionTitleEl.textContent = `${s.player ? 'Союзник' : 'Враг'}: ${NAMES[s.type]} (${Math.ceil(s.hp)}/${s.maxHp})`;
  if (!s.player) return;

  if (s.entity === 'unit') {
    addAction('Стоп', () => {
      s.moveTarget = null;
      s.target = null;
      s.gatherTarget = null;
    });
  }

  if (s.entity === 'structure' && s.type === 'command') {
    addAction(`Рабочий (${COSTS.worker})`, () => trainFromStructure(s, 'worker'));
    addAction(`Склад (+8) (${COSTS.supply})`, () => buildNear(s, 'supply'));
    addAction(`Казарма (${COSTS.barracks})`, () => buildNear(s, 'barracks'));
  }

  if (s.entity === 'structure' && s.type === 'barracks') {
    addAction(`Солдат (${COSTS.soldier})`, () => trainFromStructure(s, 'soldier'));
  }
}

function addAction(label, fn) {
  const btn = document.createElement('button');
  btn.textContent = label;
  btn.addEventListener('click', fn);
  actionsEl.appendChild(btn);
}

function spend(cost) {
  if (state.minerals < cost) return false;
  state.minerals -= cost;
  return true;
}

function trainFromStructure(structure, type) {
  const supplyNeed = type === 'soldier' ? 2 : 1;
  if (state.supplyUsed + supplyNeed > state.supplyMax) return;
  if (!spend(COSTS[type])) return;

  const unit = makeUnit(type, structure.x + structure.w + 12, structure.y + structure.h / 2, true);
  unit.moveTarget = { ...structure.rally };
  state.playerUnits.push(unit);
  pulseRing(unit.x, unit.y, '#9de8ff');
  renderActions();
}

function buildNear(structure, type) {
  if (!spend(COSTS[type])) return;
  const offset = 90 + Math.random() * 30;
  const placed = makeStructure(type, structure.x + offset, structure.y + offset * 0.4, true);
  state.structures.push(placed);
  if (type === 'supply') state.supplyMax += 8;
  pulseRing(placed.x + placed.w / 2, placed.y + placed.h / 2, '#ffe08c');
  renderActions();
}

function handleTap(clientX, clientY) {
  const rect = canvas.getBoundingClientRect();
  const world = screenToWorld(clientX - rect.left, clientY - rect.top);

  const clickable = [...state.playerUnits, ...state.enemyUnits, ...state.structures];
  const found = clickable.find((e) => {
    if (e.entity === 'unit') return Math.hypot(world.x - e.x, world.y - e.y) < 16;
    return world.x >= e.x && world.x <= e.x + e.w && world.y >= e.y && world.y <= e.y + e.h;
  });

  if (found) return setSelection(found);

  if (state.selected && state.selected.player && state.selected.entity === 'unit') {
    const selected = state.selected;
    const targetEnemy = [...state.enemyUnits, ...state.structures.filter((s) => !s.player)].find((e) => {
      if (e.entity === 'unit') return Math.hypot(world.x - e.x, world.y - e.y) < 22;
      return world.x >= e.x && world.x <= e.x + e.w && world.y >= e.y && world.y <= e.y + e.h;
    });

    const targetMineral = state.resources.find((r) => Math.hypot(world.x - r.x, world.y - r.y) <= r.radius + 10);

    if (selected.type === 'worker' && targetMineral) {
      selected.gatherTarget = targetMineral;
      selected.moveTarget = { x: targetMineral.x, y: targetMineral.y };
      selected.target = null;
      pulseRing(targetMineral.x, targetMineral.y, '#7dd1ff');
      return;
    }

    selected.target = targetEnemy || null;
    selected.gatherTarget = null;
    selected.moveTarget = targetEnemy ? null : { x: world.x, y: world.y };

    if (targetEnemy) {
      pulseRing(world.x, world.y, '#ff8ba7');
    } else {
      pulseRing(world.x, world.y, '#9ee3ff');
    }
  } else {
    setSelection(null);
  }
}

function tickAI() {
  state.tick += 1;
  if (state.tick % 180 === 0) {
    const spawners = state.structures.filter((s) => !s.player && s.type === 'spawner');
    if (spawners.length) {
      const base = spawners[Math.floor(Math.random() * spawners.length)];
      const bug = makeUnit('bug', base.x + 20, base.y + 20, false);
      bug.moveTarget = { x: 300 + Math.random() * 220, y: 280 + Math.random() * 200 };
      state.enemyUnits.push(bug);
      burst(base.x + 25, base.y + 25, '#ff88aa');
    }
  }

  for (const enemy of state.enemyUnits) {
    const victims = [...state.playerUnits, ...state.structures.filter((s) => s.player)];
    const near = victims.find((v) => distance(enemy, v) < 170);
    if (near) {
      enemy.target = near;
      enemy.moveTarget = null;
    }
  }
}

function distance(a, b) {
  const bx = b.entity === 'structure' ? b.x + b.w / 2 : b.x;
  const by = b.entity === 'structure' ? b.y + b.h / 2 : b.y;
  return Math.hypot(a.x - bx, a.y - by);
}

function updateUnits(units) {
  for (const u of units) {
    if (u.gatherTarget && u.gatherTarget.amount > 0 && distance(u, u.gatherTarget) < 20 && state.tick % 24 === 0) {
      u.gatherTarget.amount -= 6;
      state.minerals += 6;
      burst(u.x, u.y, '#72ccff', 3);
    }

    if (u.target && u.target.hp > 0) {
      const d = distance(u, u.target);
      if (d <= u.range) {
        if (state.tick % 18 === 0) {
          u.target.hp -= u.atk;
          const t = targetPos(u.target);
          state.shots.push({
            x1: u.x,
            y1: u.y,
            x2: t.x,
            y2: t.y,
            life: 8,
            color: u.player ? '#99ebff' : '#ff7a9c',
          });
          burst(t.x, t.y, u.player ? '#9defff' : '#ff8aa8', 4);
        }
      } else {
        moveToward(u, targetPos(u.target));
      }
      continue;
    }

    if (u.moveTarget) {
      const d = Math.hypot(u.moveTarget.x - u.x, u.moveTarget.y - u.y);
      if (d < 2) {
        u.moveTarget = null;
      } else {
        moveToward(u, u.moveTarget);
      }
    }
  }
}

function moveToward(unit, pos) {
  const angle = Math.atan2(pos.y - unit.y, pos.x - unit.x);
  unit.heading = angle;
  unit.x += Math.cos(angle) * unit.speed;
  unit.y += Math.sin(angle) * unit.speed;
  unit.x = Math.max(10, Math.min(WORLD.width - 10, unit.x));
  unit.y = Math.max(10, Math.min(WORLD.height - 10, unit.y));
}

function targetPos(target) {
  return target.entity === 'structure' ? { x: target.x + target.w / 2, y: target.y + target.h / 2 } : { x: target.x, y: target.y };
}

function cleanupDead() {
  state.playerUnits = state.playerUnits.filter((u) => u.hp > 0);
  state.enemyUnits = state.enemyUnits.filter((u) => u.hp > 0);
  state.structures = state.structures.filter((s) => s.hp > 0);
  state.resources = state.resources.filter((r) => r.amount > 0);
  state.supplyUsed = state.playerUnits.reduce((sum, u) => sum + (u.type === 'soldier' ? 2 : u.type === 'worker' ? 1 : 0), 0);
  if (state.selected && state.selected.hp <= 0) setSelection(null);
}

function updateFx() {
  state.shots = state.shots.filter((s) => --s.life > 0);
  state.particles = state.particles.filter((p) => {
    p.life -= 1;
    p.x += p.vx;
    p.y += p.vy;
    p.vx *= 0.98;
    p.vy *= 0.98;
    return p.life > 0;
  });
}

function burst(x, y, color, count = 7) {
  for (let i = 0; i < count; i++) {
    const a = Math.random() * Math.PI * 2;
    const speed = 0.4 + Math.random() * 1.6;
    state.particles.push({ x, y, vx: Math.cos(a) * speed, vy: Math.sin(a) * speed, life: 14 + Math.random() * 12, color, size: 1 + Math.random() * 2 });
  }
}

function pulseRing(x, y, color) {
  for (let i = 0; i < 16; i++) {
    const a = (Math.PI * 2 * i) / 16;
    state.particles.push({ x: x + Math.cos(a) * 2, y: y + Math.sin(a) * 2, vx: Math.cos(a) * 0.9, vy: Math.sin(a) * 0.9, life: 10, color, size: 1.6 });
  }
}

function clampCamera() {
  state.camera.x = Math.max(0, Math.min(WORLD.width - canvas.width, state.camera.x));
  state.camera.y = Math.max(0, Math.min(WORLD.height - canvas.height, state.camera.y));
}

function renderTerrain() {
  const grad = ctx.createLinearGradient(0, -state.camera.y, 0, WORLD.height - state.camera.y);
  grad.addColorStop(0, '#224738');
  grad.addColorStop(1, '#163126');
  ctx.fillStyle = grad;
  ctx.fillRect(-state.camera.x, -state.camera.y, WORLD.width, WORLD.height);

  for (const d of state.decor) {
    const p = worldToScreen(d.x, d.y);
    ctx.fillStyle = d.tone === 'grass' ? 'rgba(105,150,95,0.20)' : 'rgba(90,105,120,0.18)';
    ctx.fillRect(p.x, p.y, d.size * 2.2, d.size * 2.2);
  }

  for (let y = 0; y < WORLD.height; y += 64) {
    ctx.strokeStyle = 'rgba(255,255,255,0.045)';
    ctx.beginPath();
    ctx.moveTo(-state.camera.x, y - state.camera.y);
    ctx.lineTo(WORLD.width - state.camera.x, y - state.camera.y);
    ctx.stroke();
  }

  for (let x = 0; x < WORLD.width; x += 64) {
    ctx.strokeStyle = 'rgba(0,0,0,0.18)';
    ctx.beginPath();
    ctx.moveTo(x - state.camera.x, -state.camera.y);
    ctx.lineTo(x - state.camera.x, WORLD.height - state.camera.y);
    ctx.stroke();
  }

  const enemyZone = worldToScreen(1640, 970);
  const danger = ctx.createRadialGradient(enemyZone.x + 340, enemyZone.y + 250, 40, enemyZone.x + 340, enemyZone.y + 250, 420);
  danger.addColorStop(0, 'rgba(170, 45, 82, 0.25)');
  danger.addColorStop(1, 'rgba(170, 45, 82, 0.03)');
  ctx.fillStyle = danger;
  ctx.fillRect(enemyZone.x, enemyZone.y, 720, 520);
}

function renderResource(r) {
  const p = worldToScreen(r.x, r.y);
  const pulse = Math.sin((state.tick + r.x) / 14) * 1.4;

  const glow = ctx.createRadialGradient(p.x, p.y, 2, p.x, p.y, 23 + pulse);
  glow.addColorStop(0, 'rgba(150, 225, 255, 0.65)');
  glow.addColorStop(1, 'rgba(84, 170, 240, 0)');
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(p.x, p.y, 22 + pulse, 0, Math.PI * 2);
  ctx.fill();

  ctx.save();
  ctx.translate(p.x, p.y);
  ctx.rotate(Math.PI / 6);
  ctx.fillStyle = '#55c5ff';
  ctx.strokeStyle = '#e0f7ff';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(0, -r.radius - pulse);
  for (let i = 1; i < 6; i++) {
    const a = (Math.PI * 2 * i) / 6 - Math.PI / 2;
    ctx.lineTo(Math.cos(a) * (r.radius + pulse), Math.sin(a) * (r.radius + pulse));
  }
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function renderStructure(s) {
  const p = worldToScreen(s.x, s.y);

  const baseGrad = ctx.createLinearGradient(p.x, p.y, p.x, p.y + s.h);
  baseGrad.addColorStop(0, s.color);
  baseGrad.addColorStop(1, shade(s.color, -25));
  ctx.fillStyle = baseGrad;
  roundRect(p.x, p.y, s.w, s.h, 8);
  ctx.fill();

  ctx.strokeStyle = s.player ? '#d9efff' : '#ffd2dc';
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.fillStyle = 'rgba(0,0,0,0.22)';
  roundRect(p.x + 8, p.y + 8, s.w - 16, s.h - 16, 5);
  ctx.fill();

  ctx.fillStyle = 'rgba(255,255,255,0.18)';
  roundRect(p.x + 6, p.y + 6, s.w - 12, 10, 4);
  ctx.fill();

  if (s.type === 'command' || s.type === 'hive') {
    ctx.strokeStyle = 'rgba(255,255,255,0.34)';
    ctx.beginPath();
    ctx.arc(p.x + s.w / 2, p.y + s.h / 2, s.w * 0.22, 0, Math.PI * 2);
    ctx.stroke();
  }

  if (s.type === 'barracks' || s.type === 'spawner') {
    ctx.strokeStyle = 'rgba(255,255,255,0.35)';
    ctx.beginPath();
    ctx.moveTo(p.x + 13, p.y + 13);
    ctx.lineTo(p.x + s.w - 13, p.y + s.h - 13);
    ctx.moveTo(p.x + s.w - 13, p.y + 13);
    ctx.lineTo(p.x + 13, p.y + s.h - 13);
    ctx.stroke();
  }

  drawHpBar(s, p.x, p.y - 10, s.w);
  ctx.fillStyle = '#eaf4ff';
  ctx.font = '600 10px Inter, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(NAMES[s.type], p.x + s.w / 2, p.y + s.h + 14);

  if (state.selected?.id === s.id) {
    const pulse = 2 + Math.sin(state.tick / 8) * 1.2;
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    roundRect(p.x - pulse, p.y - pulse, s.w + pulse * 2, s.h + pulse * 2, 10);
    ctx.stroke();
  }
}

function renderUnit(u) {
  const p = worldToScreen(u.x, u.y);

  ctx.fillStyle = 'rgba(0,0,0,0.30)';
  ctx.beginPath();
  ctx.ellipse(p.x, p.y + 12, 11.5, 4.5, 0, 0, Math.PI * 2);
  ctx.fill();

  const glow = ctx.createRadialGradient(p.x, p.y, 2, p.x, p.y, 20);
  glow.addColorStop(0, `${u.player ? 'rgba(90,210,255,0.30)' : 'rgba(255,80,125,0.28)'}`);
  glow.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(p.x, p.y, 20, 0, Math.PI * 2);
  ctx.fill();

  ctx.save();
  ctx.translate(p.x, p.y);
  ctx.rotate(u.heading || 0);

  ctx.fillStyle = u.color;
  ctx.beginPath();
  ctx.arc(0, 0, 11, 0, Math.PI * 2);
  ctx.fill();

  ctx.strokeStyle = u.player ? '#daf4ff' : '#ffd3dc';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  ctx.fillStyle = '#0b1115';
  if (u.type === 'worker') {
    ctx.fillRect(-4, -3, 8, 6);
  } else if (u.type === 'soldier') {
    ctx.beginPath();
    ctx.moveTo(9, 0);
    ctx.lineTo(-4, -4.5);
    ctx.lineTo(-4, 4.5);
    ctx.closePath();
    ctx.fill();
  } else {
    ctx.beginPath();
    ctx.moveTo(9, 0);
    ctx.lineTo(0, -5.5);
    ctx.lineTo(-7, 0);
    ctx.lineTo(0, 5.5);
    ctx.closePath();
    ctx.fill();
  }
  ctx.restore();

  if (state.selected?.id === u.id) {
    const pulse = 16 + Math.sin(state.tick / 7) * 1.5;
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(p.x, p.y, pulse, 0, Math.PI * 2);
    ctx.stroke();

    if (u.moveTarget) {
      const t = worldToScreen(u.moveTarget.x, u.moveTarget.y);
      ctx.strokeStyle = 'rgba(150, 230, 255, 0.8)';
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
      ctx.lineTo(t.x, t.y);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    if (u.target && u.target.hp > 0) {
      const t = worldToScreen(targetPos(u.target).x, targetPos(u.target).y);
      ctx.strokeStyle = 'rgba(255, 125, 155, 0.88)';
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
      ctx.lineTo(t.x, t.y);
      ctx.stroke();
    }
  }

  drawHpBar(u, p.x - 13, p.y - 22, 26);
}

function renderShotsAndParticles() {
  for (const s of state.shots) {
    const p1 = worldToScreen(s.x1, s.y1);
    const p2 = worldToScreen(s.x2, s.y2);
    ctx.strokeStyle = s.color;
    ctx.lineWidth = 2;
    ctx.globalAlpha = s.life / 8;
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.stroke();
    ctx.globalAlpha = 1;
  }

  for (const p of state.particles) {
    const s = worldToScreen(p.x, p.y);
    ctx.fillStyle = p.color;
    ctx.globalAlpha = Math.max(0, p.life / 24);
    ctx.beginPath();
    ctx.arc(s.x, s.y, p.size, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;
  }
}

function drawHpBar(entity, x, y, w) {
  ctx.fillStyle = 'rgba(0,0,0,0.48)';
  roundRect(x, y, w, 5, 3);
  ctx.fill();

  const fill = Math.max(0, (entity.hp / entity.maxHp) * (w - 2));
  ctx.fillStyle = entity.player ? '#57ebb0' : '#ff738f';
  roundRect(x + 1, y + 1, fill, 3, 2);
  ctx.fill();
}

function renderVignette() {
  const g = ctx.createRadialGradient(canvas.width / 2, canvas.height / 2, Math.min(canvas.width, canvas.height) * 0.2, canvas.width / 2, canvas.height / 2, Math.max(canvas.width, canvas.height) * 0.8);
  g.addColorStop(0, 'rgba(0,0,0,0)');
  g.addColorStop(1, 'rgba(0,0,0,0.24)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function render() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  renderTerrain();
  for (const r of state.resources) renderResource(r);
  for (const s of state.structures) renderStructure(s);
  for (const u of [...state.playerUnits, ...state.enemyUnits]) renderUnit(u);
  renderShotsAndParticles();
  renderVignette();
  renderMinimap();
}


function showBanner(text, duration = 2200) {
  statusBannerEl.textContent = text;
  statusBannerEl.classList.add('show');
  state.bannerTimer = duration;
}

function updateBanner() {
  if (state.bannerTimer > 0) {
    state.bannerTimer -= 16;
    if (state.bannerTimer <= 0) statusBannerEl.classList.remove('show');
  }
}

function checkGameState() {
  if (state.gameOver) return;
  const playerBaseAlive = state.structures.some((s) => s.player && s.type === 'command');
  const enemyCoreAlive = state.structures.some((s) => !s.player && (s.type === 'hive' || s.type === 'spawner'));

  if (!playerBaseAlive) {
    state.gameOver = true;
    showBanner('Поражение: база уничтожена');
  } else if (!enemyCoreAlive) {
    state.gameOver = true;
    showBanner('Победа: вражеский улей уничтожен!');
  }
}

function renderMinimap() {
  const mapW = 120;
  const mapH = 78;
  const x = canvas.width - mapW - 12;
  const y = canvas.height - mapH - 12;

  ctx.fillStyle = 'rgba(7, 14, 20, 0.72)';
  roundRect(x, y, mapW, mapH, 7);
  ctx.fill();
  ctx.strokeStyle = 'rgba(145, 193, 229, 0.55)';
  ctx.lineWidth = 1;
  ctx.stroke();

  const scaleX = mapW / WORLD.width;
  const scaleY = mapH / WORLD.height;

  for (const s of state.structures) {
    ctx.fillStyle = s.player ? '#85c4ff' : '#ff86a5';
    ctx.fillRect(x + s.x * scaleX, y + s.y * scaleY, Math.max(2, s.w * scaleX), Math.max(2, s.h * scaleY));
  }

  for (const u of state.playerUnits) {
    ctx.fillStyle = '#6fe9c3';
    ctx.fillRect(x + u.x * scaleX, y + u.y * scaleY, 2, 2);
  }

  for (const u of state.enemyUnits) {
    ctx.fillStyle = '#ff7398';
    ctx.fillRect(x + u.x * scaleX, y + u.y * scaleY, 2, 2);
  }

  ctx.strokeStyle = '#ffffff';
  ctx.strokeRect(x + state.camera.x * scaleX, y + state.camera.y * scaleY, canvas.width * scaleX, canvas.height * scaleY);
}

function updateHud() {
  mineralsEl.textContent = Math.floor(state.minerals);
  supplyEl.textContent = `${state.supplyUsed}/${state.supplyMax}`;
  enemyCountEl.textContent = state.enemyUnits.length;
}

function gameLoop() {
  if (!state.gameOver) {
    tickAI();
    updateUnits(state.playerUnits);
    updateUnits(state.enemyUnits);
    cleanupDead();
    checkGameState();
  }
  updateFx();
  updateBanner();
  clampCamera();
  updateHud();
  render();
  requestAnimationFrame(gameLoop);
}

canvas.addEventListener('pointerdown', (e) => {
  state.camera.drag = true;
  state.camera.moved = 0;
  state.camera.lastX = e.clientX;
  state.camera.lastY = e.clientY;
});

canvas.addEventListener('pointermove', (e) => {
  if (!state.camera.drag) return;
  const dx = e.clientX - state.camera.lastX;
  const dy = e.clientY - state.camera.lastY;
  state.camera.moved += Math.hypot(dx, dy);
  state.camera.x -= dx;
  state.camera.y -= dy;
  state.camera.lastX = e.clientX;
  state.camera.lastY = e.clientY;
});

canvas.addEventListener('pointerup', (e) => {
  if (state.camera.moved < 8) handleTap(e.clientX, e.clientY);
  state.camera.drag = false;
});

canvas.addEventListener('pointercancel', () => {
  state.camera.drag = false;
});

window.addEventListener('resize', () => {
  resizeCanvas();
  clampCamera();
});

function roundRect(x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

function shade(hex, percent) {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 0xff;
  const g = (n >> 8) & 0xff;
  const b = n & 0xff;
  const amt = percent / 100;
  const nr = Math.max(0, Math.min(255, Math.round(r + 255 * amt)));
  const ng = Math.max(0, Math.min(255, Math.round(g + 255 * amt)));
  const nb = Math.max(0, Math.min(255, Math.round(b + 255 * amt)));
  return `rgb(${nr}, ${ng}, ${nb})`;
}

resizeCanvas();
spawnInitial();
updateHud();
renderActions();
showBanner('Уничтожь улей врага и защищай базу');
requestAnimationFrame(gameLoop);
