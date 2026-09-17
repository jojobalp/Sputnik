#!/usr/bin/env node
/**
 * smoke_inimigos.mjs — teste de fumaça dos inimigos, sem navegador.
 *
 * Carrega assets.js + game.js de verdade (ambiente falso em tools/apoio/) e
 * dirige o jogo quadro a quadro para conferir os dois inimigos do pack Tiny RPG:
 *
 *   - os sheets soldado/orc/flecha carregam no formato do jogo (célula própria,
 *     tags de idle/movement/attack/take_damage/death);
 *   - o soldado anda até a distância de tiro, para, toca o ataque e solta a
 *     flecha no meio da animação — a flecha voa, é desenhada do sheet e fere o
 *     bruxo quando acerta;
 *   - o orc é corpo a corpo: encosta, toca o ataque e bate mais forte;
 *   - os dois morrem com animação e soltam orbe de mana;
 *   - sem os sheets (clone novo, sem rodar o importador) o jogo não quebra:
 *     desenha o fallback e continua jogável.
 *
 * As checagens que dependem da arte do pack (sprites e tags) são puladas — com
 * aviso — quando os sheets não estão em Sprite/Enemies/, porque eles não são
 * versionados (licença do pack). O resto roda igual.
 *
 * Uso: node tools/smoke_inimigos.mjs
 */

import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { criarAmbiente, rodarJogo } from './apoio/falso_navegador.mjs';

const raiz = resolve(dirname(fileURLToPath(import.meta.url)), '..');

/* ------------------------------------------------------------ utilidades -- */
const falhas = [];
let checagens = 0;
let puladas = 0;
function checar(cond, msg) {
  checagens++;
  if (!cond) falhas.push(msg);
}
function titulo(t) { console.log(`\n${t}`); }

/* ------------------------------------------------ stubs de DOM e canvas -- */
const { sandbox, desenhos } = criarAmbiente(raiz);

/* --------------------------------------------------- testes dentro do jogo -- */
const testes = `
(async () => {
  const esperar = () => new Promise((r) => setTimeout(r, 0));
  for (let i = 0; i < 5; i++) await esperar();      // deixa o Assets.load terminar

  const quadro = (ms) => { const cb = globalThis.__raf; globalThis.__raf = null; cb(ms); };
  let t = 1000;
  const rodar = (n = 1, passo = 40) => { for (let i = 0; i < n; i++) { t += passo; quadro(t); } };

  globalThis.__t = {
    Assets, player, game, enemies, shots, arrows, keys, ui, ENEMY_TYPES,
    update, draw, spawn, shoot, reset, rodar, flecha,
    setGame: (campos) => Object.assign(game, campos),
    getPlayer: () => player, getGame: () => game,
    getEnemies: () => enemies, getShots: () => shots, getArrows: () => arrows,
  };
})();
`;

rodarJogo(sandbox, raiz, testes);

/* --------------------------------------------------------------- testes -- */
await new Promise((r) => setTimeout(r, 60));   // espera o boot
const T = sandbox.__t;
if (!T) {
  console.error('não consegui inicializar o jogo no sandbox');
  process.exit(1);
}
const { Assets, keys, ui } = T;
const ver = checar, sec = titulo;

/* Os sheets do pack são gerados por tools/importar_pack.py e, por licença, não
 * entram no repositório: num clone novo eles não existem. Nesse caso o teste
 * segue — o que depende da arte é pulado, o comportamento é verificado igual. */
const packOk = ['soldier', 'orc', 'flecha'].every((k) => Assets.sheet(k) && Assets.sheet(k).ok);
function pularChecagem(msg) {
  if (packOk) checar(false, msg);
  else puladas++;
}
if (!packOk) {
  console.log('AVISO: os sheets do pack Tiny RPG não estão em Sprite/Enemies/.');
  console.log('       rode: python3 tools/importar_pack.py --mapa tools/mapas/pack_tiny.json --saida-dir art/tiny-rpg-pack/jogo');
  console.log('       cp art/tiny-rpg-pack/jogo/{soldier,orc,flecha}.{png,json} Sprite/Enemies/');
  console.log('       sem eles eu pulo as checagens de sprite e sigo com o comportamento (desenho de fallback).');
}

/* confere um sheet do pack: célula, quantidade de quadros e tags esperadas */
function conferirSheet(chave, celula, tags) {
  const s = Assets.sheet(chave);
  if (!packOk || !s || !s.ok) { pularChecagem(`sheet ${chave} não carregou`); return null; }
  checar(s.frames.every((f) => f.w === celula && f.h === celula),
    `célula do ${chave} deveria ser ${celula}x${celula}`);
  checar(s.image.height === celula, `altura do ${chave} deveria ser a da célula (tira de uma linha)`);
  for (const t of tags) checar(s.hasTag(s.resolveTag(t)), `tag "${t}" não encontrada no ${chave}`);
  return s;
}

sec('1. sheets do pack no formato do jogo');
const chSoldado = conferirSheet('soldier', 64, ['idle', 'movement', 'attack', 'take_damage', 'death']);
const chOrc = conferirSheet('orc', 64, ['idle', 'movement', 'attack', 'take_damage', 'death']);
const chFlecha = conferirSheet('flecha', 32, ['idle']);
if (chFlecha) checar(chFlecha.frames.length === 1, `a flecha deveria ter 1 quadro, tem ${chFlecha.frames.length}`);
if (chSoldado && chOrc) {
  console.log(`   soldado: ${chSoldado.frames.length} quadros (célula 64) · orc: ${chOrc.frames.length} quadros`);
}

sec('2. tipos de inimigo declarados');
for (const tipo of ['goblin', 'runner', 'elite', 'soldier', 'orc']) {
  const cfg = T.ENEMY_TYPES[tipo];
  checar(!!cfg, `tipo ${tipo} não está em ENEMY_TYPES`);
  if (cfg && cfg.sheet) {
    const chave = cfg.sheet;
    if (packOk || ['skeleton1', 'skeleton2'].includes(chave)) {
      checar(!!Assets.sheet(chave) && Assets.sheet(chave).ok, `o sheet "${chave}" (tipo ${tipo}) não carregou`);
    }
  }
}
checar(T.ENEMY_TYPES.soldier.atira === true, 'o soldado deveria ser atirador (cfg.atira)');
checar(T.ENEMY_TYPES.soldier.distancia > 100, 'o soldado deveria atirar de longe');
checar((T.ENEMY_TYPES.orc.dmg || 0) > 18, 'o orc deveria bater mais forte que o contato comum');
checar(T.ENEMY_TYPES.orc.hp > T.ENEMY_TYPES.soldier.hp, 'o orc deveria aguentar mais pancada que o soldado');

sec('3. soldado: anda até a distância de tiro e para');
T.reset();
T.setGame({ spawn: 999, shoot: 999 });
T.getEnemies().length = 0;
T.spawn('soldier');
const sold = T.getEnemies()[T.getEnemies().length - 1];
checar(sold.type === 'soldier', `spawn('soldier') criou um ${sold.type}`);
sold.x = T.getPlayer().x + 260; sold.y = T.getPlayer().y;
T.rodar(1);
if (sold.anim) checar(sold.anim.tag.endsWith('movement'), `longe do bruxo deveria andar, tocou ${sold.anim.tag}`);
else pularChecagem('soldado sem animação: não dá para conferir a tag de movimento');
checar(sold.face === -1, 'o soldado à direita do bruxo deveria olhar para a esquerda');
const dAntes = Math.abs(sold.x - T.getPlayer().x);
T.rodar(20);
checar(Math.abs(sold.x - T.getPlayer().x) < dAntes - 5, 'o soldado deveria se aproximar enquanto está longe');

sold.x = T.getPlayer().x + 150; sold.reload = 0;   // já na distância de tiro
const dLonge = Math.abs(sold.x - T.getPlayer().x);
T.rodar(3);
checar(Math.abs(Math.abs(sold.x - T.getPlayer().x) - dLonge) < 1, 'na distância de tiro o soldado deveria parar');
if (sold.anim) checar(sold.anim.tag.endsWith('attack'), `ao atirar deveria tocar attack, tocou ${sold.anim.tag}`);
else pularChecagem('soldado sem animação: não dá para conferir a tag de ataque');

/* Põe um soldado a 90 px do bruxo, deixa o ataque começar e espera a flecha
 * chegar. Devolve o que interessa conferir: se desenhou do sheet, se a flecha
 * saiu no meio da animação e quanto de hp foi tirado. */
function flechada(opcoes) {
  T.reset();
  T.setGame(Object.assign({ spawn: 999, shoot: 999, hp: 100, shield: 0 }, opcoes));
  T.getEnemies().length = 0;
  T.spawn('soldier');
  const arqueiro = T.getEnemies()[T.getEnemies().length - 1];
  arqueiro.x = T.getPlayer().x + 90; arqueiro.y = T.getPlayer().y;
  arqueiro.reload = 0;
  T.rodar(2);
  const cedo = T.getArrows().length;
  T.rodar(20);                                     // ~0,8 s: passa o ARROW_DELAY
  const noAr = T.getArrows().slice();
  const ch = Assets.sheet('flecha');
  desenhos.length = 0;
  T.rodar(1);
  const desenhou = desenhos.some((d) => ch && ch.ok && d[0] === ch.image);
  const hpAntes = T.getGame().hp;
  let guarda = 0;
  while (T.getArrows().length && guarda++ < 120) T.rodar(1);
  return { arqueiro, cedo, noAr, desenhou, dano: hpAntes - T.getGame().hp };
}

sec('4. soldado: a flecha sai no meio do ataque e fere o bruxo');
const tiro = flechada({});
checar(tiro.cedo === 0, 'a flecha não deveria sair no primeiro instante do ataque');
checar(tiro.noAr.length >= 1, 'o soldado não soltou flecha nenhuma');
checar(tiro.noAr.every((f) => f.vx < 0), 'a flecha deveria voar na direção do bruxo');
if (packOk) checar(tiro.desenhou, 'a flecha não foi desenhada a partir do sheet');
else puladas++;                                    // sem o sheet, o jogo desenha o traço de fallback
checar(tiro.dano === T.ENEMY_TYPES.soldier.dmg,
  `a flecha deveria tirar ${T.ENEMY_TYPES.soldier.dmg} de hp, tirou ${tiro.dano}`);
checar(T.getPlayer().anim.tag.endsWith('take_damage'), 'o bruxo deveria reagir à flechada');

sec('5. o escudo arcano segura a flecha');
const comEscudo = flechada({ shield: 1 });
checar(comEscudo.dano === 0, `com escudo a flecha não deveria tirar hp, tirou ${comEscudo.dano}`);
checar(T.getGame().shield === 0, 'o escudo deveria ser consumido pela flechada');

sec('6. soldado não bate corpo a corpo');
T.reset();
T.setGame({ spawn: 999, shoot: 999, hp: 100, shield: 0 });
T.getEnemies().length = 0;
T.spawn('soldier');
const encostado = T.getEnemies()[T.getEnemies().length - 1];
encostado.x = T.getPlayer().x; encostado.y = T.getPlayer().y;
T.rodar(2);
checar(T.getGame().hp === 100, `o soldado não deveria dar dano de contato (hp ${T.getGame().hp})`);

sec('7. orc: brutamontes corpo a corpo');
T.reset();
T.setGame({ spawn: 999, shoot: 999, hp: 100, shield: 0 });
T.getEnemies().length = 0;
T.spawn('orc');
const orc = T.getEnemies()[T.getEnemies().length - 1];
checar(orc.type === 'orc', `spawn('orc') criou um ${orc.type}`);
checar(orc.hp === T.ENEMY_TYPES.orc.hp, 'o orc deveria nascer com o hp do tipo');
orc.x = T.getPlayer().x + 25; orc.y = T.getPlayer().y;
T.rodar(1);
if (orc.anim) checar(orc.anim.tag.endsWith('attack'), `encostado deveria tocar attack, tocou ${orc.anim.tag}`);
else pularChecagem('orc sem animação: não dá para conferir a tag de ataque');
checar(T.getGame().hp === 100 - T.ENEMY_TYPES.orc.dmg,
  `o orc deveria tirar ${T.ENEMY_TYPES.orc.dmg} de hp, tirou ${100 - T.getGame().hp}`);
if (chOrc) {
  desenhos.length = 0;
  T.rodar(1);
  checar(desenhos.some((d) => d[0] === chOrc.image), 'o orc não foi desenhado a partir do sheet');
} else {
  puladas++;
}

sec('8. morte dos dois com animação e orbe');
for (const tipo of ['soldier', 'orc']) {
  T.reset();
  T.setGame({ spawn: 999, shoot: 999, hp: 100 });
  T.getEnemies().length = 0;
  T.spawn(tipo);
  const alvo = T.getEnemies()[T.getEnemies().length - 1];
  alvo.x = T.getPlayer().x + 120; alvo.y = T.getPlayer().y;
  alvo.hp = 1;
  T.getShots().push({ x: alvo.x, y: alvo.y, vx: 0, vy: 0, life: 10 });
  T.rodar(1);
  checar(alvo.dying, `${tipo}: ao zerar o hp deveria entrar em morte`);
  if (alvo.anim) {
    checar(alvo.anim.tag.endsWith('death'), `${tipo}: deveria tocar death, tocou ${alvo.anim.tag}`);
  } else {
    pularChecagem(`${tipo}: sem animação de morte`);
  }
  checar(T.getGame().kills === 1, `${tipo}: a morte deveria contar como abate`);
  T.rodar(60, 40);                               // ~2,4 s: a morte tem 0,9 s
  checar(T.getEnemies().length === 0, `${tipo}: o corpo deveria sair da lista depois da animação`);
}

sec('9. a mistura de inimigos abre com o tempo');
/* sorteiaTipo não é exposto; uso as ondas do jogo para conferir que os tipos
 * novos aparecem depois do tempo previsto. */
T.reset();
T.setGame({ spawn: 999, shoot: 999, time: 0 });
const cedo = new Set();
for (let i = 0; i < 120; i++) { T.spawn(); cedo.add(T.getEnemies().pop().type); }
checar(cedo.size === 1 && cedo.has('goblin'), `no começo deveria nascer só goblin, veio ${[...cedo].join('/')}`);
T.setGame({ time: 200 });
const tarde = new Set();
for (let i = 0; i < 400; i++) { T.spawn(); tarde.add(T.getEnemies().pop().type); }
for (const tipo of ['goblin', 'soldier', 'runner', 'orc']) {
  checar(tarde.has(tipo), `no meio da partida o tipo ${tipo} deveria aparecer (veio ${[...tarde].join('/')})`);
}
T.setGame({ time: 400 });
const fim = new Set();
for (let i = 0; i < 400; i++) { T.spawn(); fim.add(T.getEnemies().pop().type); }
checar(fim.has('elite'), `no fim da partida o elite deveria aparecer (veio ${[...fim].join('/')})`);

sec('10. o jogo não quebra sem os sheets do pack');
T.reset();
T.getEnemies().length = 0;
T.setGame({ spawn: 999, shoot: 999 });
T.spawn('soldier');
T.spawn('orc');
keys.d = true;
T.rodar(5);
keys.d = false;
for (const e of T.getEnemies()) { e.sheet = null; e.anim = null; }   // como se o PNG não tivesse vindo
T.rodar(5);
checar(true, 'o desenho de fallback dos inimigos quebrou');
checar(ui.gameover.classList.contains('hidden'), 'a tela de fim não deveria aparecer aqui');

/* -------------------------------------------------------------- resumo -- */
console.log(`\nchecagens: ${checagens}${puladas ? ` (+${puladas} puladas sem os sheets do pack)` : ''}`);
if (falhas.length) {
  console.log('FALHAS:');
  for (const f of falhas) console.log('  x', f);
  process.exit(1);
}
console.log(packOk
  ? 'tudo certo: soldado e orc nascem, animam, atacam e morrem no jogo.'
  : 'tudo certo: com os sheets ausentes, o comportamento dos inimigos segue correto e o desenho cai no fallback.');
