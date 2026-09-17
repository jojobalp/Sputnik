#!/usr/bin/env node
/**
 * smoke_personagem.mjs — teste de fumaça do protagonista, sem navegador.
 *
 * Monta um DOM e um canvas falsos, carrega assets.js + game.js de verdade e
 * dirige o jogo quadro a quadro, verificando o que o bruxo faz:
 *
 *   - o sheet Sprite/Characters/bruxo.* carrega e tem todas as tags;
 *   - parado fica em `idle`, andando fica em `movement` e vira para o lado certo;
 *   - ao atacar toca `attack`, vira para o alvo e a magia sai da ponta do cajado;
 *   - ao levar dano toca `take_damage` (e o dano entra normalmente no HUD);
 *   - ao morrer toca `death` e só então aparece a tela de fim de jogo;
 *   - o desenho usa o sheet do bruxo (e cai no fallback vetorial se faltar).
 *
 * Uso: node tools/smoke_personagem.mjs
 */

import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { criarAmbiente, rodarJogo } from './apoio/falso_navegador.mjs';

const raiz = resolve(dirname(fileURLToPath(import.meta.url)), '..');

/* ------------------------------------------------------------ utilidades -- */
const falhas = [];
let checagens = 0;
function checar(cond, msg) {
  checagens++;
  if (!cond) falhas.push(msg);
}
function titulo(t) { console.log(`\n${t}`); }

/* ------------------------------------------------ stubs de DOM e canvas -- */
/* O ambiente falso (DOM, canvas, Image, fetch) e o carregamento do jogo moram
 * em tools/apoio/falso_navegador.mjs, compartilhados com o teste dos inimigos. */
const { sandbox, desenhos } = criarAmbiente(raiz);

/* ----------------------------------------------------- testes dentro do jogo -- */
const testes = `
(async () => {
  const esperar = () => new Promise((r) => setTimeout(r, 0));
  for (let i = 0; i < 5; i++) await esperar();      // deixa o Assets.load terminar

  const quadro = (ms) => { const cb = globalThis.__raf; globalThis.__raf = null; cb(ms); };
  let t = 1000;
  const rodar = (n = 1, passo = 40) => { for (let i = 0; i < n; i++) { t += passo; quadro(t); } };

  globalThis.__t = {
    Assets, player, game, enemies, shots, keys, ui, update, draw, shoot, spawn,
    rodar,
    setGame: (campos) => Object.assign(game, campos),
    reset, getPlayer: () => player, getGame: () => game,
    getEnemies: () => enemies, getShots: () => shots,
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

sec('1. carregamento do personagem');
const sheet = Assets.sheet('bruxo');
ver(!!sheet && sheet.ok, 'sheet bruxo não carregou');
ver(!!sheet && !!sheet.image, 'imagem do bruxo ausente');
ver(sheet.image.width === 1568 && sheet.image.height === 32,
  `tamanho inesperado do sheet: ${sheet.image && sheet.image.width}x${sheet.image && sheet.image.height}`);
for (const tag of ['idle', 'movement', 'attack', 'take_damage', 'death']) {
  ver(sheet.hasTag(sheet.resolveTag(tag)), `tag "${tag}" não encontrada no bruxo`);
}
ver(Assets.sheet('skeleton1').ok && Assets.sheet('skeleton2').ok, 'sheets dos inimigos não carregaram');
ver(!Assets.sheet('vampire'), 'sheet vampire não deveria mais existir');

sec('2. estado parado e andando');
T.reset();
// sem inimigos e sem tiro: isola o estado idle/movement (o cajado atira sozinho
// e, com alvo na tela, o bruxo entra em ataque imediatamente)
T.setGame({ spawn: 999, shoot: 999 });
T.getEnemies().length = 0;
desenhos.length = 0;
T.rodar(3);
ver(T.getPlayer().anim.tag.endsWith('idle'), `parado deveria tocar idle, tocou ${T.getPlayer().anim.tag}`);
ver(desenhos.some((d) => d[0] === sheet.image), 'o bruxo não foi desenhado a partir do sheet');

keys.d = true;
T.rodar(4);
ver(T.getPlayer().anim.tag.endsWith('movement'), `andando deveria tocar movement, tocou ${T.getPlayer().anim.tag}`);
ver(T.getPlayer().face === 1, 'andando para a direita deveria estar virado para a direita');
keys.d = false; keys.a = true;
T.rodar(4);
ver(T.getPlayer().face === -1, 'andando para a esquerda deveria estar virado para a esquerda');
keys.a = false;
T.rodar(2);
ver(T.getPlayer().anim.tag.endsWith('idle'), 'ao soltar as teclas deveria voltar para idle');

sec('3. ataque do cajado');
T.reset();
T.setGame({ spawn: 999, shoot: 0 });
T.getEnemies().length = 0;
T.spawn();
const alvo = T.getEnemies()[T.getEnemies().length - 1];
alvo.x = T.getPlayer().x + 200; alvo.y = T.getPlayer().y;
T.rodar(1);                                    // o tiro sai neste quadro
ver(T.getPlayer().anim.tag.endsWith('attack'), `deveria tocar attack, tocou ${T.getPlayer().anim.tag}`);
ver(T.getPlayer().face === 1, 'deveria virar para o alvo à direita');
ver(T.getShots().length >= 1, 'nenhum projétil foi criado');
if (T.getShots().length) {
  const s = T.getShots()[0], p = T.getPlayer();
  const d = Math.hypot(s.x - p.x, s.y - p.y);
  ver(d > 10, `a magia deveria sair da ponta do cajado, saiu a ${d.toFixed(1)}px do centro`);
}
alvo.x = T.getPlayer().x - 200;
T.setGame({ shoot: 0 });
T.rodar(1);
ver(T.getPlayer().face === -1, 'deveria virar para o alvo à esquerda');

sec('4. levar dano');
T.reset();
T.setGame({ shield: 0, hp: 100, spawn: 999, shoot: 999 });
T.spawn();
const e = T.getEnemies()[T.getEnemies().length - 1];
e.x = T.getPlayer().x; e.y = T.getPlayer().y; e.hp = 5;
T.rodar(1);
ver(T.getGame().hp === 82, `hp deveria cair para 82, ficou ${T.getGame().hp}`);
ver(T.getPlayer().anim.tag.endsWith('take_damage'), `deveria tocar take_damage, tocou ${T.getPlayer().anim.tag}`);
T.rodar(1);
ver(T.getPlayer().anim.tag.endsWith('take_damage'), 'take_damage deveria continuar até o fim');

sec('5. morte e fim de jogo');
T.reset();
T.setGame({ shield: 0, hp: 10, spawn: 999, shoot: 999 });
T.spawn();
const assassino = T.getEnemies()[T.getEnemies().length - 1];
assassino.x = T.getPlayer().x; assassino.y = T.getPlayer().y; assassino.hp = 5;
T.rodar(1);
ver(T.getPlayer().dying, 'ao zerar o hp o bruxo deveria entrar em morte');
ver(T.getPlayer().anim.tag.endsWith('death'), `deveria tocar death, tocou ${T.getPlayer().anim.tag}`);
ver(ui.gameover.classList.contains('hidden'), 'a tela de fim não deveria aparecer antes da animação');
T.rodar(60, 40);                                // ~2,4 s: morte tem 1,4 s
ver(T.getPlayer().dead, 'o bruxo deveria ter terminado a morte');
ver(!ui.gameover.classList.contains('hidden'), 'a tela de fim deveria aparecer depois da animação');
ver(!!ui.finalStats.textContent, 'o resumo final deveria ser preenchido');

sec('6. reinício');
ui.restart.onclick();
ver(!T.getPlayer().dying && !T.getPlayer().dead, 'o reinício deveria limpar o estado de morte');
ver(T.getGame().hp === 100, 'o reinício deveria devolver o hp cheio');
ver(T.getPlayer().anim.tag.endsWith('idle'), 'após reiniciar o bruxo deveria estar em idle');
T.rodar(3);

sec('7. fallback quando o sprite não carrega');
const guardado = Assets.sheet('bruxo');
const p = T.getPlayer();
p.sheet = null; p.anim = null;
T.rodar(2);                                     // não pode lançar exceção
ver(true, 'o desenho de fallback quebrou');
p.sheet = guardado;
p.anim = new Assets.Animation(guardado, 'idle');

/* -------------------------------------------------------------- resumo -- */
console.log(`\nchecagens: ${checagens}`);
if (falhas.length) {
  console.log('FALHAS:');
  for (const f of falhas) console.log('  x', f);
  process.exit(1);
}
console.log('tudo certo: o bruxo carrega, anima, ataca, reage ao dano e morre com animação.');
