#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_spritesheet.py — limpa uma prancha de referência e separa frame a frame.

Feito para as pranchas "de planejamento" (geradas por IA ou desenhadas à mão) que
trazem grade, título, numeração, rótulos e uma coluna de referência: aqui elas
viram PNGs individuais com fundo transparente, agrupados por animação.

Como funciona:
    1. acha as linhas da grade (picos de borda vertical/horizontal) e monta as
       células — assim o personagem não precisa estar centralizado nem inteiro
       para ser recortado;
    2. em cada célula, descarta a faixa do rótulo (embaixo) e recorta o resto;
    3. remove o fundo por preenchimento a partir da borda da célula, com alfa
       suave nas bordas anti-aliasadas, preservando partes claras internas
       (mão, magia, brilho);
    4. limpa resíduos: respingos, halo claro, poeira de JPEG e a numeração
       pequena da célula;
    5. alinha os quadros pela base (pés) dentro da animação, sem matar o
       movimento do corpo;
    6. grava frames soltos, sheet reconstruído sem grade/rótulos, GIF de prévia
       e um manifest com a mesma estrutura do export do Aseprite.

Uso:
    # 1) ver o que ele encontrou, sem gravar
    python3 tools/extrair_spritesheet.py --entrada prancha.jpg --diagnostico

    # 2) extrair
    python3 tools/extrair_spritesheet.py --entrada prancha.jpg \
        --mapa tools/mapas/wizard_casting.json --saida-dir Sprite/Characters/casting

    # 3) se a grade automática errar, informe a grade na mão
    python3 tools/extrair_spritesheet.py --entrada prancha.jpg --grade manual \
        --x0 22 --y0 44 --celula 148x72 --colunas 7 --linhas 6
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image
from scipy import ndimage

# --------------------------------------------------------------------------- #
# parâmetros
# --------------------------------------------------------------------------- #
LUM_FUNDO = 205          # a partir disto o pixel é "fundo claro"
SAT_CONTEUDO = 26        # saturação mínima para tratar como conteúdo colorido
TOL_FUNDO = 22           # tolerância do preenchimento de fundo (distância RGB)
TOL_HALO = 40            # a partir disto o pixel claro é considerado halo de borda
FOLGA = 2                # px de folga ao recortar
ALFA_SOLIDO = 0.55
MIN_MASSA = 24           # px: abaixo disto é respingo/ruído de JPEG
MIN_MASSA_REL = 0.12     # fração do corpo: candidato a resíduo
TOPO_RESIDUO = 0.18      # fração do topo da célula onde mora a numeração
FRACAO_ROTULO = 0.22     # fração inferior da célula reservada ao rótulo
MIN_ESPACO_LINHA = 24    # px: distância mínima entre linhas de grade


# --------------------------------------------------------------------------- #
# utilidades de pixel
# --------------------------------------------------------------------------- #
def luminancia(rgb: np.ndarray) -> np.ndarray:
    return (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2])


def saturacao(rgb: np.ndarray) -> np.ndarray:
    return (rgb.max(axis=-1).astype(np.int16) - rgb.min(axis=-1).astype(np.int16))


def _picos(perfil: np.ndarray, min_espaco: int, limiar: float) -> List[int]:
    """Posições dos picos de um perfil 1-D, com supressão de vizinhança."""
    if perfil.size == 0:
        return []
    candidatos = np.where(perfil > limiar)[0]
    if candidatos.size == 0:
        return []
    ordenados = candidatos[np.argsort(-perfil[candidatos])]
    escolhidos: List[int] = []
    for c in ordenados:
        if all(abs(int(c) - e) >= min_espaco for e in escolhidos):
            escolhidos.append(int(c))
    return sorted(escolhidos)


def perfil_linhas(cinza: np.ndarray, eixo: int, limiar_aresta: float = 6.0) -> np.ndarray:
    """Fração da imagem que tem borda em cada coluna (eixo=1) ou linha (eixo=0).

    Uma linha de grade atravessa a figura inteira, então essa fração fica alta;
    a borda de um desenho (cajado, ombro, magia) só cobre um trecho e fica baixa.
    É isso que separa grade de personagem sem depender de posição.
    """
    grad = np.abs(np.diff(cinza, axis=eixo))
    total = cinza.shape[0] if eixo == 1 else cinza.shape[1]
    return (grad > limiar_aresta).sum(axis=0 if eixo == 1 else 1) / total


def detectar_grade(img: Image.Image, forca: float = 0.55,
                   min_espaco: int = MIN_ESPACO_LINHA,
                   limiar_aresta: float = 6.0) -> Tuple[List[int], List[int]]:
    """Colunas e linhas da grade (fração mínima `forca` de borda ao longo da figura)."""
    cinza = luminancia(np.asarray(img.convert('RGB')).astype(np.float32))
    cx = perfil_linhas(cinza, 1, limiar_aresta)
    cy = perfil_linhas(cinza, 0, limiar_aresta)
    xs = [p + 1 for p in _picos(cx, min_espaco, forca)]
    ys = [p + 1 for p in _picos(cy, min_espaco, forca)]
    return xs, ys


def faixas(coords: Sequence[int], limite: int, minima: int = 24) -> List[Tuple[int, int]]:
    """Converte coordenadas de linha em faixas, descartando margens estreitas.

    As faixas de borda (papel branco em volta da prancha) são bem mais estreitas
    que uma célula; o corte em `minima` (e em 30% da mediana) tira elas sem
    depender de posição.
    """
    if not coords:
        return []
    bordas = [0] + list(coords) + [limite]
    brutas = [(a, b) for a, b in zip(bordas, bordas[1:]) if b - a >= 8]
    if not brutas:
        return []
    mediana = sorted(b - a for a, b in brutas)[len(brutas) // 2]
    corte = max(minima, int(0.3 * mediana))
    return [(a, b) for a, b in brutas if b - a >= corte]


# --------------------------------------------------------------------------- #
# recorte e remoção de fundo
# --------------------------------------------------------------------------- #
def alfa_do_fundo(recorte: Image.Image, tol: int = TOL_FUNDO,
                  limiar_aresta: float = 26.0) -> Image.Image:
    """Remove o fundo claro preservando claridade interna (mão, magia, brilho).

    O preenchimento sai das bordas do recorte e só avança por pixels parecidos
    com o fundo E que não sejam borda. Sem isso, uma bola de magia branca sobre
    fundo claro tem o miolo apagado (o preenchimento atravessa o contorno dela);
    com a barreira de borda, ela fica "fechada" e é preservada.
    """
    rgb = np.asarray(recorte.convert('RGB')).astype(np.int16)
    lum = luminancia(rgb)
    sat = saturacao(rgb)

    fundo_cor = np.median(np.concatenate([
        rgb[0, :, :], rgb[-1, :, :], rgb[:, 0, :], rgb[:, -1, :]]), axis=0)
    dist = np.sqrt(((rgb - fundo_cor) ** 2).sum(axis=-1))
    parecido = (dist < tol) | ((lum > LUM_FUNDO - 30) & (sat < SAT_CONTEUDO))

    # barreira: onde a imagem muda de cor bruscamente (contorno do personagem,
    # anel da magia, sombra das dobras) o preenchimento para.
    gy = np.zeros_like(lum)
    gx = np.zeros_like(lum)
    gy[1:, :] = np.abs(np.diff(lum, axis=0))
    gx[:, 1:] = np.abs(np.diff(lum, axis=1))
    borda = np.maximum(gy, gx) > limiar_aresta
    borda = ndimage.binary_dilation(borda, np.ones((3, 3), bool))
    passavel = parecido & ~borda

    sementes = np.zeros(lum.shape, dtype=bool)
    sementes[0, :] = sementes[-1, :] = True
    sementes[:, 0] = sementes[:, -1] = True
    sementes &= passavel
    fundo = ndimage.binary_propagation(sementes, mask=passavel,
                                       structure=np.ones((3, 3), bool))

    lum_fundo = float(np.median(lum[fundo])) if fundo.any() else 240.0
    alfa = np.clip((lum_fundo - lum.astype(np.float32)) / max(12.0, lum_fundo * 0.42), 0.0, 1.0)
    alfa = np.where(fundo, 0.0, alfa)
    # halo: pixel claro, sem cor, logo acima do fundo (borda anti-aliasada). Só
    # estes são atenuados — o miolo de uma magia branca é claro mas está longe
    # da cor do fundo, então continua opaco.
    halo = (~fundo) & (alfa < ALFA_SOLIDO) & (dist < TOL_HALO)
    alfa[halo] = np.clip(alfa[halo] - 0.25, 0.0, 1.0)

    rgba = np.dstack([np.asarray(recorte.convert('RGB')), (alfa * 255).astype(np.uint8)])
    return Image.fromarray(rgba.astype(np.uint8), 'RGBA')


def limpar_residuo(im: Image.Image, min_massa: int = MIN_MASSA,
                   min_rel: float = MIN_MASSA_REL,
                   topo_residuo: float = TOPO_RESIDUO) -> Image.Image:
    """Descarta numeração de célula e respingos, preservando efeitos soltos.

    A magia na ponta do cajado é um componente pequeno e DESLIGADO do corpo —
    por isso não pode ser removida só por ser menor. O que se remove é:
      - qualquer coisa minúscula (respingo, poeira de JPEG); e
      - componente pequeno que fica colado no topo da célula (a numeração
        impressa pela prancha, que sobra do recorte).
    """
    dados = np.asarray(im).copy()
    a = dados[..., 3]
    forte = a > 24
    rot, n = ndimage.label(forte, structure=np.ones((3, 3), int))
    if n == 0:
        return im
    tamanhos = ndimage.sum(forte, rot, range(1, n + 1))
    maior = float(tamanhos.max()) if len(tamanhos) else 0.0
    corte_tamanho = max(min_massa, min_rel * maior)
    limite_topo = im.height * topo_residuo

    manter = []
    for i, tamanho in enumerate(tamanhos):
        if tamanho < min_massa:
            continue
        if tamanho < corte_tamanho:
            ys, _ = np.where(rot == i + 1)
            if ys.size and float(ys.mean()) <= limite_topo:
                continue                      # numeração colada no topo
        manter.append(i + 1)
    if not manter:
        return Image.fromarray(np.dstack([dados[..., :3], np.zeros_like(a)]), 'RGBA')
    dados[..., 3] = np.where(np.isin(rot, manter), a, 0)
    return Image.fromarray(dados, 'RGBA')


def cobertura(celula: Image.Image, extraido: Image.Image) -> float:
    """Fração do conteúdo da célula que sobreviveu na extração (0..1).

    Mede o quanto do "desenho" (o que não é fundo claro) virou pixel visível.
    Serve de alarme: se cair muito, algum pedaço foi apagado por engano.
    """
    rgb = np.asarray(celula.convert('RGB')).astype(np.int16)
    conteudo = (luminancia(rgb) < LUM_FUNDO - 15) | (saturacao(rgb) > SAT_CONTEUDO)
    esperado = int(conteudo.sum())
    if esperado == 0:
        return 1.0
    obtido = int((np.asarray(extraido)[..., 3] > 24).sum())
    return min(1.0, obtido / esperado)


def aparar(im: Image.Image) -> Image.Image:
    caixa = im.getchannel('A').point(lambda v: 255 if v > 12 else 0).getbbox()
    return im.crop(caixa) if caixa else im


# --------------------------------------------------------------------------- #
# alinhamento e saída
# --------------------------------------------------------------------------- #
def alinhar(frames: Sequence[Image.Image], modo: str = 'base') -> Tuple[List[Image.Image], Tuple[int, int]]:
    W = max(f.width for f in frames)
    H = max(f.height for f in frames)
    saida = []
    for f in frames:
        tela = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        x = (W - f.width + 1) // 2
        y = H - f.height if modo == 'base' else (H - f.height + 1) // 2
        tela.paste(f, (x, y))
        saida.append(tela)
    return saida, (W, H)


def montar_sheet(frames: Sequence[Image.Image], tam: Tuple[int, int]) -> Image.Image:
    w, h = tam
    sheet = Image.new('RGBA', (w * len(frames), h), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, (i * w, 0))
    return sheet


def gif(frames: Sequence[Image.Image], caminho: str, ms: int = 130, zoom: int = 3) -> None:
    if not frames:
        return
    W, H = frames[0].size
    preparados = []
    for f in frames:
        tela = Image.new('RGBA', (W, H), (26, 26, 32, 255))
        tela.alpha_composite(f)
        preparados.append(tela.convert('P', palette=Image.ADAPTIVE, colors=128)
                          .resize((W * zoom, H * zoom), Image.NEAREST))
    preparados[0].save(caminho, save_all=True, append_images=preparados[1:],
                       duration=ms, loop=0, disposal=2)


def tem_conteudo(img: Image.Image, faixa: Tuple[int, int], eixo: int,
                 min_altura_rel: float = 0.35, min_px: int = 250) -> bool:
    """Diz se uma faixa da prancha contém um desenho (e não só texto).

    Faixa de título ou de legenda tem só glifos baixos; uma fileira de quadros
    tem o personagem, que ocupa boa parte da altura da faixa. O critério é a
    extensão vertical (ou horizontal) do conteúdo dentro da faixa.
    """
    a, b = faixa
    recorte = img.crop((0, a, img.width, b)) if eixo == 0 else img.crop((a, 0, b, img.height))
    rgb = np.asarray(recorte.convert('RGB')).astype(np.int16)
    mask = (luminancia(rgb) < LUM_FUNDO - 30) | (saturacao(rgb) > SAT_CONTEUDO)
    if mask.sum() < min_px:
        return False
    proj = mask.sum(axis=1 if eixo == 0 else 0)
    linhas = np.where(proj > 1)[0]
    if linhas.size == 0:
        return False
    extensao = linhas.max() - linhas.min() + 1
    referencia = (b - a)
    return (extensao / referencia) >= min_altura_rel


def ler_mapa(caminho: Optional[str]) -> Optional[dict]:
    if not caminho:
        return None
    with open(caminho, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def rotulos_da_linha(mapa: Optional[dict], indice: int, n_colunas: int) -> Tuple[str, List[str]]:
    linhas = (mapa or {}).get('linhas', [])
    if indice < len(linhas):
        linha = linhas[indice]
        direcao = linha.get('nome') or linha.get('direcao') or f'linha{indice+1}'
        rotulos = list(linha.get('sequencia', []))
        while len(rotulos) < n_colunas:
            rotulos.append(f'frame{len(rotulos)+1:02d}')
        return direcao, rotulos[:n_colunas]
    return f'linha{indice+1}', [f'frame{i+1:02d}' for i in range(n_colunas)]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Limpa uma prancha e extrai os frames.')
    ap.add_argument('--entrada', required=True)
    ap.add_argument('--saida-dir', default='Sprite/Characters/casting')
    ap.add_argument('--mapa', default=None, help='JSON com as animações de cada linha')
    ap.add_argument('--grade', choices=['auto', 'manual'], default='auto')
    ap.add_argument('--x0', type=int, default=0)
    ap.add_argument('--y0', type=int, default=0)
    ap.add_argument('--celula', default='148x72', help='largura x altura da célula (grade manual)')
    ap.add_argument('--colunas', type=int, default=0, help='nº de colunas de animação (0 = todas)')
    ap.add_argument('--linhas', type=int, default=0, help='nº de linhas de animação (0 = todas)')
    ap.add_argument('--fracao-rotulo', type=float, default=FRACAO_ROTULO,
                    help='fração inferior da célula reservada ao rótulo (descartada)')
    ap.add_argument('--forca-pico', type=float, default=0.55,
                    help='fração mínima da figura que precisa ter borda para ser linha de grade')
    ap.add_argument('--prefixo', default='')
    ap.add_argument('--diagnostico', action='store_true')
    ap.add_argument('--gif', action='store_true')
    ap.add_argument('--debug', action='store_true', help='salva um PNG com a grade detectada')
    args = ap.parse_args(argv)

    img = Image.open(args.entrada).convert('RGB')
    W, H = img.size
    print(f'{args.entrada}: {W}x{H}')

    if args.grade == 'auto':
        xs, ys = detectar_grade(img, args.forca_pico)
        colunas = faixas(xs, W)
        linhas = faixas(ys, H)
    else:
        cw, ch = (int(v) for v in args.celula.lower().split('x'))
        n_col = args.colunas or max(1, (W - args.x0) // cw)
        n_lin = args.linhas or max(1, (H - args.y0) // ch)
        colunas = [(args.x0 + i * cw, args.x0 + (i + 1) * cw) for i in range(n_col)]
        linhas = [(args.y0 + j * ch, args.y0 + (j + 1) * ch) for j in range(n_lin)]

    print(f'   colunas ({len(colunas)}): ' + ', '.join(f'{a}-{b}' for a, b in colunas))
    print(f'   linhas  ({len(linhas)}): ' + ', '.join(f'{a}-{b}' for a, b in linhas))

    # tira faixas que só têm texto (título, legenda, margem) antes de numerar
    linhas = [f for f in linhas if tem_conteudo(img, f, 0)]
    colunas = [f for f in colunas if tem_conteudo(img, f, 1)]
    if args.colunas:
        colunas = colunas[:args.colunas]
    if args.linhas:
        linhas = linhas[:args.linhas]
    print(f'   depois do filtro: {len(colunas)} colunas, {len(linhas)} linhas')

    if args.debug:
        from PIL import ImageDraw
        dbg = img.copy()
        d = ImageDraw.Draw(dbg)
        for a, b in colunas:
            d.line([(a, 0), (a, H)], fill=(255, 0, 0), width=1)
            d.line([(b - 1, 0), (b - 1, H)], fill=(255, 0, 0), width=1)
        for a, b in linhas:
            d.line([(0, a), (W, a)], fill=(0, 120, 255), width=1)
            d.line([(0, b - 1), (W, b - 1)], fill=(0, 120, 255), width=1)
        saida_dbg = os.path.join(os.path.dirname(args.saida_dir) or '.', 'grade-detectada.png')
        dbg.save(saida_dbg)
        print(f'   depuração salva em {saida_dbg}')

    if args.diagnostico:
        print('\n(diagnóstico: nada foi gravado)')
        return 0

    mapa = ler_mapa(args.mapa)
    os.makedirs(args.saida_dir, exist_ok=True)
    manifest = {'fonte': os.path.basename(args.entrada),
                'grade': {'colunas': colunas, 'linhas': linhas,
                          'fracao_rotulo': args.fracao_rotulo},
                'animacoes': {}}
    total = 0
    indice_linha = -1          # só conta linhas que realmente viraram animação
    for j, (ya, yb) in enumerate(linhas):
        # descarta a faixa do rótulo, embaixo, e a numeração da célula, em cima
        corte = int((yb - ya) * args.fracao_rotulo)
        topo = ya + 2
        base = yb - corte
        if base - topo < 12:
            continue
        nome_linha, rotulos = rotulos_da_linha(mapa, indice_linha + 1, len(colunas))
        frames, usados, avisos = [], [], []
        for i, (xa, xb) in enumerate(colunas):
            celula = img.crop((xa + 2, topo, xb - 2, base))
            if celula.width < 12 or celula.height < 12:
                continue
            rec = limpar_residuo(alfa_do_fundo(celula, TOL_FUNDO))
            rec = aparar(rec)
            if rec.width <= 3 or rec.height <= 3:
                continue
            rotulo = rotulos[i] if i < len(rotulos) else f'frame{i+1:02d}'
            razao = cobertura(celula, rec)
            if razao < 0.85:
                avisos.append((rotulo, razao))
            frames.append(rec)
            usados.append(rotulo)
        if not frames:
            continue
        indice_linha += 1
        frames, tam = alinhar(frames, 'base')
        sub = os.path.join(args.saida_dir, 'frames', nome_linha)
        os.makedirs(sub, exist_ok=True)
        for rotulo, f in zip(usados, frames):
            f.save(os.path.join(sub, f'{args.prefixo}{rotulo}.png'))
            total += 1
        montar_sheet(frames, tam).save(os.path.join(args.saida_dir, f'{nome_linha}.png'))
        if args.gif:
            gif(frames, os.path.join(args.saida_dir, f'{nome_linha}.gif'))
        manifest['animacoes'][nome_linha] = {
            'rotulos': usados,
            'cobertura_minima': round(min((cobertura(img.crop((colunas[k][0] + 2, topo, colunas[k][1] - 2, base)), f)
                                           for k, f in enumerate(frames)), default=1.0), 3),
            'celula': {'w': tam[0], 'h': tam[1]},
            'sheet': f'{nome_linha}.png',
            'frames': [f'frames/{nome_linha}/{args.prefixo}{r}.png' for r in usados],
        }
        resumo_cob = ''
        if avisos:
            resumo_cob = '  ATENÇÃO: ' + ', '.join(f'{r} {v:.0%}' for r, v in avisos)
        print(f'   {nome_linha}: {len(frames)} frames, célula {tam[0]}x{tam[1]}{resumo_cob}')
    with open(os.path.join(args.saida_dir, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print(f'\n{total} frames gravados em {args.saida_dir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
