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
    rampa = np.clip((lum_fundo - lum.astype(np.float32)) / max(12.0, lum_fundo * 0.42), 0.0, 1.0)

    # Interior fica OPACO; a rampa de alfa vale só na primeira camada de pixels
    # em volta do fundo (anti-alias). Sem isso, detalhe claro dentro do desenho
    # — o miolo branco da bola de relâmpago — vira transparente por ser mais
    # claro que o fundo da prancha.
    em_volta = ndimage.binary_dilation(fundo, np.ones((3, 3), bool)) & ~fundo
    alfa = np.ones(lum.shape, dtype=np.float32)
    alfa[em_volta] = rampa[em_volta]
    alfa[fundo] = 0.0
    # halo claro colado no fundo: atenua só o que está nessa camada
    halo = em_volta & (alfa < ALFA_SOLIDO) & (dist < TOL_HALO)
    alfa[halo] = np.clip(alfa[halo] - 0.25, 0.0, 1.0)

    rgba = np.dstack([np.asarray(recorte.convert('RGB')), (alfa * 255).astype(np.uint8)])
    return Image.fromarray(rgba.astype(np.uint8), 'RGBA')


def remover_grade_interna(im: Image.Image, cobertura: float = 0.45,
                          sat_max: int = 30, lum_min: float = 115.0,
                          lum_max: float = 999.0) -> Image.Image:
    """Apaga as linhas de grade que a prancha desenha DENTRO da célula.

    Essas linhas são cinzas ou brancas (mais escuras ou mais claras que o fundo)
    e atravessam a célula inteira; o personagem ocupa só um trecho. O critério é
    a linearidade: linha que cobre boa parte da célula. Só os pixels neutros
    (baixa saturação) são apagados, então o desenho que cruza a linha continua
    inteiro. O miolo branco de uma magia é neutro, mas não é linear — por isso
    sobrevive.
    """
    dados = np.asarray(im).copy()
    alfa = dados[..., 3]
    rgb = dados[..., :3].astype(np.int16)
    lum = luminancia(rgb)
    sat = saturacao(rgb)
    cinza = (sat < sat_max) & (lum > lum_min) & (lum < lum_max)
    apagados = 0
    for horizontal in (True, False):
        # linha horizontal: fração de cinza por LINHA (axis=1); vertical: por coluna
        frac = cinza.mean(axis=1) if horizontal else cinza.mean(axis=0)
        idx = np.where(frac >= cobertura)[0]
        if idx.size == 0:
            continue
        mascara = np.zeros_like(cinza, dtype=bool)
        if horizontal:
            mascara[idx, :] = cinza[idx, :]
        else:
            mascara[:, idx] = cinza[:, idx]
        alfa[mascara] = 0
        apagados += int(mascara.sum())
    dados[..., 3] = alfa
    return Image.fromarray(dados, 'RGBA')


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


def vale_do_rotulo(img: Image.Image, ya: int, yb: int,
                    minimo_rel: float = 0.55, maximo_rel: float = 0.96) -> int:
    """Y onde o desenho termina — o vale de conteúdo antes do rótulo impresso.

    A faixa do rótulo é o rodapé da célula, mas ela não tem altura fixa: com um
    corte por porcentagem o pé do personagem (ou a sombra dele) entra no corte.
    O que separa desenho de texto é o vazio entre os dois, e é ele que se procura
    no último terço da célula.
    """
    dados = np.asarray(img.convert('RGB')).astype(np.int16)[ya:yb]
    conteudo = (luminancia(dados) < LUM_FUNDO - 15) | (saturacao(dados) > SAT_CONTEUDO)
    if conteudo.size == 0:
        return yb
    perfil = conteudo.sum(axis=1).astype(np.float64)
    nucleo = np.ones(3) / 3.0
    perfil = np.convolve(perfil, nucleo, mode='same')
    altura = yb - ya
    i0 = int(altura * minimo_rel)
    i1 = max(i0 + 1, int(altura * maximo_rel))
    if i1 - i0 < 2:
        return yb
    return ya + int(i0 + int(np.argmin(perfil[i0:i1])))


def massas_por_celula(img: Image.Image, linhas: Sequence[Tuple[int, int]],
                      colunas: Sequence[Tuple[int, int]], bases: Sequence[int],
                      erosao: int = 2, dist_max: int = 6,
                      min_massa: int = 150) -> Dict[Tuple[int, int], Tuple[List[Tuple[int, int, int, int]], int]]:
    """Acha CADA desenho da prancha e diz a que célula ele pertence.

    A grade da prancha é regular; o desenho não é — a bola de magia atravessa a
    fronteira e sobra um pedaço na célula do vizinho. Aqui a decisão não é a
    posição na grade, e sim o desenho: o conteúdo é afinado (erosão) até a grade
    e o texto sumirem, cada massa que resta é rotulada e vai para a célula onde
    está o seu CENTRO. Assim um quadro inteiro (corpo + magia + partículas) é
    montado como união das massas dele, mesmo que uma massa passe da fronteira.
    """
    dados = np.asarray(img.convert('RGB')).astype(np.int16)
    conteudo = (luminancia(dados) < LUM_FUNDO - 15) | (saturacao(dados) > SAT_CONTEUDO)
    for (ya, yb), base in zip(linhas, bases):  # o rótulo (embaixo) não é desenho
        conteudo[base:yb + 1] = False

    nucleo = ndimage.binary_erosion(conteudo, np.ones((3, 3), bool), iterations=erosao)
    rot, n = ndimage.label(nucleo, np.ones((3, 3), int))
    if n == 0:
        return {}
    _, idx = ndimage.distance_transform_edt(~nucleo, return_indices=True)
    dist = ndimage.distance_transform_edt(~nucleo)
    rot_final = np.where(dist <= dist_max, rot[idx[0], idx[1]], 0)

    # referência de área: só o que é DESENHO de verdade na máscara original
    # (a franja de reconstrução em volta do núcleo não conta)
    desenho_da_massa = rot_final > 0
    por_celula: Dict[Tuple[int, int], Tuple[List[Tuple[int, int, int, int]], int]] = {}
    for i in range(1, n + 1):
        sel = rot_final == i
        area_massa = int((conteudo & sel).sum())
        if area_massa < min_massa:
            continue
        if area_massa < min_massa:
            continue
        ys, xs = np.where(sel)
        cx, cy = int(xs.mean()), int(ys.mean())
        j = next((k for k in range(len(linhas)) if linhas[k][0] <= cy <= linhas[k][1]), None)
        i_ = next((k for k in range(len(colunas)) if colunas[k][0] <= cx <= colunas[k][1]), None)
        if j is None or i_ is None:
            continue
        caixa = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
        caixas, area = por_celula.get((j, i_), ([], 0))
        caixas.append(caixa)
        por_celula[(j, i_)] = (caixas, area + area_massa)
    return por_celula


def ajustar_fronteiras(img: Image.Image, colunas: Sequence[Tuple[int, int]],
                       topo: int, base: int, janela: int = 60,
                       min_larg: int = 40) -> List[Tuple[int, int]]:
    """Recoloca cada fronteira de coluna no vazio mais próximo, NESTA linha.

    A grade da prancha é regular, mas o desenho não: partículas da magia
    atravessam a fronteira e um pedaço do quadro fica na célula do vizinho. Como
    a faixa vazia entre dois quadros existe e é larga, a fronteira vai para o
    ponto de menor conteúdo dentro de uma janela em volta da posição original.
    A numeração do topo é ignorada (só o miolo da célula entra na conta).
    """
    if janela <= 0 or len(colunas) < 2:
        return list(colunas)
    margem = int((base - topo) * 0.22)          # fora a numeração da célula
    a0, a1 = topo + margem, base
    if a1 - a0 < 8:
        return list(colunas)
    rgb = np.asarray(img.convert('RGB')).astype(np.int16)[a0:a1]
    conteudo = (luminancia(rgb) < LUM_FUNDO - 15) | (saturacao(rgb) > SAT_CONTEUDO)
    perfil = conteudo.sum(axis=0).astype(np.float64)
    if perfil.size > 4:                          # suaviza p/ não cair em ruído
        nucleo = np.ones(5) / 5.0
        perfil = np.convolve(perfil, nucleo, mode='same')
    novas = [(colunas[0][0], colunas[0][1])]
    for k in range(1, len(colunas)):
        limite = colunas[k][0]
        esq = max(colunas[k - 1][0] + min_larg, limite - janela)
        dir_ = min(colunas[k][1] - min_larg, limite + janela)
        novo = limite
        if esq < dir_:
            trecho = perfil[esq:dir_]
            if trecho.size:
                novo = int(esq + int(np.argmin(trecho)))
        novas[-1] = (novas[-1][0], novo)
        novas.append((novo, colunas[k][1]))
    return novas


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
    ap.add_argument('--grade', choices=['auto', 'manual', 'explicita', 'componentes'], default='auto')
    ap.add_argument('--min-massa', type=int, default=150,
                    help='px: massa mínima p/ contar como desenho no modo componentes')
    ap.add_argument('--colunas-x', default=None,
                    help='fronteiras verticais das colunas, ex.: "18,175,346,520,691,858,1049,1238"')
    ap.add_argument('--linhas-y', default=None,
                    help='fronteiras horizontais das linhas, ex.: "47,163,273,390,511,635,753"')
    ap.add_argument('--x0', type=int, default=0)
    ap.add_argument('--y0', type=int, default=0)
    ap.add_argument('--celula', default='148x72', help='largura x altura da célula (grade manual)')
    ap.add_argument('--colunas', type=int, default=0, help='nº de colunas de animação (0 = todas)')
    ap.add_argument('--linhas', type=int, default=0, help='nº de linhas de animação (0 = todas)')
    ap.add_argument('--fracao-rotulo', type=float, default=FRACAO_ROTULO,
                    help='fração inferior da célula reservada ao rótulo (descartada)')
    ap.add_argument('--ajustar-fronteiras', type=int, default=0, metavar='JANELA',
                    help='px: procura o vazio mais próximo p/ cada fronteira de coluna (0 = desliga)')
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

    if args.grade == 'componentes':
        if not (args.colunas_x and args.linhas_y):
            raise SystemExit('--grade componentes exige --colunas-x e --linhas-y')
        cxs = [int(v) for v in args.colunas_x.split(',')]
        lys = [int(v) for v in args.linhas_y.split(',')]
        colunas = list(zip(cxs, cxs[1:]))
        linhas = list(zip(lys, lys[1:]))
    elif args.grade == 'explicita':
        if not (args.colunas_x and args.linhas_y):
            raise SystemExit('--grade explicita exige --colunas-x e --linhas-y')
        cxs = [int(v) for v in args.colunas_x.split(',')]
        lys = [int(v) for v in args.linhas_y.split(',')]
        colunas = list(zip(cxs, cxs[1:]))
        linhas = list(zip(lys, lys[1:]))
    elif args.grade == 'auto':
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

    massas = None
    bases = None
    if args.grade == 'componentes':
        bases = [vale_do_rotulo(img, ya, yb) for ya, yb in linhas]
        print('   fim do desenho por linha: ' +
              ', '.join(f'L{j+1}={b}' for j, b in enumerate(bases)))
        massas = massas_por_celula(img, linhas, colunas, bases,
                                   min_massa=args.min_massa)
        vazias = [(j + 1, i + 1) for j in range(len(linhas)) for i in range(len(colunas))
                  if not massas.get((j, i))]
        if vazias:
            print('   ATENÇÃO: células sem desenho: ' +
                  ', '.join(f'L{j}C{i}' for j, i in vazias))

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
        base = bases[j] if bases is not None else yb - corte
        if base - topo < 12:
            continue
        nome_linha, rotulos = rotulos_da_linha(mapa, indice_linha + 1, len(colunas))
        colunas_linha = ajustar_fronteiras(img, colunas, topo, base, args.ajustar_fronteiras)
        frames, usados, avisos, preservacao = [], [], [], 1.0
        for i, (xa, xb) in enumerate(colunas_linha):
            if massas is not None:
                # recorte = união dos desenhos desta célula (não a grade)
                dados_celula = massas.get((j, i))
                if not dados_celula:
                    continue
                caixas, area_ref = dados_celula
                x0 = max(0, min(c[0] for c in caixas) - FOLGA)
                y0 = max(topo, min(c[1] for c in caixas) - FOLGA)
                x1 = min(W, max(c[2] for c in caixas) + FOLGA + 1)
                y1 = min(yb, max(c[3] for c in caixas) + FOLGA + 1)
            else:
                x0, y0, x1, y1 = xa + 2, topo, xb - 2, base
            celula = img.crop((x0, y0, x1, y1))
            if celula.width < 12 or celula.height < 12:
                continue
            rec = alfa_do_fundo(celula, TOL_FUNDO)
            rec = remover_grade_interna(rec)
            rec = limpar_residuo(rec)
            rec = aparar(rec)
            if rec.width <= 3 or rec.height <= 3:
                continue
            rotulo = rotulos[i] if i < len(rotulos) else f'frame{i+1:02d}'
            if massas is not None:
                # no modo componentes o que vale é a fração do DESENHO que ficou,
                # não a fração da célula da grade (que contém desenho do vizinho)
                razao = min(1.0, int((np.asarray(rec)[..., 3] > 24).sum()) / max(1, area_ref))
            else:
                razao = cobertura(celula, rec)
            if razao < 0.85:
                avisos.append((rotulo, razao))
            frames.append(rec)
            usados.append(rotulo)
            preservacao = min(preservacao, razao)
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
            'preservacao_minima': round(preservacao, 3),
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
