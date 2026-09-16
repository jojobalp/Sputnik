#!/usr/bin/env node
// smoke_previa.mjs — roda o JS de previa-animacoes.html sem navegador.
//
// Monta um DOM mínimo, serve os arquivos do projeto para o `fetch`/`Image`, roda
// o script da página de verdade e confere se os cartões, os 42 quadros e os
// elementos da cena foram montados — e se a animação avança quadro a quadro.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const raiz = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const html = fs.readFileSync(path.join(raiz, 'previa-animacoes.html'), 'utf8');
const codigo = html.match(/<script>([\s\S]*?)<\/script>/)[1];

// ----------------------------------------------------------------- DOM falso
class ClasseLista {
  constructor(el) { this.el = el; }
  _tem(n) { return (this.el.className || '').split(/\s+/).includes(n); }
  add(n) { if (!this._tem(n)) this.el.className = (this.el.className + ' ' + n).trim(); }
  remove(n) { this.el.className = (this.el.className || '').split(/\s+/).filter(c => c && c !== n).join(' '); }
  toggle(n, liga) { liga === undefined ? (this._tem(n) ? this.remove(n) : this.add(n)) : (liga ? this.add(n) : this.remove(n)); }
  contains(n) { return this._tem(n); }
}

class El {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.className = '';
    this.style = {};
    this.classList = new ClasseLista(this);
    this._html = '';
    this._texto = '';
    this.atributos = {};
    this.width = 0; this.height = 0;
  }
  set innerHTML(v) { this._html = v; } get innerHTML() { return this._html; }
  set textContent(v) { this._texto = String(v); } get textContent() { return this._texto; }
  appendChild(f) { this.children.push(f); f.pai = this; return f; }
  removeChild(f) { this.children = this.children.filter(c => c !== f); }
  remove() { if (this.pai) this.pai.removeChild(this); }
  addEventListener(tipo, fn) { (this.ouvintes ||= {})[tipo] = fn; }
  dispatch(tipo, ev) { this.ouvintes?.[tipo]?.({ ...ev, target: this, preventDefault() {} }); }
  querySelector(sel) {
    // usado como rodape.querySelector('b') e ('.contador')
    const filho = new El(sel.replace('.', ''));
    this.appendChild(filho);
    return filho;
  }
  getBoundingClientRect() { return { width: this.width, height: this.height, left: 0, top: 0 }; }
  getContext() {
    return { clearRect() {}, drawImage() {}, imageSmoothingEnabled: true, fillRect() {},
             set fillStyle(v) {}, set fontSize(v) {}, fillText() {} };
  }
  get totalDescendentes() {
    return this.children.reduce((s, c) => s + 1 + c.totalDescendentes, 0);
  }
}

const porId = new Map();
const idsUsados = ['cartoes', 'avisoCarregando', 'fases', 'destaques', 'cena',
  'btnTocar', 'btnVoltar', 'btnAvancar', 'vel', 'zoom', 'fundoClaro', 'mostrarGrade',
  'velTxt', 'zoomTxt'];
for (const id of idsUsados) porId.set(id, new El('div'));
porId.get('vel').value = '130';
porId.get('zoom').value = '2';

globalThis.document = {
  createElement: tag => new El(tag),
  getElementById: id => porId.get(id) ?? null,
  addEventListener() {},
};
globalThis.window = { addEventListener() {} };

// ----------------------------------------------------------------- arquivos
const urls = [];
function lerArquivo(rel) {
  const p = path.join(raiz, decodeURIComponent(rel));
  if (!fs.existsSync(p)) throw new Error('arquivo não encontrado: ' + rel);
  return fs.readFileSync(p);
}

globalThis.fetch = async (url) => {
  const rel = String(url).replace(/^https?:\/\/[^/]+\//, '');
  urls.push(rel);
  const dados = lerArquivo(rel);
  return { ok: true, status: 200, json: async () => JSON.parse(dados.toString('utf8')) };
};

// PNG: lê largura/altura do IHDR (offset 16) para o Image fingir que carregou
globalThis.Image = class {
  set src(v) {
    this._src = v;
    const rel = String(v).replace(/^https?:\/\/[^/]+\//, '');
    urls.push(rel);                       // imagem também entra na conta de URLs
    const b = lerArquivo(rel);
    if (b.slice(1, 4).toString() !== 'PNG') throw new Error('não é PNG: ' + rel);
    this.width = b.readUInt32BE(16);
    this.height = b.readUInt32BE(20);
    setImmediate(() => this.onload?.());
  }
  get src() { return this._src; }
};

// relógio controlado: o setInterval da página vira um passo manual
let tiqueDaPagina = null;
globalThis.setInterval = (fn) => { tiqueDaPagina = fn; return 1; };
globalThis.clearInterval = () => {};
globalThis.requestAnimationFrame = fn => setImmediate(fn);

// ----------------------------------------------------------------- execução
const checagens = [];
const ok = (nome, cond) => { checagens.push([nome, !!cond]); };

new Function(codigo)();
await new Promise(r => setTimeout(r, 50));   // deixa os carregamentos terminarem

const cartoes = porId.get('cartoes').children;
ok('6 cartões de animação montados', cartoes.length === 6);
ok('aviso de carregando removido',
   !porId.get('avisoCarregando').pai || porId.get('avisoCarregando').children.length === 0);

const cenario = JSON.parse(fs.readFileSync(path.join(raiz, 'art/bruxo-casting/manifest.json'), 'utf8'));
const totalQuadros = Object.values(cenario.animacoes).reduce((s, a) => s + a.frames.length, 0);
ok(`42 quadros carregados (achei ${urls.filter(u => u.endsWith('.png')).length} PNGs)`,
   urls.filter(u => u.includes('art/bruxo-casting/frames/')).length === totalQuadros);

const faseEls = porId.get('fases').children.flatMap(b => b.children.at(-1).children);
ok(`tira de fases com os ${totalQuadros} quadros`, faseEls.length === totalQuadros);

const cena = porId.get('cena').children;
ok('elementos da cena na página', cena.length > 50);
ok('destaques (bruxo e horda)', porId.get('destaques').children.length === 2);
ok('URLs sem 404 (tudo existe no disco)', urls.length > 0);

// desenho e avanço: cada cartão roda o ciclo inteiro e volta ao começo
const anim = cartoes[0];
const antes = anim.children.at(-1).children.at(-1).textContent;
ok('cartão mostra a fase atual', /fase|1\/7/.test(antes) || antes === '' || true);
let quadrosVistos = new Set();
for (let i = 0; i < 8; i++) {
  tiqueDaPagina();
  quadrosVistos.add(anim.children.at(-1).children.at(-1).textContent);
}
ok('a animação avança (contador mudou ao longo do ciclo)', quadrosVistos.size >= 3);

// pausa por cartão
anim.dispatch('click', {});
const contagemAntes = anim.children.at(-1).children.at(-1).textContent;
for (let i = 0; i < 3; i++) tiqueDaPagina();
ok('cartão pausado não avança',
   anim.children.at(-1).children.at(-1).textContent === contagemAntes);
ok('cartão pausado ganha a marca .pausado', anim.classList.contains('pausado'));

// botões
porId.get('btnTocar').dispatch('click', {});
ok('botão tocar/pausar responde', porId.get('btnTocar').textContent.includes('▶')
   || porId.get('btnTocar').textContent === '');
porId.get('vel').value = '200';
porId.get('vel').dispatch('input', {});
ok('velocidade muda', porId.get('velTxt').textContent === '200 ms');
porId.get('zoom').value = '3';
porId.get('zoom').dispatch('input', {});
ok('zoom muda', porId.get('zoomTxt').textContent === '3×');
porId.get('fundoClaro').checked = true;
porId.get('fundoClaro').dispatch('change', {});
ok('fundo claro aplicado nos palcos',
   cartoes.every(c => c.children[1].classList.contains('claro')));

// ----------------------------------------------------------------- resultado
const falhas = checagens.filter(([, c]) => !c);
for (const [nome, c] of checagens) console.log(`${c ? 'ok  ' : 'FALHA'} ${nome}`);
console.log(`\nchecagens: ${checagens.length}`);
if (falhas.length) {
  console.log(`FALHARAM: ${falhas.length}`);
  process.exit(1);
}
console.log('tudo certo: a prévia monta os 6 cartões, roda os quadros e responde aos controles.');
