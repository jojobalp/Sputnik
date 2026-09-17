#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
teste_prancha_sintetica.py — gera uma prancha parecida com as de referência
(grade, rótulos de texto, título, moldura e coluna de referência) para testar a
extração sem depender de arte de verdade.

Uso:
    python3 tools/teste_prancha_sintetica.py --saida /tmp/prancha.jpg --jpg --qualidade 88
"""

from __future__ import annotations

import argparse
from typing import List

from PIL import Image, ImageDraw

ROTULOS = ['IDLE S', 'CHARGE S', 'CHARGE S', 'CAST S', 'RELEASE', 'TRAVEL', 'RECOVERY']
CINZA_FUNDO = (233, 235, 237)
CINZA_LINHA = (176, 178, 181)
TINTA = (24, 22, 20)

def desenhar(dr: ImageDraw.ImageDraw, cx: int, base_y: int, escala: float, semente: int) -> None:
    """Boneco simples (capuz + manto + cajado) com variação para parecer animação."""
    import math
    r = int(26 * escala)
    corpo_h = int(46 * escala)
    topo = base_y - corpo_h
    # manto
    dr.polygon([(cx - r, base_y), (cx + r, base_y), (cx + int(r * .55), topo),
                (cx - int(r * .55), topo)], fill=(46, 42, 72))
    # capuz
    dr.ellipse([cx - int(r * .62), topo - int(r * .5), cx + int(r * .62), topo + int(r * .55)],
               fill=(58, 52, 92))
    # cajado
    ang = math.sin(semente * 0.9) * 0.5
    bx = cx + int(r * 1.25)
    dr.line([(bx, base_y), (bx + int(ang * 16), topo - int(r * .3))], fill=(150, 120, 90),
            width=max(2, int(2 * escala)))
    # magia na ponta, variando de tamanho (charge -> release)
    raio = int((4 + (semente % 4) * 3) * escala)
    mx = bx + int(ang * 16)
    my = topo - int(r * .3)
    dr.ellipse([mx - raio, my - raio, mx + raio, my + raio], fill=(250, 250, 255))
    dr.ellipse([mx - raio - 3, my - raio - 3, mx + raio + 3, my + raio + 3], outline=(150, 90, 230), width=2)
    # botas
    dr.rectangle([cx - int(r * .5), base_y - int(5 * escala), cx - 2, base_y], fill=(30, 26, 24))
    dr.rectangle([cx + 2, base_y - int(5 * escala), cx + int(r * .5), base_y], fill=(30, 26, 24))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Gera uma prancha sintética para testar a extração.')
    ap.add_argument('--saida', default='/tmp/prancha_sintetica.png')
    ap.add_argument('--jpg', action='store_true', help='salva como JPEG (reproduz artefatos)')
    ap.add_argument('--qualidade', type=int, default=88)
    ap.add_argument('--linhas', type=int, default=6)
    ap.add_argument('--colunas', type=int, default=7)
    args = ap.parse_args(argv)

    cw, ch = 150, 102          # célula com o rótulo embaixo
    margem, topo = 18, 54
    ref_w = 140
    W = margem * 2 + cw * args.colunas + ref_w
    H = topo + ch * args.linhas + margem
    img = Image.new('RGB', (W, H), (255, 255, 255))
    dr = ImageDraw.Draw(img)

    dr.text((margem + 6, 16), 'TOP-DOWN WIZARD CASTING ANIMATION SPRITESHEET: LIGHTNING BALL',
            fill=TINTA)
    # coluna de referência (à direita, separada por uma moldura)
    rx = margem + cw * args.colunas + 10
    dr.rectangle([rx, topo, rx + ref_w - 20, topo + ch * args.linhas - 10], outline=CINZA_LINHA)

    for lin in range(args.linhas):
        for col in range(args.colunas):
            x0 = margem + col * cw
            y0 = topo + lin * ch
            dr.rectangle([x0, y0, x0 + cw - 1, y0 + ch - 1], fill=CINZA_FUNDO, outline=CINZA_LINHA)
            desenhar(dr, x0 + cw // 2 - 6, y0 + ch - 22, 1.0, lin * args.colunas + col)
            rotulo = ROTULOS[col] if lin % 3 else ROTULOS[col]
            dr.text((x0 + 12, y0 + ch - 18), rotulo, fill=TINTA)
            dr.text((x0 + 6, y0 + 4), f'{lin*10+col}', fill=(90, 90, 90))
        # referência à direita
        y0 = topo + lin * ch
        dr.rectangle([rx, y0, rx + ref_w - 20, y0 + ch - 10], fill=CINZA_FUNDO, outline=CINZA_LINHA)
        desenhar(dr, rx + (ref_w - 20) // 2, y0 + ch - 30, 0.9, lin + 99)
        dr.text((rx + 8, y0 + ch - 24), 'Reference', fill=TINTA)

    if args.jpg:
        img.save(args.saida, quality=args.qualidade, subsampling=2)
    else:
        img.save(args.saida)
    print(f'gerado {args.saida} {img.size}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
