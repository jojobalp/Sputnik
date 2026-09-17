#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extrair_cena.py — separa uma ilustração de cena em elementos soltos.

Feito para as pranchas "de cena" (terreno + mobs + itens numa só imagem): aqui
não existe grade e nem sempre existe animação — o que se quer é cada desenho
solto em PNG com fundo transparente, para virar asset.

Como funciona:
    1. o fundo (branco/ chapado) vira transparência, com alfa suave na borda;
    2. o que sobrou é agrupado em massas (componentes conexos). Uma abertura
       opcional quebra as pontes finas que grudam um desenho no outro;
    3. massas grandes demais (aglomerado de mobs) podem ser separadas por
       marcadores — cada pixel vai para o marcador mais próximo;
    4. cada massa grande o bastante vira um PNG, com folga, numa pasta por zona;
    5. saem também um manifesto e um mapa numerado para conferência.

Uso:
    python3 tools/extrair_cena.py --entrada art/referencia/cena.png \\
        --saida-dir art/cena --zonas "0:400=itens" "400:1050=cena" "1050:=mobs"
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Dict, List, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

# --------------------------------------------------------------------------- #
# parâmetros
# --------------------------------------------------------------------------- #
LUM_FUNDO = 236          # abaixo disto o pixel não é fundo claro
SAT_CONTEUDO = 18        # acima disto o pixel é colorido mesmo se claro
ABERTURA = 1             # erosões que quebram ponte fina entre desenhos
MIN_AREA = 150           # px: menor massa que vira arquivo
FOLGA = 2                # px de folga no recorte
MAX_LADO = 110           # px: massa com caixa maior que isto é aglomerado
SEPARAR_MIN = 300        # px: marcador mínimo ao separar um aglomerado
                         #     (marcador pequeno fragmenta o desenho fino — o raio do bruxo)


def luminancia(rgb: np.ndarray) -> np.ndarray:
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def saturacao(rgb: np.ndarray) -> np.ndarray:
    return (rgb.max(axis=-1).astype(np.int16) - rgb.min(axis=-1).astype(np.int16))


def alfa_do_fundo(recorte: Image.Image) -> Image.Image:
    """Fundo claro vira transparente; a borda anti-aliasada ganha rampa de alfa."""
    rgb = np.asarray(recorte.convert('RGB')).astype(np.float32)
    lum = luminancia(rgb)
    sat = saturacao(rgb.astype(np.int16))
    opaco = (lum < LUM_FUNDO) | (sat > SAT_CONTEUDO)
    # rampa: quanto mais claro que o fundo, mais transparente (só na borda)
    rampa = np.clip((LUM_FUNDO + 12.0 - lum) / 24.0, 0.0, 1.0)
    alfa = np.where(opaco, np.maximum(rampa, 0.55), rampa * 0.5)
    alfa[~opaco & (lum > LUM_FUNDO + 6)] = 0.0
    rgba = np.dstack([rgb, (np.clip(alfa, 0, 1) * 255).astype(np.uint8)])
    return Image.fromarray(rgba.astype(np.uint8), 'RGBA')


def zonas_do_intervalo(espec: Sequence[str], largura: int) -> List[Tuple[str, int, int]]:
    """['0:400=itens', '400:=mobs'] → [('itens',0,400), ('mobs',400,largura)]"""
    zonas: List[Tuple[str, int, int]] = []
    for item in espec or []:
        if '=' not in item or ':' not in item.split('=')[0]:
            raise SystemExit(f'zona inválida: {item!r} (use "x0:x1=nome")')
        faixa, nome = item.split('=', 1)
        a, _, b = faixa.partition(':')
        zonas.append((nome.strip(), int(a or 0), int(b) if b.strip() else largura))
    return zonas


def zona_de(zonas: Sequence[Tuple[str, int, int]], x: int, largura: int) -> str:
    for nome, a, b in zonas:
        if a <= x < b:
            return nome
    return 'outros'


def massas(conteudo: np.ndarray, abertura: int) -> Tuple[np.ndarray, int]:
    """Rotula o conteúdo, opcionalmente abrindo antes para quebrar pontes finas."""
    base = conteudo
    if abertura > 0:
        erodido = ndimage.binary_erosion(conteudo, np.ones((3, 3), bool), iterations=abertura)
        # reconstrói por dilatação geodésica: separa sem encolher os desenhos
        sementes = erodido
        crescido = sementes.copy()
        for _ in range(abertura + 1):
            crescido = ndimage.binary_dilation(crescido, np.ones((3, 3), bool)) & base
        base = crescido | (conteudo & ~ndimage.binary_dilation(crescido, np.ones((3, 3), bool)))
    rot, n = ndimage.label(base, np.ones((3, 3), int))
    return rot, n


def separar_aglomerado(sel: np.ndarray, min_marcador: int,
                       fracao_max: float = 0.8) -> np.ndarray:
    """Divide uma massa em partes pelos marcadores (cada pixel vai ao mais perto).

    Só vale a pena quando a massa é mesmo um punhado de desenhos colados: se uma
    parte concentra quase tudo (`fracao_max`), é um aglomerado de gente
    sobreposta e nenhum corte automático vai separar — devolve inteiro.
    """
    marc = ndimage.binary_erosion(sel, np.ones((3, 3), bool), iterations=2)
    rot, n = ndimage.label(marc, np.ones((3, 3), int))
    if n < 2:
        return np.where(sel, 1, 0)
    tam = ndimage.sum(marc, rot, range(1, n + 1))
    manter = [i + 1 for i in range(n) if tam[i] >= min_marcador]
    if len(manter) < 2:
        return np.where(sel, 1, 0)
    maior = max(float(tam[i - 1]) for i in manter)
    if maior / float(sum(tam[i - 1] for i in manter)) > fracao_max:
        return np.where(sel, 1, 0)
    limpo = np.where(np.isin(rot, manter), rot, 0)
    _, idx = ndimage.distance_transform_edt(limpo == 0, return_indices=True)
    return np.where(sel, limpo[idx[0], idx[1]], 0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Separa uma cena em elementos soltos.')
    ap.add_argument('--entrada', required=True)
    ap.add_argument('--saida-dir', required=True)
    ap.add_argument('--zonas', action='append', default=[],
                    help='faixas em x para organizar as pastas, ex.: "0:400=itens"')
    ap.add_argument('--min-area', type=int, default=MIN_AREA)
    ap.add_argument('--min-area-zona', action='append', default=[],
                    help='reforça o mínimo por zona, ex.: "mobs=420" (fragmento de mob '
                         'colado no aglomerado é bem menor que um mob inteiro)')
    ap.add_argument('--sem-grupos', action='store_true',
                    help='não separa pasta de grupos: tudo vira elemento')
    ap.add_argument('--abertura', type=int, default=ABERTURA)
    ap.add_argument('--folga', type=int, default=FOLGA)
    ap.add_argument('--max-lado', type=int, default=MAX_LADO,
                    help='px: caixa a partir da qual um recorte é apenas avisado como grande')
    ap.add_argument('--max-area', type=int, default=20000,
                    help='px²: massa maior que isto é aglomerado (horda sobreposta) e vai '
                         'para grupos/ em vez de elementos/')
    ap.add_argument('--separar', action='store_true',
                    help='tenta separar os aglomerados grandes (mobs sobrepostos)')
    ap.add_argument('--prefixo', default='')
    args = ap.parse_args(argv)

    img = Image.open(args.entrada).convert('RGB')
    W, H = img.size
    dados = np.asarray(img).astype(np.int16)
    conteudo = (luminancia(dados) < LUM_FUNDO) | (saturacao(dados) > SAT_CONTEUDO)
    print(f'{args.entrada}: {W}x{H} | conteúdo {100.0 * conteudo.mean():.1f}%')

    # descarta poeira de 1 px antes de agrupar
    conteudo = ndimage.binary_opening(conteudo, np.ones((2, 2), bool))
    rot, n = massas(conteudo, args.abertura)

    zonas = zonas_do_intervalo(args.zonas, W)
    minimos: Dict[str, int] = {}
    for item in args.min_area_zona:
        if '=' not in item:
            raise SystemExit(f'--min-area-zona inválido: {item!r} (use "zona=px")')
        nome, valor = item.split('=', 1)
        minimos[nome.strip()] = int(valor)
    elementos: List[Dict] = []
    for i in range(1, n + 1):
        sel = rot == i
        area = int(sel.sum())
        ys_pre, xs_pre = np.where(sel)
        if xs_pre.size == 0:
            continue
        zona_pre = zona_de(zonas, int((xs_pre.min() + xs_pre.max()) // 2), W) if zonas else 'elementos'
        if area < max(args.min_area, minimos.get(zona_pre, 0)):
            continue
        ys, xs = ys_pre, xs_pre
        larg = int(xs.max() - xs.min() + 1)
        alt = int(ys.max() - ys.min() + 1)
        if args.separar and max(larg, alt) > args.max_lado:
            sub = separar_aglomerado(sel, SEPARAR_MIN)
            for k in np.unique(sub):
                if k == 0:
                    continue
                sel_k = sub == k
                area_k = int(sel_k.sum())
                if area_k < args.min_area:
                    continue
                ys_k, xs_k = np.where(sel_k)
                lk = int(xs_k.max() - xs_k.min() + 1)
                ak = int(ys_k.max() - ys_k.min() + 1)
                elementos.append({
                    'x0': int(xs_k.min()), 'y0': int(ys_k.min()),
                    'x1': int(xs_k.max()), 'y1': int(ys_k.max()),
                    'area': area_k, 'sel': sel_k,
                    'grupo': (not args.sem_grupos) and area_k > args.max_area,
                })
            continue
        elementos.append({'x0': int(xs.min()), 'y0': int(ys.min()),
                          'x1': int(xs.max()), 'y1': int(ys.max()),
                          'area': area, 'sel': sel,
                          'grupo': (not args.sem_grupos) and area > args.max_area})

    elementos.sort(key=lambda e: (e['y0'], e['x0']))
    os.makedirs(args.saida_dir, exist_ok=True)
    manifest = {'fonte': os.path.basename(args.entrada),
                'tamanho': [W, H],
                'zonas': [{'nome': nome, 'x0': a, 'x1': b} for nome, a, b in zonas],
                'elementos': []}
    contagem: Dict[str, int] = {}
    grande = 0
    grupos = 0
    for e in elementos:
        z = zona_de(zonas, (e['x0'] + e['x1']) // 2, W) if zonas else 'elementos'
        if e.get('grupo'):
            z = 'grupos'
            grupos += 1
        contagem[z] = contagem.get(z, 0) + 1
        pasta = os.path.join(args.saida_dir, z)
        os.makedirs(pasta, exist_ok=True)
        cx0 = max(0, e['x0'] - args.folga)
        cy0 = max(0, e['y0'] - args.folga)
        cx1 = min(W, e['x1'] + args.folga + 1)
        cy1 = min(H, e['y1'] + args.folga + 1)
        nome = f'{args.prefixo}{z}_{contagem[z]:03d}'
        recorte = alfa_do_fundo(img.crop((cx0, cy0, cx1, cy1)))
        # mantém só a massa: o que veio de outro desenho não entra
        mascara = np.zeros(recorte.size[::-1], bool)
        sub = e['sel'][cy0:cy1, cx0:cx1]
        mascara[:sub.shape[0], :sub.shape[1]] = sub
        crescido = ndimage.binary_dilation(mascara, np.ones((5, 5), bool))
        arr = np.asarray(recorte).copy()
        arr[..., 3] = np.where(crescido, arr[..., 3], 0)
        recorte = Image.fromarray(arr, 'RGBA')
        caixa = recorte.getchannel('A').point(lambda v: 255 if v > 12 else 0).getbbox()
        if caixa:
            recorte = recorte.crop(caixa)
        recorte.save(os.path.join(pasta, f'{nome}.png'))
        manifest['elementos'].append({
            'nome': f'{z}/{nome}.png', 'zona': z,
            'onde': [cx0, cy0, cx1, cy1],
            'tamanho': [recorte.width, recorte.height], 'area': e['area'],
        })
        if max(cx1 - cx0, cy1 - cy0) > args.max_lado:
            grande += 1

    with open(os.path.join(args.saida_dir, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    # mapa numerado: cada elemento ganha um número na posição dele
    mapa = img.copy()
    d = ImageDraw.Draw(mapa)
    for k, e in enumerate(elementos, start=1):
        d.rectangle([e['x0'] - 1, e['y0'] - 1, e['x1'] + 1, e['y1'] + 1],
                    outline=(220, 40, 40), width=2)
        d.text((e['x0'], max(0, e['y0'] - 12)), str(k), fill=(200, 0, 0))
    mapa.save(os.path.join(args.saida_dir, 'mapa-numerado.png'))

    print(f'   {len(elementos)} recortes: ' +
          ', '.join(f'{k}={v}' for k, v in sorted(contagem.items())))
    if grupos:
        print(f'   (grupos: mobs sobrepostos numa massa só, guardados em grupos/; '
              f'separem na mão se algum dia precisar)')
    if grande:
        print(f'   aviso: {grande} recorte(s) com caixa maior que {args.max_lado} px')
    print(f'   mapa de conferência: {os.path.join(args.saida_dir, "mapa-numerado.png")}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
