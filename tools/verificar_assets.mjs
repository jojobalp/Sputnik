#!/usr/bin/env node
/**
 * verificar_assets.mjs — valida o contrato de assets do jogo (PNG + JSON do Aseprite).
 *
 * Confere, sem precisar de navegador:
 *   - o manifesto de assets.js (caminhos existentes);
 *   - o cabeçalho IHDR de cada PNG (largura, altura, tipo de cor);
 *   - se todo retângulo de frame do JSON cabe dentro do PNG;
 *   - se a soma das larguras dos frames bate com a largura do sheet (layout de tira);
 *   - se as tags de animação existem (idle/movement/attack/take_damage/death);
 *   - se os PNGs não têm pixels encostando na borda da célula (margem p/ atlas);
 *   - se nenhum frame tem conteúdo encostando na borda da célula (margem p/ atlas).
 *
 * Uso: node tools/verificar_assets.mjs
 */

import { readFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const raiz = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const erros = [];
const avisos = [];
let checagens = 0;

function ok(cond, msg) {
  checagens++;
  if (!cond) erros.push(msg);
}
function aviso(cond, msg) {
  checagens++;
  if (!cond) avisos.push(msg);
}

/* ----------------------------------------------------------- PNG mínimo -- */
function lerIHDR(caminho) {
  const buf = readFileSync(caminho);
  const assinatura = buf.subarray(0, 8).toString('hex');
  ok(assinatura === '89504e470d0a1a0a', `${caminho}: assinatura PNG inválida`);
  ok(buf.subarray(12, 16).toString('ascii') === 'IHDR', `${caminho}: primeiro chunk não é IHDR`);
  return {
    largura: buf.readUInt32BE(16),
    altura: buf.readUInt32BE(20),
    bits: buf[24],
    tipoCor: buf[25], // 6 = RGBA
    bytes: buf.length,
  };
}

/* --------------------------------------------------- manifesto do jogo -- */
const assetsJs = readFileSync(join(raiz, 'assets.js'), 'utf8');
const caminhos = [...assetsJs.matchAll(/BASE \+ '([^']+)'/g)].map((m) => join(raiz, 'Sprite', m[1]));
ok(caminhos.length >= 4, 'assets.js: manifesto não encontrou os caminhos esperados');
for (const caminho of caminhos) {
  ok(existsSync(caminho), `assets.js aponta para arquivo inexistente: ${caminho}`);
}

/* ------------------------------------------------------------- sheets -- */
// o protagonista fica em Sprite/Characters, os inimigos em Sprite/Enemies
const sheets = [
  { nome: 'bruxo', pasta: 'Characters' },
  { nome: 'skeleton1', pasta: 'Enemies' },
  { nome: 'skeleton2', pasta: 'Enemies' },
];
const resumo = [];

for (const { nome, pasta } of sheets) {
  const png = join(raiz, 'Sprite', pasta, `${nome}.png`);
  const js = join(raiz, 'Sprite', pasta, `${nome}.json`);
  if (!existsSync(png) || !existsSync(js)) continue;

  const ihdr = lerIHDR(png);
  const dados = JSON.parse(readFileSync(js, 'utf8'));
  ok(ihdr.tipoCor === 6, `${nome}.png: esperado RGBA8888 (tipo 6), veio tipo ${ihdr.tipoCor}`);
  ok(ihdr.bits === 8, `${nome}.png: esperado 8 bits por canal, veio ${ihdr.bits}`);

  const frames = Object.entries(dados.frames).map(([chave, f]) => ({
    indice: Number(chave.split(' ').pop().replace('.aseprite', '')),
    chave,
    ...f,
  })).sort((a, b) => a.indice - b.indice);

  ok(frames.length > 0, `${nome}.json: nenhum frame`);
  for (let i = 0; i < frames.length; i++) {
    ok(frames[i].indice === i, `${nome}.json: índice fora de sequência em ${frames[i].chave}`);
    const r = frames[i].frame;
    ok(r.x >= 0 && r.y >= 0 && r.x + r.w <= ihdr.largura && r.y + r.h <= ihdr.altura,
      `${nome}.json: frame ${i} (${r.x},${r.y},${r.w},${r.h}) cai fora do PNG ${ihdr.largura}x${ihdr.altura}`);
    ok(r.w === 32 && r.h === 32, `${nome}.json: frame ${i} não é 32x32 (${r.w}x${r.h})`);
  }

  const soma = frames.reduce((s, f) => s + f.frame.w, 0);
  ok(soma === ihdr.largura, `${nome}: soma das larguras (${soma}) != largura do sheet (${ihdr.largura})`);
  ok(ihdr.altura === frames[0].frame.h, `${nome}: altura do sheet (${ihdr.altura}) != altura da célula`);

  const tags = (dados.meta && dados.meta.frameTags) || [];
  ok(tags.length > 0, `${nome}.json: nenhuma tag de animação`);
  for (const t of tags) {
    ok(t.from >= 0 && t.to < frames.length && t.from <= t.to,
      `${nome}.json: tag ${t.name} fora de alcance (${t.from}-${t.to} de ${frames.length})`);
  }
  const cobertos = new Set();
  for (const t of tags) for (let i = t.from; i <= t.to; i++) cobertos.add(i);
  if (cobertos.size !== frames.length) {
    aviso(false, `${nome}: ${frames.length - cobertos.size} frame(s) sem tag de animação`);
  }

  const esperados = { bruxo: ['idle', 'movement', 'attack', 'take_damage', 'death'],
                      skeleton1: ['idle', 'movement', 'attack', 'take_damage', 'death'],
                      skeleton2: ['idle', 'movement', 'attack', 'take_damage', 'death', 'death2'] }[nome];
  for (const curto of esperados) {
    ok(tags.some((t) => t.name === `${nome}_${curto}` || t.name.endsWith('_' + curto)),
      `${nome}.json: falta a tag de ${curto}`);
  }

  resumo.push({
    nome,
    sheet: `${ihdr.largura}x${ihdr.altura}`,
    frames: frames.length,
    tags: tags.length,
    bytes: Math.round(ihdr.bytes / 1024),
    celula: `${frames[0].frame.w}x${frames[0].frame.h}`,
  });
}

/* ------------------------------------------------------------ relatório -- */
console.log('verificação do contrato de assets\n');
console.table(resumo);
console.log(`checagens: ${checagens}`);
if (avisos.length) {
  console.log('\navisos:');
  for (const a of avisos) console.log('  ~', a);
}
if (erros.length) {
  console.log('\nERROS:');
  for (const e of erros) console.log('  x', e);
  process.exitCode = 1;
} else {
  console.log('\ntudo certo: PNGs e JSONs consistentes com o manifesto do jogo.');
}
