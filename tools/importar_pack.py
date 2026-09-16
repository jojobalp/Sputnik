#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""importar_pack.py — converte um pack de terceiros para o formato do jogo.

O pack "Tiny RPG Character Asset Pack" traz a arte em células de 100x100, uma
tira por animação, com sombra numa camada e nomes de tag próprios. O jogo espera
outra coisa: célula própria, âncora nos pés (o desenho termina na base da célula)
e tags `<personagem>_<idle|movement|attack|take_damage|death>`.

Este script faz essa conversão lendo os `.aseprite` de origem — não as tiras —
para poder escolher as camadas (exporta sem a sombra, porque o jogo desenha a
sua) e usar cada quadro com a duração original.

Uso:
    python3 tools/importar_pack.py --mapa tools/mapas/pack_tiny.json \\
        --saida-dir art/tiny-rpg-pack/jogo
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageStat

AQUI = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    'verificar_aseprite', os.path.join(AQUI, 'verificar_aseprite.py'))
va = importlib.util.module_from_spec(_spec)
sys.modules['verificar_aseprite'] = va
_spec.loader.exec_module(va)


# --------------------------------------------------------------------------- #
# leitura do pack
# --------------------------------------------------------------------------- #
def achar_tag(tags: Sequence[dict], nome: str) -> dict:
    for t in tags:
        if t['nome'].lower() == nome.lower():
            return t
    raise SystemExit(f'tag "{nome}" não existe no arquivo (tem: ' +
                     ', '.join(t["nome"] for t in tags) + ')')


def montar_frames(caminho: str, remover: Sequence[str]) -> Tuple[List[Image.Image], List[dict], Tuple[int, int]]:
    """Frames achatados sem as camadas pedidas (ex.: sem a sombra do pack)."""
    frames, tags, canvas = va.ler_arquivo(caminho)
    nomes_camadas = va.ler_camadas(caminho)
    fora = {i for i, nome in enumerate(nomes_camadas) if nome in set(remover)}
    imagens = []
    for f in frames:
        tela = Image.new('RGBA', canvas, (0, 0, 0, 0))
        for c in f.get('cels') or ([f['cel']] if f.get('cel') else []):
            if c.get('img') is None or c.get('layer') in fora:
                continue
            tela.alpha_composite(c['img'], (max(0, c['x']), max(0, c['y'])))
        imagens.append(tela)
    return imagens, tags, canvas


def caixa(imagens: Sequence[Image.Image], alfa_min: int = 40) -> Optional[Tuple[int, int, int, int]]:
    """Menor retângulo com desenho, considerando todos os quadros recebidos.

    `alfa_min` baixo pega a borda anti-aliasada (é o que interessa para saber até
    onde o desenho chega); alto pega só o pixel sólido — é o que serve para achar
    a linha dos pés, porque o pé tem pixel fraco no contorno e o desenho "acaba"
    antes dele.
    """
    x0 = y0 = 10 ** 9
    x1 = y1 = -1
    for im in imagens:
        a = im.getchannel('A').point(lambda v: 255 if v > alfa_min else 0)
        c = a.getbbox()
        if not c:
            continue
        x0, y0 = min(x0, c[0]), min(y0, c[1])
        x1, y1 = max(x1, c[2] - 1), max(y1, c[3] - 1)
    return None if x1 < 0 else (x0, y0, x1, y1)


def janela(imagens: Sequence[Image.Image], quadros_de_repouso: Sequence[Image.Image],
           celula: Tuple[int, int], margem_base: int) -> Tuple[int, int, int]:
    """Canto superior esquerdo do recorte fixo (mesmo para todos os quadros).

    A janela é fixa de propósito: recortar cada quadro pelo próprio desenho faria
    o personagem tremer de um quadro para o outro. O centro horizontal vem das
    animações de repouso (parado/andando) e a base, da linha dos pés nessas
    mesmas animações — o jogo ancora o desenho pela base.

    Se a animação de ataque passar do centro (a espada esticada, por exemplo), a
    janela desliza o mínimo necessário para caber — o corpo continua no centro e
    nada é cortado de lado. Para baixo não há escapatória: manter a linha dos pés
    na base é o que faz a âncora do jogo funcionar, então o que passar da margem
    é cortado e o corte é informado.
    """
    cw, ch = celula
    c_repouso = caixa(quadros_de_repouso)
    c_solido = caixa(quadros_de_repouso, alfa_min=200)
    c_tudo = caixa(imagens)
    if c_repouso is None or c_tudo is None or c_solido is None:
        raise SystemExit('não achei desenho nas animações de repouso')
    centro_x = (c_repouso[0] + c_repouso[2]) / 2.0
    pes = c_solido[3] - 1                # linha dos pés: último pixel sólido (bbox é exclusivo)
    desejado = int(round(centro_x - (cw - 1) / 2.0))
    # menor deslocamento que mantém todo o desenho dentro da largura da célula
    minimo = c_tudo[2] - cw              # x0 não pode ser menor que isto
    maximo = c_tudo[0]                   # nem maior que isto
    x0 = desejado if minimo <= desejado <= maximo else min(max(desejado, minimo), maximo)
    y0 = pes - (ch - 1 - margem_base)
    corte = max(0, (c_tudo[3] - 1) - (y0 + ch - 1))   # bbox é exclusivo
    return x0, y0, corte


def recortar(imagens: Sequence[Image.Image], x0: int, y0: int,
             celula: Tuple[int, int]) -> List[Image.Image]:
    cw, ch = celula
    saida = []
    for im in imagens:
        tela = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
        tela.alpha_composite(im, (-x0, -y0))
        saida.append(tela)
    return saida


# --------------------------------------------------------------------------- #
# escrita no formato do Aseprite (o que assets.js lê)
# --------------------------------------------------------------------------- #
def tinta(im: Image.Image) -> int:
    """Soma do canal alfa: serve para conferir que o recorte não perdeu desenho."""
    return int(ImageStat.Stat(im.getchannel('A')).sum[0])


def alfa_fora(im: Image.Image, x0: int, y0: int, celula: Tuple[int, int]) -> int:
    """Alfa mais forte que sobrou fora da janela de recorte (0 = nada ficou fora)."""
    cw, ch = celula
    mascara = Image.new('L', im.size, 255)          # 255 = fora da janela
    mascara.paste(0, (max(0, x0), max(0, y0),
                      min(im.width, x0 + cw), min(im.height, y0 + ch)))
    recorte = Image.composite(im.getchannel('A'), Image.new('L', im.size, 0), mascara)
    return int(ImageStat.Stat(recorte).extrema[0][1])


def montar(tira: Sequence[Image.Image], celula: Tuple[int, int]) -> Image.Image:
    cw, ch = celula
    sheet = Image.new('RGBA', (cw * len(tira), ch), (0, 0, 0, 0))
    for i, f in enumerate(tira):
        sheet.paste(f, (i * cw, 0))
    return sheet


def json_aseprite(nome: str, n_frames_por_tag: List[Tuple[str, int]], celula: Tuple[int, int],
                  duracoes: List[int], largura: int, total: int) -> dict:
    cw, ch = celula
    frames = {}
    for i in range(total):
        frames[f'{nome} {i}.aseprite'] = {
            'frame': {'x': i * cw, 'y': 0, 'w': cw, 'h': ch},
            'rotated': False,
            'trimmed': False,
            'spriteSourceSize': {'x': 0, 'y': 0, 'w': cw, 'h': ch},
            'sourceSize': {'w': cw, 'h': ch},
            'duration': duracoes[i],
        }
    tags, cursor = [], 0
    for rotulo, quantos in n_frames_por_tag:
        tags.append({'name': f'{nome}_{rotulo}', 'from': cursor, 'to': cursor + quantos - 1,
                     'direction': 'forward', 'color': '#000000ff'})
        cursor += quantos
    return {
        'frames': frames,
        'meta': {
            'app': 'https://www.aseprite.org/',
            'version': '1.3.17-x64',
            'image': f'{nome}.png',
            'format': 'RGBA8888',
            'size': {'w': largura, 'h': ch},
            'scale': '1',
            'frameTags': tags,
            'layers': [{'name': 'Flattened', 'opacity': 255, 'blendMode': 'normal'}],
            'slices': [],
        },
    }


# --------------------------------------------------------------------------- #
# programa
# --------------------------------------------------------------------------- #
def importar_personagem(cfg: dict, celula: Tuple[int, int], margem_base: int, saida: str,
                        prefixo: str = '') -> dict:
    nome = cfg['nome']
    imagens, tags, canvas = montar_frames(cfg['aseprite'], cfg.get('remover_camadas', []))
    print(f'{nome}: {len(imagens)} quadros, canvas {canvas[0]}x{canvas[1]}, '
          f'camadas removidas: {cfg.get("remover_camadas") or "nenhuma"}')

    mapa = cfg['animacoes']
    de_repouso, usados = [], []
    for rotulo, tag_nome in mapa.items():
        t = achar_tag(tags, tag_nome)
        usados.extend(imagens[t['de']:t['ate'] + 1])
        if rotulo in ('idle', 'movement'):
            de_repouso.extend(imagens[t['de']:t['ate'] + 1])
    x0, y0, corte = janela(usados, de_repouso, celula, margem_base)
    print(f'   janela de recorte: x0={x0} y0={y0} (célula {celula[0]}x{celula[1]}, '
          f'{margem_base} px de margem abaixo dos pés)')
    if corte:
        print(f'   observação: {corte} px abaixo da margem são cortados — é onde o golpe '
              f'passa do chão (o desenho tem de terminar na base da célula)')

    tira: List[Image.Image] = []
    duracoes: List[int] = []
    contagem: List[Tuple[str, int]] = []
    for rotulo, tag_nome in mapa.items():
        t = achar_tag(tags, tag_nome)
        if t['de'] == t['ate']:
            print(f'   ATENÇÃO: a tag "{tag_nome}" tem um quadro só ({rotulo} vai ser estático)')
        qs = recortar(imagens[t['de']:t['ate'] + 1], x0, y0, celula)
        tira.extend(qs)
        duracoes.extend([f['dur'] for f in qs and []] or
                        [im['dur'] for im in va.ler_arquivo(cfg['aseprite'])[0][t['de']:t['ate'] + 1]])
        contagem.append((rotulo, len(qs)))
        print(f'   {rotulo:12s} <- {tag_nome:10s} {len(qs)} quadros, '
              f'{sum(duracoes[-len(qs):])} ms')

    # confere se sobrou desenho fora do recorte
    antes = sum(tinta(im) for im in usados)
    depois = sum(tinta(im) for im in tira)
    fora = max(alfa_fora(im, x0, y0, celula) for im in usados)
    if depois >= antes:
        print(f'   recorte preserva 100% do desenho ({antes} de tinta)')
    else:
        resto = '' if fora > 40 else ' — abaixo do limiar visível, é a ponta suave do golpe'
        print(f'   recorte preserva {100.0 * depois / antes:.2f}% do desenho '
              f'({antes - depois} de tinta fora do quadro; pixel mais forte: alfa {fora}{resto})')

    sheet = montar(tira, celula)
    os.makedirs(saida, exist_ok=True)
    sheet.save(os.path.join(saida, f'{prefixo}{nome}.png'))
    dados = json_aseprite(nome, contagem, celula, duracoes, sheet.width, len(tira))
    with open(os.path.join(saida, f'{prefixo}{nome}.json'), 'w', encoding='utf-8') as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)
    print(f'   -> {prefixo}{nome}.png ({sheet.width}x{sheet.height}) + .json')

    # conferência: nenhum quadro pode encostar na borda da célula (o projeto usa
    # essa margem para não vazar pixel do vizinho no atlas)
    encostando = 0
    for i, f in enumerate(tira):
        a = f.getchannel('A').point(lambda v: 255 if v > 40 else 0)
        c = a.getbbox()
        if not c:
            continue
        if c[0] == 0 or c[1] == 0 or c[2] == celula[0] or c[3] == celula[1]:
            encostando += 1
    if encostando:
        print(f'   ATENÇÃO: {encostando} quadro(s) com desenho encostando na borda da célula '
              f'(aumente a célula ou diminua o desenho)')
    return {'nome': nome, 'quadros': len(tira), 'celula': list(celula),
            'animacoes': {r: n for r, n in contagem}, 'encostando_na_borda': encostando}


def importar_projetil(cfg: dict, saida: str) -> dict:
    """Projétil: recorta o desenho e centraliza numa célula quadrada."""
    nome = cfg['nome']
    lado = int(cfg['celula'])
    im = Image.open(cfg['png']).convert('RGBA')
    c = im.getchannel('A').point(lambda v: 255 if v > 40 else 0).getbbox()
    if not c:
        raise SystemExit(f'{cfg["png"]}: imagem vazia')
    desenho = im.crop(c)
    if desenho.width > lado or desenho.height > lado:
        raise SystemExit(f'{nome}: desenho {desenho.width}x{desenho.height} não cabe em {lado}x{lado}')
    cel = Image.new('RGBA', (lado, lado), (0, 0, 0, 0))
    cel.alpha_composite(desenho, ((lado - desenho.width) // 2, (lado - desenho.height) // 2))
    os.makedirs(saida, exist_ok=True)
    cel.save(os.path.join(saida, f'{nome}.png'))
    dados = json_aseprite(nome, [('idle', 1)], (lado, lado), [100], lado, 1)
    with open(os.path.join(saida, f'{nome}.json'), 'w', encoding='utf-8') as fh:
        json.dump(dados, fh, ensure_ascii=False, indent=2)
    print(f'{nome}: {desenho.width}x{desenho.height} px de desenho numa célula {lado}x{lado} '
          f'(aponta para a direita) -> {nome}.png + .json')
    return {'nome': nome, 'celula': [lado, lado], 'desenho': [desenho.width, desenho.height]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Importa um pack de terceiros para o formato do jogo.')
    ap.add_argument('--mapa', required=True, help='JSON com o de/para de cada personagem')
    ap.add_argument('--saida-dir', required=True)
    ap.add_argument('--prefixo', default='')
    ap.add_argument('--sem-projetil', action='store_true')
    args = ap.parse_args(argv)

    with open(args.mapa, encoding='utf-8') as fh:
        mapa = json.load(fh)
    celula = (int(mapa['celula']['w']), int(mapa['celula']['h']))
    margem = int(mapa['celula'].get('margem_base', 3))
    print(f'{mapa["pack"]}\n')

    resumo = {'pack': mapa['pack'], 'autor': mapa.get('autor'), 'origem': mapa.get('origem'),
              'celula': list(celula), 'personagens': {}, 'projetil': None}
    for cfg in mapa['personagens']:
        resumo['personagens'][cfg['nome']] = importar_personagem(
            cfg, celula, margem, args.saida_dir, args.prefixo)
        print()
    if mapa.get('projetil') and not args.sem_projetil:
        resumo['projetil'] = importar_projetil(mapa['projetil'], args.saida_dir)
        print()

    caminho = os.path.join(args.saida_dir, 'gerado.json')
    with open(caminho, 'w', encoding='utf-8') as fh:
        json.dump(resumo, fh, ensure_ascii=False, indent=2)
    print(f'resumo em {caminho}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
