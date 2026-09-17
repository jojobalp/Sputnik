'use strict';
/*
 * assets.js — camada de carregamento e animação dos sprites Aseprite.
 *
 * Lê os pares PNG+JSON exportados pelo Aseprite (Sprite/Characters/* para o
 * personagem, Sprite/Enemies/* para os inimigos) e o piso
 * (Sprite/Background/Floor.png). Cada sheet vira um objeto SpriteSheet com:
 *   - frames: retângulos na ordem correta (ordenados pelo sufixo numérico)
 *   - tags:   nome da animação -> { from, to }
 *   - durations: ms por frame (o Aseprite exporta frames de duração variável)
 *
 * Nenhuma função daqui lança exceção: se um asset falhar (rede, file://,
 * caminho errado), o jogo continua rodando com o desenho vetorial de fallback.
 */

const Assets = (() => {
  const BASE = 'Sprite/';

  /* `opcional` marca os sheets que vêm de um pack de terceiros e não entram no
   * repositório por licença: quem clona roda `python3 tools/importar_pack.py`
   * (veja art/tiny-rpg-pack/LEIA-ME.md) para gerá-los em Sprite/Enemies/. Sem
   * eles o jogo continua rodando, com o desenho vetorial de fallback nos tipos
   * correspondentes. */
  const MANIFEST = {
    background: BASE + 'Background/Floor.png',
    sheets: [
      // protagonista
      { key: 'bruxo',     png: BASE + 'Characters/bruxo.png',     json: BASE + 'Characters/bruxo.json'     },
      // inimigos
      { key: 'skeleton1', png: BASE + 'Enemies/skeleton1.png', json: BASE + 'Enemies/skeleton1.json' },
      { key: 'skeleton2', png: BASE + 'Enemies/skeleton2.png', json: BASE + 'Enemies/skeleton2.json' },
      // inimigos do pack Tiny RPG + a flecha do soldado (opcional)
      { key: 'soldier',   png: BASE + 'Enemies/soldier.png',   json: BASE + 'Enemies/soldier.json'   },   // opcional
      { key: 'orc',       png: BASE + 'Enemies/orc.png',       json: BASE + 'Enemies/orc.json'       },   // opcional
      { key: 'flecha',    png: BASE + 'Enemies/flecha.png',    json: BASE + 'Enemies/flecha.json'    },   // opcional
    ],
  };

  // Animações que tocam uma vez e param no último frame (as demais fazem loop).
  const ONE_SHOT = /^(.*_)?(death|death2|take_damage)$/;

  function loadImage(src) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);   // nunca rejeita
      img.src = src;
    });
  }

  async function loadJSON(src) {
    try {
      const r = await fetch(src);
      if (!r.ok) return null;
      return await r.json();
    } catch (e) {
      return null;
    }
  }

  class SpriteSheet {
    constructor(key, image, data) {
      this.key = key;
      this.image = image;
      this.ok = !!(image && data);
      this.frames = [];
      this.tags = {};
      this.durations = [];
      if (!this.ok) return;

      // Ordena pelos índices do nome "<base> N.aseprite" para não depender
      // da ordem de inserção das chaves no JSON.
      const entries = Object.entries(data.frames)
        .map(([name, f]) => {
          const m = name.match(/(\d+)\.aseprite$/);
          return { i: m ? +m[1] : this.frames.length, f };
        })
        .sort((a, b) => a.i - b.i);

      for (const { f } of entries) {
        this.frames.push({ x: f.frame.x, y: f.frame.y, w: f.frame.w, h: f.frame.h });
        this.durations.push(f.duration || 100);
      }

      for (const t of (data.meta && data.meta.frameTags) || []) {
        this.tags[t.name] = { from: t.from, to: t.to, loop: !ONE_SHOT.test(t.name) };
      }
    }

    hasTag(name) { return Object.prototype.hasOwnProperty.call(this.tags, name); }

    // Resolve um nome de tag com tolerância: aceita 'idle' -> 'skeleton1_idle'.
    resolveTag(name) {
      if (this.hasTag(name)) return name;
      const hit = Object.keys(this.tags).find((k) => k.endsWith('_' + name));
      return hit || null;
    }
  }

  // Estado de animação de uma entidade. Avança pelos durations reais do JSON.
  class Animation {
    constructor(sheet, tagName) {
      this.sheet = sheet;
      this.set(tagName);
    }

    /* this.tag  = nome resolvido no sheet (ex.: 'bruxo_attack')
     * this.name = nome pedido pelo jogo (ex.: 'attack') — use este para comparar */
    set(tagName) {
      const tag = this.sheet ? this.sheet.resolveTag(tagName) : null;
      this.name = tagName;
      if (!tag) { this.tag = null; this.frame = 0; this.t = 0; this.done = true; return; }
      if (this.tag === tag) return;
      this.tag = tag;
      const r = this.sheet.tags[tag];
      this.from = r.from; this.to = r.to; this.loop = r.loop;
      this.frame = r.from; this.t = 0; this.done = false;
    }

    get finished() { return this.done; }

    // Recomeça a animação atual (usado por golpes: ataque e reação a dano).
    restart() {
      if (this.tag == null) { this.done = true; return; }
      this.frame = this.from;
      this.t = 0;
      this.done = false;
    }

    advance(dtMs) {
      if (!this.sheet || this.done) return;
      this.t += dtMs;
      const r = this.sheet.tags[this.tag];
      let guard = 0;
      while (this.t >= this.sheet.durations[this.frame] && guard++ < 512) {
        this.t -= this.sheet.durations[this.frame];
        if (this.frame < r.to) {
          this.frame++;
        } else if (this.loop) {
          this.frame = r.from;
        } else {
          this.frame = r.to;
          this.done = true;
          break;
        }
      }
    }

    get rect() { return this.sheet.frames[this.frame]; }
  }

  const state = { background: null, sheets: {}, ready: false, anyFailed: false };

  async function load() {
    const [bg, ...sheetResults] = await Promise.all([
      loadImage(MANIFEST.background),
      ...MANIFEST.sheets.map(async (s) => {
        const [image, data] = await Promise.all([loadImage(s.png), loadJSON(s.json)]);
        return [s.key, new SpriteSheet(s.key, image, data)];
      }),
    ]);

    state.background = bg;
    for (const [key, sheet] of sheetResults) state.sheets[key] = sheet;
    state.anyFailed = !bg || sheetResults.some(([, s]) => !s.ok);
    state.ready = true;
    return state;
  }

  return {
    load,
    get background() { return state.background; },
    get ready() { return state.ready; },
    get anyFailed() { return state.anyFailed; },
    sheet: (key) => state.sheets[key] || null,
    Animation,
  };
})();
