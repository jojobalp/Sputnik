#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prancha_inimigos.py — prancha de conferência dos inimigos do pack no jogo.

Monta a imagem "como fica no jogo": o piso do projeto no fundo, o bruxo como
referência de tamanho e, para cada inimigo, o quadro parado e um quadro de golpe,
todos desenhados com a **escala e a âncora reais** usadas em game.js (o desenho
termina na linha dos pés, sombra de contato elíptica embaixo).

Serve para conferir tamanho relativo e encaixe no chão sem abrir o navegador.

Como as folhas dos inimigos vêm do pack Tiny RPG, a prancha gerada contém arte de
terceiros e por isso **não é versionada** (fica junto da arte, em
art/tiny-rpg-pack/). Este script, sim: ele só tem caminhos e números.

Uso:
    python3 tools/prancha_inimigos.py --saida art/tiny-rpg-pack/previa-no-jogo.png
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, Tuple

from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)


# --------------------------------------------------------------------------- #
# números do jogo (lidos de game.js para a prancha não mentir)
# --------------------------------------------------------------------------- #
def escalas_do_jogo(caminho: str) -> Tuple[float, int, Dict[str, Tuple[float, int]]]:
    """(escala do bruxo, r do bruxo, {tipo: (escala, r)}) a partir de game.js."""
    texto = open(caminho, encoding='utf-8').read()
    m = re.search(r'const PLAYER = \{ r: ([\d.]+), scale: ([\d.]+)', texto)
    if not m:
        raise SystemExit('não achei o PLAYER em game.js')
    r_bruxo, escala_bruxo = int(float(m.group(1))), float(m.group(2))

    tipos: Dict[str, Tuple[float, int]] = {}
    # cada tipo pode ocupar mais de uma linha: pego do nome até a chave de fechamento
    for m in re.finditer(r'^\s+(\w+):\s+\{(.*?)\}', texto, re.M | re.S):
        corpo = m.group(2)
        e = re.search(r"sheet: '(\w+)'", corpo)
        s = re.search(r'scale: ([\d.]+)', corpo)
        r = re.search(r'\br: (\d+)', corpo)
        if e and s and r:
            tipos[e.group(1)] = (float(s.group(1)), int(r.group(1)))
    if 'soldier' not in tipos or 'orc' not in tipos:
        raise SystemExit('não achei os tipos soldier/orc em ENEMY_TYPES')
    return escala_bruxo, r_bruxo, tipos


# --------------------------------------------------------------------------- #
# desenho
# --------------------------------------------------------------------------- #
def abrir_sheet(png: str, js: str):
    """(função que devolve o quadro de uma tag, altura da célula)."""
    dados = json.load(open(js, encoding='utf-8'))
    img = Image.open(png).convert('RGBA')
    ordem = list(dados['frames'])
    tags = {t['name']: (t['from'], t['to']) for t in dados['meta']['frameTags']}

    def quadro(tag: str, i: int = 0) -> Image.Image:
        alvo = next((k for k in tags if k.endswith('_' + tag)), None)
        if alvo is None:
            raise SystemExit(f'{js}: não achei a tag {tag}')
        a, b = tags[alvo]
        r = dados['frames'][ordem[min(a + i, b)]]['frame']
        return img.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h']))

    return quadro, dados['meta']['size']['h']


def fonte(tamanho: int):
    for caminho in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        if os.path.exists(caminho):
            return ImageFont.truetype(caminho, tamanho)
    return ImageFont.load_default()


def montar(saida: str, largura: int, altura: int) -> None:
    escala_bruxo, r_bruxo, tipos = escalas_do_jogo(os.path.join(RAIZ, 'game.js'))
    casa = os.path.join(RAIZ, 'art/tiny-rpg-pack/jogo')
    bruxo_q, _ = abrir_sheet(os.path.join(RAIZ, 'Sprite/Characters/bruxo.png'),
                             os.path.join(RAIZ, 'Sprite/Characters/bruxo.json'))
    soldado_q, _ = abrir_sheet(os.path.join(casa, 'soldier.png'), os.path.join(casa, 'soldier.json'))
    orc_q, _ = abrir_sheet(os.path.join(casa, 'orc.png'), os.path.join(casa, 'orc.json'))

    tela = Image.new('RGBA', (largura, altura), (10, 20, 15, 255))
    piso = Image.open(os.path.join(RAIZ, 'Sprite/Background/Floor.png')).convert('RGBA')
    for i in range(0, largura, piso.width):
        for j in range(0, altura, piso.height):
            tela.alpha_composite(piso, (i, j))
    tela.alpha_composite(Image.new('RGBA', (largura, altura), (7, 17, 12, 77)))  # escurecimento do jogo
    des = ImageDraw.Draw(tela)
    f_titulo, f_legenda = fonte(22), fonte(15)

    def poe(quadro: Image.Image, x: float, pes: float, escala: float, r: int, face: int = 1):
        des.ellipse([x - r * .95, pes - r * .38, x + r * .95, pes + r * .38], fill=(4, 10, 7, 89))
        im = quadro.resize((int(quadro.width * escala), int(quadro.height * escala)), Image.NEAREST)
        if face < 0:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        tela.alpha_composite(im, (int(x - im.width / 2), int(pes - im.height)))

    des.text((28, 20), 'Soldado e orc no jogo — escala e âncora dos pés', font=f_titulo, fill=(235, 240, 235))
    des.text((28, 48), 'imagem gerada por tools/prancha_inimigos.py a partir dos números de game.js',
             font=f_legenda, fill=(190, 205, 195))

    linha = altura - 190
    des.line([40, linha, largura - 40, linha], fill=(255, 255, 255, 70))

    # bruxo: parado em cima, golpe embaixo (referência de tamanho)
    poe(bruxo_q('idle'), 210, linha - 120, escala_bruxo, r_bruxo)
    poe(bruxo_q('attack', 8), 210, linha - 10, escala_bruxo, r_bruxo)
    des.text((150, linha + 10), f'bruxo {escala_bruxo}× (protagonista)', font=f_legenda, fill=(226, 214, 255))

    # soldado: parado e no golpe, virado para a esquerda
    e_sold, r_sold = tipos['soldier']
    poe(soldado_q('idle'), 640, linha - 120, e_sold, r_sold)
    poe(soldado_q('attack', 7), 640, linha - 10, e_sold, r_sold, face=-1)
    des.text((530, linha + 10), f'soldado {e_sold}× — atira flecha (r {r_sold})',
             font=f_legenda, fill=(200, 220, 240))

    # a flecha, girando como o jogo desenha
    flecha = Image.open(os.path.join(casa, 'flecha.png')).convert('RGBA')
    lado = int(flecha.width * 1.7)
    for k, ang in enumerate((180, 160)):
        im = flecha.resize((lado, lado), Image.NEAREST).rotate(ang, resample=Image.NEAREST,
                                                               center=(lado / 2, lado / 2))
        tela.alpha_composite(im, (330 + k * 130, linha - 105))

    # orc: parado e golpeando
    e_orc, r_orc = tipos['orc']
    poe(orc_q('idle'), 1060, linha - 120, e_orc, r_orc)
    poe(orc_q('attack', 3), 1060, linha - 10, e_orc, r_orc, face=-1)
    legenda_orc = f'orc {e_orc}× — brutamontes (r {r_orc})'
    des.text((largura - 40 - des.textlength(legenda_orc, font=f_legenda), linha + 10), legenda_orc,
             font=f_legenda, fill=(210, 230, 190))

    os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
    tela.convert('RGB').save(saida)
    print(f'{saida} ({largura}x{altura}) — bruxo {escala_bruxo}×, '
          f'soldado {e_sold}×, orc {e_orc}×')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Prancha de conferência dos inimigos no jogo.')
    ap.add_argument('--saida', default='art/tiny-rpg-pack/previa-no-jogo.png')
    ap.add_argument('--largura', type=int, default=1280)
    ap.add_argument('--altura', type=int, default=720)
    args = ap.parse_args(argv)
    montar(args.saida, args.largura, args.altura)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
