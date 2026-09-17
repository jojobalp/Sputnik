/**
 * falso_navegador.mjs — DOM, canvas, Image e fetch falsos para rodar o jogo
 * fora do navegador.
 *
 * Os testes de fumaça (`tools/smoke_*.mjs`) montam esse ambiente, carregam
 * assets.js + game.js de verdade dentro de uma VM e dirigem o jogo quadro a
 * quadro. O `requestAnimationFrame` fica sob controle do teste: cada chamada do
 * callback é um quadro, com o timestamp que o teste escolher.
 *
 * Uso:
 *   import { criarAmbiente, rodarJogo } from './apoio/falso_navegador.mjs';
 *   const { sandbox, desenhos } = criarAmbiente(raiz);
 *   rodarJogo(sandbox, raiz, 'globalThis.__t = { ... };');
 *
 * `desenhos` acumula cada drawImage — é como os testes conferem o que foi
 * desenhado (imagem, recorte e posição).
 */

import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import vm from 'node:vm';

export function criarAmbiente(raiz) {
  /* ------------------------------------------------------------ desenhos -- */
  const desenhos = [];          // cada drawImage registrado
  const elementos = new Map();
  const ouvintes = {};

  function classListFalsa(inicial = []) {
    const set = new Set(inicial);
    return {
      add: (...c) => c.forEach((x) => set.add(x)),
      remove: (...c) => c.forEach((x) => set.delete(x)),
      contains: (c) => set.has(c),
      toggle: (c) => (set.has(c) ? set.delete(c) : set.add(c)),
      _set: set,
    };
  }

  function ctxFalso() {
    const alvo = {
      drawImage(...args) { desenhos.push(args); },
      canvas: null,
    };
    return new Proxy(alvo, {
      get(t, k) {
        if (k in t) return t[k];
        if (k === 'then') return undefined;
        return () => {};
      },
      set(t, k, v) { t[k] = v; return true; },
    });
  }

  function canvasFalso() {
    const c = {
      width: 0, height: 0, style: {},
      classList: classListFalsa(),
      getContext: () => { const x = ctxFalso(); x.canvas = c; return x; },
      addEventListener() {}, removeEventListener() {},
    };
    return c;
  }

  function elementoFalso(id) {
    return {
      id, textContent: '', innerHTML: '', style: {}, onclick: null,
      classList: classListFalsa(['overlay', 'hidden'].includes(id) ? ['hidden'] : []),
      addEventListener() {}, removeEventListener() {},
    };
  }

  function elemento(sel) {
    if (!elementos.has(sel)) {
      elementos.set(sel, sel === '#game' ? canvasFalso() : elementoFalso(sel));
    }
    return elementos.get(sel);
  }

  const sandbox = {
    console,
    setTimeout, clearTimeout, setInterval, clearInterval,
    Promise, Math, Date, JSON, Object, Array, String, Number, Boolean, Error,
    devicePixelRatio: 1,
    innerWidth: 1280,
    innerHeight: 720,
    addEventListener: (tipo, fn) => { (ouvintes[tipo] ||= []).push(fn); },
    removeEventListener: () => {},
    document: {
      querySelector: (sel) => elemento(sel),
      querySelectorAll: () => [],
      createElement: (tag) => (tag === 'canvas' ? canvasFalso() : elementoFalso(tag)),
      addEventListener() {},
    },
  };

  // requestAnimationFrame controlado pelo teste: guarda o callback do próximo
  // quadro (o sandbox é o próprio global do contexto do VM, então
  // sandbox.__raf === globalThis.__raf lá dentro).
  sandbox.__raf = null;
  sandbox.requestAnimationFrame = (cb) => { sandbox.__raf = cb; return 1; };

  /* Image e fetch lendo os arquivos do repositório */
  class ImagemFalsa {
    constructor() { this.onload = null; this.onerror = null; this._src = ''; }
    set src(v) {
      this._src = v;
      const caminho = join(raiz, v);
      if (existsSync(caminho)) {
        const buf = readFileSync(caminho);
        this.width = buf.readUInt32BE(16);
        this.height = buf.readUInt32BE(20);
        queueMicrotask(() => this.onload && this.onload());
      } else {
        queueMicrotask(() => this.onerror && this.onerror());
      }
    }
    get src() { return this._src; }
  }
  sandbox.Image = ImagemFalsa;
  sandbox.fetch = async (url) => {
    const caminho = join(raiz, url);
    if (!existsSync(caminho)) return { ok: false, json: async () => { throw new Error('404'); } };
    return { ok: true, json: async () => JSON.parse(readFileSync(caminho, 'utf8')) };
  };

  return { sandbox, desenhos, elementos, ouvintes };
}

/* Carrega assets.js + game.js de verdade (`extra` é o trecho que expõe as
 * variáveis internas do jogo para o teste) dentro de um contexto de VM. */
export function rodarJogo(sandbox, raiz, extra = '') {
  const codigo = [
    readFileSync(join(raiz, 'assets.js'), 'utf8'),
    readFileSync(join(raiz, 'game.js'), 'utf8'),
  ].join('\n;\n');
  const ctx = vm.createContext(sandbox);
  vm.runInContext(codigo + '\n' + extra, ctx, { filename: 'jogo.js' });
  return ctx;
}
