'use strict';
/*
 * game.js — Arcana Grove.
 *
 * Gameplay idêntico ao original; a renderização agora usa os sprites Aseprite
 * (via assets.js) em vez de círculos vetoriais. Se um asset não carregar, o
 * desenho vetorial de fallback assume automaticamente.
 */

const canvas = document.querySelector('#game');
const ctx = canvas.getContext('2d');
let W, H, dpr;
let bgCanvas = null;   // piso pré-renderizado em modo "cover"

/* Referências explícitas de UI (o original confiava em globais implícitas
 * criadas pelos id dos elementos, o que é frágil). */
const ui = {
  wave: document.querySelector('#wave'),
  time: document.querySelector('#time'),
  kills: document.querySelector('#kills'),
  hp: document.querySelector('#hp'),
  hpText: document.querySelector('#hpText'),
  xp: document.querySelector('#xp'),
  level: document.querySelector('#level'),
  choices: document.querySelector('#choices'),
  levelup: document.querySelector('#levelup'),
  gameover: document.querySelector('#gameover'),
  finalStats: document.querySelector('#finalStats'),
  restart: document.querySelector('#restart'),
  hint: document.querySelector('#hint'),
  loading: document.querySelector('#loading'),
};

/* ---------------------------------------------------------------- resize -- */
function resize() {
  dpr = devicePixelRatio || 1;
  W = innerWidth;
  H = innerHeight;
  canvas.width = W * dpr;
  canvas.height = H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  rebuildBackground();
}
addEventListener('resize', resize);

/* Piso em modo cover: escala para cobrir a tela com corte central. A textura
 * não é tileável, então repetir em mosaico criaria emendas visíveis. */
function rebuildBackground() {
  const img = Assets.background;
  if (!img) { bgCanvas = null; return; }   // sem imagem: draw() cai no fundo vetorial
  bgCanvas = document.createElement('canvas');
  bgCanvas.width = W;
  bgCanvas.height = H;
  const b = bgCanvas.getContext('2d');
  const s = Math.max(W / img.width, H / img.height);
  const dw = img.width * s, dh = img.height * s;
  b.imageSmoothingEnabled = true;
  b.drawImage(img, (W - dw) / 2, (H - dh) / 2, dw, dh);
}

/* ----------------------------------------------------------------- input -- */
const keys = {};
addEventListener('keydown', (e) => {
  keys[e.key.toLowerCase()] = true;
  if (['arrowup', 'arrowdown', 'arrowleft', 'arrowright', ' '].includes(e.key.toLowerCase())) e.preventDefault();
});
addEventListener('keyup', (e) => keys[e.key.toLowerCase()] = false);

/* ---------------------------------------------------------------- estado -- */
let player, enemies, shots, orbs, particles, trees, game, last = 0;
let playerMoving = false;   // usado para escolher idle/movement do bruxo

const upgrades = [
  { name: 'Projéteis Adicionais', desc: 'Dispara +1 feitiço simultâneo em leque.', icon: '✦', fn: () => game.bullets++ },
  { name: 'Área de Impacto', desc: 'Aumenta o raio de explosão das magias.', icon: '◉', fn: () => game.aoe += 8 },
  { name: 'Raio de Atração', desc: 'Coleta fragmentos de mana de mais longe.', icon: '⌁', fn: () => game.magnet += 45 },
  { name: 'Botas do Vento', desc: 'Aumenta sua velocidade de movimento.', icon: '➤', fn: () => game.speed += .7 },
  { name: 'Escudo Arcano', desc: 'Absorve um golpe. Recarga em 15 segundos.', icon: '◇', fn: () => game.shield++ },
];

/* Cada tipo de inimigo aponta para um sheet exportado do Aseprite. Os raios de
 * colisão (r) são os mesmos do jogo original; scale só afeta o desenho.
 * O bruxo (personagem principal) saiu da lista: agora ele tem sprite próprio em
 * Sprite/Characters/bruxo.png. */
const ENEMY_TYPES = {
  goblin: { sheet: 'skeleton1', r: 11, hp: 1, spd: .7,  scale: 1.6 },
  runner: { sheet: 'skeleton2', r: 9,  hp: 1, spd: 1.5, scale: 1.3 },
  elite:  { sheet: 'skeleton2', r: 16, hp: 7, spd: 1.05, scale: 2.4 },
};

/* Personagem principal: mesma convenção dos inimigos — célula 32x32, âncora nos
 * pés (o art tem de 15 a 20 px de altura dentro da célula) e espelhamento
 * horizontal. O ataque do bruxo dura 1,6 s no Aseprite, mas o cajado dispara a
 * cada 0,65 s: tocar mais rápido evita que a animação fique reiniciando. */
const PLAYER_SHEET = 'bruxo';
const PLAYER = { r: 13, scale: 2.2, animSpeed: { attack: 2.4 } };

function reset() {
  game = { time: 0, wave: 1, kills: 0, level: 1, xp: 0, next: 7, hp: 100, bullets: 1, aoe: 18, magnet: 55, speed: 2.5, shield: 1, spawn: 0, shoot: 0 };
  const sheet = Assets.sheet(PLAYER_SHEET);
  player = {
    x: W / 2, y: H / 2, r: PLAYER.r, inv: 0, face: 1,
    sheet, anim: sheet && sheet.ok ? new Assets.Animation(sheet, 'idle') : null,
    dying: false, dead: false,
  };
  enemies = []; shots = []; orbs = []; particles = []; trees = [];
  for (let i = 0; i < 38; i++) {
    let x = Math.random() * W, y = Math.random() * H;
    if (Math.hypot(x - player.x, y - player.y) > 130) trees.push({ x, y, r: 10 + Math.random() * 16, type: Math.random() > .25 ? 'tree' : 'rock' });
  }
  playerMoving = false;
  ui.gameover.classList.add('hidden');
  ui.levelup.classList.add('hidden');
}

/* --------------------------------------------------------------- combate -- */
function spawn() {
  let a = Math.random() * Math.PI * 2, dist = Math.max(W, H) * .65;
  let type = game.time > 300 ? (Math.random() < .2 ? 'elite' : 'runner') : game.time > 120 ? 'runner' : 'goblin';
  const cfg = ENEMY_TYPES[type];
  const sheet = Assets.sheet(cfg.sheet);
  enemies.push({
    x: player.x + Math.cos(a) * dist,
    y: player.y + Math.sin(a) * dist,
    r: cfg.r, hp: cfg.hp, spd: cfg.spd, type,
    scale: cfg.scale,
    sheet,
    anim: sheet && sheet.ok ? new Assets.Animation(sheet, 'movement') : null,
    face: 1, hitT: 0, dying: false, remove: false,
  });
}

function shoot() {
  const alive = enemies.filter((e) => !e.dying);
  if (!alive.length) return;
  let target = alive.reduce((a, b) =>
    Math.hypot(a.x - player.x, a.y - player.y) < Math.hypot(b.x - player.x, b.y - player.y) ? a : b);
  let base = Math.atan2(target.y - player.y, target.x - player.x);

  // vira para o alvo e dá o golpe de cajado
  player.face = Math.cos(base) >= 0 ? 1 : -1;
  if (player.anim) { player.anim.set('attack'); player.anim.restart(); }

  // a magia sai da ponta do cajado, não do meio do corpo
  const ox = player.x + Math.cos(base) * 14, oy = player.y + Math.sin(base) * 14;
  for (let i = 0; i < game.bullets; i++) {
    let spread = (i - (game.bullets - 1) / 2) * .22;
    shots.push({ x: ox, y: oy, vx: Math.cos(base + spread) * 5, vy: Math.sin(base + spread) * 5, life: 80 });
  }
}

function update(dt) {
  game.time += dt;
  game.wave = 1 + Math.floor(game.time / 60);
  game.spawn -= dt; game.shoot -= dt;
  player.inv = Math.max(0, player.inv - dt);

  /* --- morte do bruxo: toca a animação e só então mostra o fim de jogo --- */
  if (player.dying) {
    if (player.anim) player.anim.advance(dt * 1000 * playerAnimSpeed('death'));
    playerMoving = false;
    if (!player.anim || player.anim.finished) {
      player.dying = false;
      player.dead = true;
      ui.finalStats.textContent = `Você alcançou a onda ${game.wave} e derrotou ${game.kills} criaturas.`;
      ui.gameover.classList.remove('hidden');
    }
    updateHUD();
    return;
  }

  if (game.spawn <= 0) { spawn(); game.spawn = Math.max(.18, 1.1 - game.time / 500); }
  if (game.shoot <= 0) { shoot(); game.shoot = .65; }

  let dx = (keys.d || keys.arrowright ? 1 : 0) - (keys.a || keys.arrowleft ? 1 : 0);
  let dy = (keys.s || keys.arrowdown ? 1 : 0) - (keys.w || keys.arrowup ? 1 : 0);
  let len = Math.hypot(dx, dy) || 1;
  player.x = Math.max(25, Math.min(W - 25, player.x + dx / len * game.speed));
  player.y = Math.max(55, Math.min(H - 25, player.y + dy / len * game.speed));
  if (dx) player.face = dx > 0 ? 1 : -1;      // olha para onde anda
  playerMoving = !!(dx || dy);

  for (let s of shots) { s.x += s.vx; s.y += s.vy; s.life -= dt * 60; }
  shots = shots.filter((s) => s.life > 0);

  for (let e of enemies) {
    if (e.hitT > 0) e.hitT -= dt;

    // Morrendo: só reproduz a animação de morte até o fim, sem colidir.
    if (e.dying) {
      if (e.anim) e.anim.advance(dt * 1000);
      if (!e.anim || e.anim.finished) e.remove = true;
      continue;
    }

    let a = Math.atan2(player.y - e.y, player.x - e.x), slow = 0;
    for (let t of trees) if (Math.hypot(e.x - t.x, e.y - t.y) < t.r + e.r + 5) slow = .4;
    e.x += Math.cos(a) * e.spd * (1 - slow);
    e.y += Math.sin(a) * e.spd * (1 - slow);
    e.face = player.x >= e.x ? 1 : -1;   // sprites olham p/ direita por padrão

    const dist = Math.hypot(e.x - player.x, e.y - player.y);
    const contact = dist < e.r + player.r + 4;
    if (e.anim) {
      e.anim.set(e.hitT > 0 ? 'take_damage' : (contact ? 'attack' : 'movement'));
      e.anim.advance(dt * 1000);
    }

    if (dist < e.r + player.r && player.inv <= 0) {
      if (game.shield) { game.shield--; player.inv = 1.2; } else game.hp -= 18;
      player.inv = 1.2;
      if (game.hp <= 0) {                       // golpe final: morre com animação
        player.dying = true;
        if (player.anim) { player.anim.set('death'); player.anim.restart(); }
      } else if (player.anim) {                 // reação ao levar dano
        player.anim.set('take_damage');
        player.anim.restart();
      }
    }
  }

  for (let s of shots) {
    for (let e of enemies) {
      if (e.dying) continue;
      if (Math.hypot(s.x - e.x, s.y - e.y) < e.r + 5) {
        e.hp--; s.life = 0;
        if (e.hp <= 0) {
          game.kills++;
          orbs.push({ x: e.x, y: e.y, val: e.type === 'elite' ? 3 : 1 });
          for (let i = 0; i < 4; i++) {
            const pa = Math.random() * Math.PI * 2;
            particles.push({ x: e.x, y: e.y, vx: Math.cos(pa) * 40, vy: Math.sin(pa) * 40, life: .4 });
          }
          // entra em estado de morte: toca a animação antes de sumir
          e.dying = true;
          if (e.anim) {
            const alt = e.sheet && e.sheet.hasTag(e.sheet.resolveTag('death2')) && Math.random() < .5;
            e.anim.set(alt ? 'death2' : 'death');
          }
        } else {
          e.hitT = .28;   // reage ao golpe sem morrer
        }
        break;
      }
    }
  }
  enemies = enemies.filter((e) => !e.remove);

  for (let o of orbs) {
    let d = Math.hypot(player.x - o.x, player.y - o.y);
    if (d < game.magnet) { o.x += (player.x - o.x) * .07; o.y += (player.y - o.y) * .07; }
    if (d < 18) { game.xp += o.val; o.dead = true; }
  }
  orbs = orbs.filter((o) => !o.dead);

  for (let p of particles) { p.x += p.vx * dt; p.y += p.vy * dt; p.life -= dt; }
  particles = particles.filter((p) => p.life > 0);

  if (game.xp >= game.next) { game.xp -= game.next; game.next = Math.floor(game.next * 1.35); game.level++; pauseLevel(); }
  updatePlayerAnim(dt);
  updateHUD();
}

/* ------------------------------------------------------- animação do herói -- */
/* Escolhe a tag pelo que está acontecendo, dando prioridade para os estados de
 * uma vez só (ataque / dano), que não podem ser interrompidos no meio. */
function playerAnimSpeed(tag) { return PLAYER.animSpeed[tag] || 1; }

function updatePlayerAnim(dt) {
  const a = player.anim;
  if (!a || player.dying) return;
  if (!a.finished && (a.name === 'attack' || a.name === 'take_damage')) {   // toca até o fim
    a.advance(dt * 1000 * playerAnimSpeed(a.name));
    return;
  }
  a.set(playerMoving ? 'movement' : 'idle');
  a.advance(dt * 1000);
}

/* ------------------------------------------------------------ level / HUD -- */
function pauseLevel() {
  ui.level.textContent = game.level;
  let picks = [...upgrades].sort(() => Math.random() - .5).slice(0, 3);
  ui.choices.innerHTML = picks.map((u, i) =>
    `<article class="choice" data-i="${i}"><div class="icon">${u.icon}</div><h2>${u.name}</h2><p>${u.desc}</p></article>`).join('');
  document.querySelectorAll('.choice').forEach((el, i) => {
    el.onclick = () => { picks[i].fn(); ui.levelup.classList.add('hidden'); };
  });
  ui.levelup.classList.remove('hidden');
}

function updateHUD() {
  ui.wave.textContent = game.wave;
  ui.kills.textContent = game.kills;
  ui.time.textContent = new Date(game.time * 1000).toISOString().substring(14, 19);
  ui.hp.style.width = Math.max(0, game.hp) + '%';
  ui.hpText.textContent = `${Math.max(0, game.hp)} / 100`;
  ui.xp.style.width = Math.min(100, game.xp / game.next * 100) + '%';
}

/* ------------------------------------------------------------------ draw -- */
function drawBackground() {
  if (bgCanvas) {
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(bgCanvas, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = 'rgba(7,17,12,0.30)';   // escurece p/ legibilidade do HUD
    ctx.fillRect(0, 0, W, H);
    return;
  }
  // fallback vetorial (asset ausente)
  ctx.fillStyle = '#10291e'; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#153b27';
  for (let i = 0; i < 120; i++) { let x = (i * 83) % W, y = (i * 47) % H; ctx.fillRect(x, y, 2, 2); }
}

/* Desenha um frame de sheet ancorado nos pés, com espelhamento horizontal.
 * Usado pelo personagem e pelos inimigos — mesma convenção de arte. */
function drawSheet(sheet, anim, x, feetY, scale, face) {
  const rct = anim.rect, dw = rct.w * scale, dh = rct.h * scale;
  ctx.save();
  ctx.translate(x, feetY);
  ctx.scale(face, 1);
  ctx.imageSmoothingEnabled = false;      // pixel art nítida
  ctx.drawImage(sheet.image, rct.x, rct.y, rct.w, rct.h, -dw / 2, -dh, dw, dh);
  ctx.restore();
}

function drawEnemy(e) {
  const feetY = e.y + e.r;
  // sombra de contato com o chão
  ctx.fillStyle = 'rgba(4,10,7,0.35)';
  ctx.beginPath();
  ctx.ellipse(e.x, feetY, e.r * .95, e.r * .38, 0, 0, 7);
  ctx.fill();

  if (e.anim && e.sheet && e.sheet.ok) {
    drawSheet(e.sheet, e.anim, e.x, feetY, e.scale, e.face);
  } else {
    // fallback: o desenho vetorial original
    ctx.fillStyle = e.type === 'elite' ? '#db725d' : e.type === 'runner' ? '#ddad54' : '#a7c85e';
    ctx.beginPath(); ctx.arc(e.x, e.y, e.r, 0, 7); ctx.fill();
    ctx.fillStyle = '#14251b';
    ctx.fillRect(e.x - 5, e.y - 2, 3, 3); ctx.fillRect(e.x + 3, e.y - 2, 3, 3);
    if (e.type === 'elite') {
      ctx.strokeStyle = '#ee816c'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(e.x, e.y, e.r + 5, 0, 7); ctx.stroke();
    }
  }

  if (e.type === 'elite' && !e.dying) {   // aura p/ destacar o elite
    ctx.strokeStyle = 'rgba(238,129,108,0.55)';
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(e.x, e.y, e.r + 6, 0, 7); ctx.stroke();
  }
}

function draw() {
  drawBackground();

  for (let t of trees) {
    ctx.fillStyle = t.type === 'tree' ? '#0a2118' : '#334d3c';
    ctx.beginPath(); ctx.arc(t.x, t.y, t.r, 0, 7); ctx.fill();
    if (t.type === 'tree') {
      ctx.fillStyle = '#1f5636';
      ctx.fillRect(t.x - 3, t.y - t.r - 12, 6, 15);
      ctx.beginPath(); ctx.arc(t.x, t.y - t.r, 12, 0, 7); ctx.fill();
    }
  }

  for (let o of orbs) {
    ctx.fillStyle = '#bca0ff'; ctx.shadowBlur = 10; ctx.shadowColor = '#a987ff';
    ctx.beginPath(); ctx.arc(o.x, o.y, 5, 0, 7); ctx.fill();
    ctx.shadowBlur = 0;
  }

  for (let p of particles) {
    ctx.globalAlpha = Math.max(0, p.life / .4);
    ctx.fillStyle = '#e6d8ff';
    ctx.fillRect(p.x - 2, p.y - 2, 4, 4);
    ctx.globalAlpha = 1;
  }

  for (let s of shots) {
    ctx.fillStyle = '#d9c3ff'; ctx.shadowBlur = 12; ctx.shadowColor = '#a987ff';
    ctx.beginPath(); ctx.arc(s.x, s.y, 5, 0, 7); ctx.fill();
    ctx.shadowBlur = 0;
  }

  for (let e of enemies) drawEnemy(e);

  drawPlayer();

  requestAnimationFrame(loop);
}

/* O bruxo: sprite quando disponível, círculo + cajado (placeholder original)
 * como fallback. A âncora é a mesma dos inimigos — os pés. */
const PLAYER_FALLBACK = { body: '#7558a8', hit: '#fff', hat: '#d6c3ad', staff: '#c5ed72' };

function drawPlayer() {
  const feetY = player.y + player.r;

  ctx.fillStyle = 'rgba(4,10,7,0.35)';        // sombra de contato
  ctx.beginPath();
  ctx.ellipse(player.x, feetY, player.r * .95, player.r * .38, 0, 0, 7);
  ctx.fill();

  // pisca enquanto está invulnerável depois de levar dano
  const piscando = player.inv > 0 && Math.floor(player.inv * 12) % 2 === 0;
  ctx.globalAlpha = piscando ? .35 : 1;

  if (player.anim && player.sheet && player.sheet.ok && player.anim.rect) {
    drawSheet(player.sheet, player.anim, player.x, feetY, PLAYER.scale, player.face);
  } else {
    ctx.save();
    ctx.translate(player.x, player.y);
    ctx.fillStyle = piscando ? PLAYER_FALLBACK.hit : PLAYER_FALLBACK.body;
    ctx.beginPath(); ctx.arc(0, 0, player.r, 0, 7); ctx.fill();
    ctx.fillStyle = PLAYER_FALLBACK.hat; ctx.fillRect(-9, -12, 18, 5);
    ctx.fillStyle = PLAYER_FALLBACK.staff; ctx.rotate(-.6); ctx.fillRect(8, -2, 22, 3);
    ctx.restore();
  }
  ctx.globalAlpha = 1;

  // escudo arcano ativo: aro em volta do bruxo
  if (game.shield > 0 && !player.dead) {
    ctx.strokeStyle = 'rgba(180,160,255,0.5)';
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(player.x, player.y, player.r + 6, 0, 7); ctx.stroke();
  }
}

function loop(t) {
  let dt = Math.min(.04, (t - last) / 1000);
  last = t;
  if (ui.levelup.classList.contains('hidden') &&
      ui.gameover.classList.contains('hidden')) update(dt);
  draw();
}

/* ------------------------------------------------------------------ boot -- */
ui.restart.onclick = reset;
resize();
reset();

Assets.load().then(() => {
  rebuildBackground();                      // piso pode ter chegado depois do resize
  ui.loading.classList.add('hidden');
  if (Assets.anyFailed) {
    ui.hint.textContent =
      'WASD / SETAS para mover · O cajado ataca sozinho · (alguns sprites não carregaram: usando fallback)';
  }
  requestAnimationFrame(loop);
});
