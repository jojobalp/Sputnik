#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
limpar_sprites.py — limpeza e correção de spritesheets exportados do Aseprite.

O script NÃO depende do Aseprite: ele trabalha no par PNG + JSON (o mesmo par que
o jogo e a Unity consomem) e mantém o layout original (mesma ordem, mesmo tamanho
de célula, mesmos retângulos no JSON), de modo que nada precisa mudar no jogo.

Uso:
    # 1) só diagnostica, sem alterar nada
    python3 tools/limpar_sprites.py --dir Sprite/Enemies --report

    # 2) aplica as correções (sobrescreve o PNG; o JSON não muda)
    python3 tools/limpar_sprites.py --dir Sprite/Enemies --fix

Correções aplicadas por --fix:
    [E] Pixels soltos    : componentes de até --max-solto px que não estão ligados
                           ao desenho principal (lixo de pincel/borracha).
    [P] Paleta           : cores "órfãs" (menos de --min-cor px no sheet inteiro)
                           são aproximadas da cor canônica mais próxima.
    [T] Transparentes    : pixels com alpha=0 mas com cor (halo invisível que
                           vaza ao filtrar em atlas) são zerados para (0,0,0,0).
    [M] Margem           : se o desenho de uma animação encosta na borda da
                           célula, a animação inteira é deslocada na horizontal
                           para manter --margem px de folga (atlas-safe).

Obs.: todas as correções são determinísticas e documentadas no JSON de relatório
(--edits), o que permite auditar e reverter qualquer alteração.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Sequence, Tuple

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow é necessário: pip install pillow")

# --------------------------------------------------------------------------- #
# parâmetros padrão
# --------------------------------------------------------------------------- #
MAX_SOLTO = 3        # px: componentes desconectados até este tamanho = lixo
DIST_SOLTO = 3       # px: só remove se estiver a >= isso do desenho principal
MIN_COR = 25         # px: cores abaixo disso no sheet inteiro são "órfãs"
MARGEM = 1           # px: folga mínima entre desenho e borda da célula
SHIFT_MAX = 4        # px: deslocamento máximo permitido para corrigir margem
VIZINHOS = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))


# --------------------------------------------------------------------------- #
# leitura do sheet
# --------------------------------------------------------------------------- #
def ler_json(caminho: str) -> dict:
    with open(caminho, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def ordem_frames(dados_json: dict) -> List[Tuple[int, dict]]:
    """Retorna [(índice, frame_json)] ordenado pelo sufixo numérico do nome."""
    itens = []
    for nome, frame in dados_json['frames'].items():
        sufixo = nome.rsplit(' ', 1)[-1].replace('.aseprite', '')
        itens.append((int(sufixo), frame))
    return sorted(itens, key=lambda t: t[0])


def ler_tags(dados_json: dict) -> List[dict]:
    return list(dados_json.get('meta', {}).get('frameTags', []))


# --------------------------------------------------------------------------- #
# utilidades de pixel
# --------------------------------------------------------------------------- #
def componentes(px, largura: int, altura: int) -> List[List[Tuple[int, int]]]:
    """Componentes conectados (8-vizinhos) dos pixels opacos de uma célula."""
    visto = [[False] * altura for _ in range(largura)]
    saida = []
    for y in range(altura):
        for x in range(largura):
            if px[x, y][3] == 0 or visto[x][y]:
                continue
            pilha = [(x, y)]
            visto[x][y] = True
            pontos = []
            while pilha:
                cx, cy = pilha.pop()
                pontos.append((cx, cy))
                for dx, dy in VIZINHOS:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < largura and 0 <= ny < altura and not visto[nx][ny] and px[nx, ny][3]:
                        visto[nx][ny] = True
                        pilha.append((nx, ny))
            saida.append(pontos)
    return saida


def bbox(pontos: Sequence[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    xs = [p[0] for p in pontos]
    ys = [p[1] for p in pontos]
    return min(xs), min(ys), max(xs), max(ys)


def dist_cor(a, b) -> int:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def dist_cheby(pontos_a: Sequence[Tuple[int, int]], pontos_b: Sequence[Tuple[int, int]]) -> int:
    """Menor distância de Chebyshev entre dois conjuntos de pixels."""
    return min(max(abs(ax - bx), abs(ay - by)) for ax, ay in pontos_a for bx, by in pontos_b)


def separar_componentes(px, largura: int, altura: int,
                        max_solto: int = MAX_SOLTO, dist_solto: int = DIST_SOLTO):
    """Componentes ordenados: (principal, [candidatos a lixo], [mantidos]).

    Um componente pequeno só entra como lixo se estiver a >= dist_solto px do
    componente principal — assim partículas de fumaça/poeira que tocam o desenho
    são preservadas.
    """
    comps = componentes(px, largura, altura)
    if not comps:
        return [], [], []
    comps.sort(key=len, reverse=True)
    principal, resto = comps[0], comps[1:]
    lixo, mantidos = [], []
    for c in resto:
        if len(c) <= max_solto and dist_cheby(c, principal) >= dist_solto:
            lixo.append(c)
        else:
            mantidos.append(c)
    return principal, lixo, mantidos


def paleta_do_sheet(pixels: Sequence[Tuple[int, int, int]], min_cor: int):
    """Separa cores canônicas (>= min_cor px) das órfãs e devolve o mapa de snap."""
    contagem = Counter(pixels)
    canonicas = [c for c, n in contagem.items() if n >= min_cor]
    if not canonicas:  # sheet muito pequeno: usa a cor mais frequente
        canonicas = [contagem.most_common(1)[0][0]]
    mapa = {}
    for cor, n in contagem.items():
        if n >= min_cor:
            continue
        alvo = min(canonicas, key=lambda c: dist_cor(c, cor))
        mapa[cor] = (alvo, n)
    return contagem, canonicas, mapa


# --------------------------------------------------------------------------- #
# análise de um sheet
# --------------------------------------------------------------------------- #
class Sheet:
    def __init__(self, caminho_png: str, caminho_json: str):
        self.png = caminho_png
        self.json = caminho_json
        self.nome = os.path.splitext(os.path.basename(caminho_png))[0]
        self.dados = ler_json(caminho_json)
        self.img = Image.open(caminho_png).convert('RGBA')
        self.frames = ordem_frames(self.dados)
        self.tags = ler_tags(self.dados)
        self.celulas = {}          # índice -> pixels da célula (novo objeto)
        self.tamanho = None        # (w, h) da célula
        for i, frame in self.frames:
            r = frame['frame']
            self.tamanho = (r['w'], r['h'])
            self.celulas[i] = self.img.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h'])).copy()

    # -- helpers ---------------------------------------------------------- #
    def tag_do_frame(self) -> Dict[int, str]:
        mapa = {}
        for t in self.tags:
            for i in range(t['from'], t['to'] + 1):
                mapa[i] = t['name']
        return mapa

    def indice_do_nome(self) -> Dict[str, Tuple[int, int]]:
        return {t['name']: (t['from'], t['to']) for t in self.tags}

    def pontos(self, i: int) -> List[Tuple[int, int]]:
        px = self.celulas[i].load()
        largura, altura = self.tamanho
        return [(x, y) for y in range(altura) for x in range(largura) if px[x, y][3]]

    def bbox_principal(self, i: int, max_solto: int = MAX_SOLTO,
                       dist_solto: int = DIST_SOLTO) -> Tuple[int, int, int, int]:
        """bbox só do desenho principal (ignora partículas soltas)."""
        px = self.celulas[i].load()
        principal, _, _ = separar_componentes(px, *self.tamanho, max_solto, dist_solto)
        return bbox(principal) if principal else (0, 0, 0, 0)

    # -- diagnóstico ------------------------------------------------------ #
    def diagnosticar(self, max_solto: int, min_cor: int, margem: int, dist_solto: int = DIST_SOLTO) -> dict:
        rel = {
            'sheet': self.nome,
            'png': self.png,
            'tamanho_celula': self.tamanho,
            'tamanho_sheet': self.img.size,
            'frames': len(self.frames),
            'tags': [{'nome': t['name'], 'de': t['from'], 'ate': t['to'],
                      'frames': t['to'] - t['from'] + 1} for t in self.tags],
            'duracao_ms': sorted(Counter(f['duration'] for _, f in self.frames).items()),
            'solto': [],
            'soltos_colados': [],
            'cores_orfas': [],
            'transparentes_coloridos': {'pixels': 0, 'cores': []},
            'borda': [],
            'frames_iguais': [],
        }

        # frames com pixels idênticos (possível duplicata)
        assinaturas = defaultdict(list)
        for i, _ in self.frames:
            assinaturas[self.celulas[i].tobytes()].append(i)
        rel['frames_iguais'] = [v for v in assinaturas.values() if len(v) > 1]

        todas_cores = []
        largura, altura = self.tamanho
        for i, _ in self.frames:
            px = self.celulas[i].load()
            pts = [(x, y) for y in range(altura) for x in range(largura) if px[x, y][3]]
            todas_cores += [px[x, y][:3] for x, y in pts]

            principal, lixo, mantidos = separar_componentes(px, largura, altura, max_solto, dist_solto)
            for c in lixo:
                cx, cy = c[0]
                rel['solto'].append({'frame': i, 'px': len(c), 'x': cx, 'y': cy,
                                     'cor': '#%02x%02x%02x' % px[cx, cy][:3],
                                     'dist': dist_cheby(c, principal)})
            for c in mantidos:
                if len(c) <= max_solto:
                    cx, cy = c[0]
                    rel['soltos_colados'].append({'frame': i, 'px': len(c), 'x': cx, 'y': cy,
                                                  'dist': dist_cheby(c, principal)})

            # pixels invisíveis mas com cor
            for y in range(altura):
                for x in range(largura):
                    c = px[x, y]
                    if c[3] == 0 and c[:3] != (0, 0, 0):
                        rel['transparentes_coloridos']['pixels'] += 1
                        rel['transparentes_coloridos']['cores'].append('#%02x%02x%02x' % c[:3])

            x0, y0, x1, y1 = bbox(principal)
            if x0 < margem or y0 < margem or x1 > largura - 1 - margem or y1 > altura - 1 - margem:
                rel['borda'].append({'frame': i, 'tag': self.tag_do_frame().get(i),
                                     'bbox': [x0, y0, x1, y1], 'tag_bbox': None})

        # bbox por tag (para decidir o deslocamento da animação inteira)
        por_tag = defaultdict(list)
        for i, _ in self.frames:
            por_tag[self.tag_do_frame().get(i)].append(i)
        for entrada in rel['borda']:
            irm = por_tag[entrada['tag']]
            xs = [self.bbox_principal(i, max_solto, dist_solto) for i in irm]
            entrada['tag_bbox'] = [min(b[0] for b in xs), min(b[1] for b in xs),
                                   max(b[2] for b in xs), max(b[3] for b in xs)]

        contagem, canonicas, mapa = paleta_do_sheet(todas_cores, min_cor)
        rel['paleta'] = {
            'cores_usadas': len(contagem),
            'canonicas': len(canonicas),
            'detalhe': [{'cor': '#%02x%02x%02x' % c, 'px': n} for c, n in contagem.most_common()],
        }
        rel['cores_orfas'] = [{'cor': '#%02x%02x%02x' % c, 'px': mapa[c][1],
                               'sugerida': '#%02x%02x%02x' % mapa[c][0]}
                              for c in sorted(mapa, key=lambda k: -mapa[k][1])]
        rel['transparentes_coloridos']['cores'] = [
            {'cor': c, 'px': n}
            for c, n in Counter(rel['transparentes_coloridos']['cores']).most_common()
        ]
        return rel

    # -- correção --------------------------------------------------------- #
    def corrigir(self, max_solto: int, min_cor: int, margem: int,
                 shift_vertical: bool = False, dist_solto: int = DIST_SOLTO,
                 alinhamento: str = 'minimo') -> dict:
        largura, altura = self.tamanho
        edits = {'sheet': self.nome, 'frames': {}, 'tags': {}}

        # 1) paleta canônica
        todas = []
        for i, _ in self.frames:
            px = self.celulas[i].load()
            todas += [px[x, y][:3] for x, y in self.pontos(i)]
        _, _, mapa_cores = paleta_do_sheet(todas, min_cor)

        # 2) shift por tag para respeitar a margem: escolhe o MENOR deslocamento
        #    possível da animação inteira (evita "pular" o personagem).
        tag_de = self.tag_do_frame()
        shifts: Dict[str, int] = {}
        sem_solucao: List[str] = []
        for nome in {tag_de.get(i) for i, _ in self.frames}:
            if nome is None:      # frames sem tag: tratados individualmente
                continue
            indices = [i for i, _ in self.frames if tag_de.get(i) == nome]
            minx = min(self.bbox_principal(i, max_solto, dist_solto)[0] for i in indices)
            maxx = max(self.bbox_principal(i, max_solto, dist_solto)[2] for i in indices)
            # dx tem de satisfazer: minx+dx >= margem  e  maxx+dx <= largura-1-margem
            esquerda = margem - minx
            direita = (largura - 1 - margem) - maxx
            if esquerda > direita:
                shifts[nome] = 0
                sem_solucao.append(nome)     # arte mais larga que a janela útil
                continue
            if alinhamento == 'centro':
                centro_arte = (minx + maxx) / 2
                centro_celula = (largura - 1) / 2
                desejado = round(centro_celula - centro_arte)
            else:
                desejado = 0
            minimo = max(esquerda, -SHIFT_MAX)
            maximo = min(direita, SHIFT_MAX)
            if minimo > maximo:
                shifts[nome] = 0
                sem_solucao.append(nome)     # não há shift dentro do limite
            else:
                shifts[nome] = int(min(max(desejado, minimo), maximo))
        edits['tags'] = shifts
        edits['tags_sem_solucao'] = sem_solucao

        # 3) aplica pixel a pixel
        for i, _ in self.frames:
            cel = self.celulas[i]
            px = cel.load()
            registro = {'shift': 0, 'solto_removido': [], 'cores_mapeadas': {}, 'transparentes_zerados': 0}

            # 3a) pixels soltos (antes do shift, para registrar coordenadas originais)
            _, lixo, _ = separar_componentes(px, largura, altura, max_solto, dist_solto)
            for c in lixo:
                for x, y in c:
                    cor = px[x, y][:3]
                    px[x, y] = (0, 0, 0, 0)
                    registro['solto_removido'].append([x, y, '#%02x%02x%02x' % cor])

            # 3b) cores órfãs
            for y in range(altura):
                for x in range(largura):
                    c = px[x, y]
                    if c[3] == 0:
                        continue
                    if c[:3] in mapa_cores:
                        nova = mapa_cores[c[:3]][0]
                        px[x, y] = (nova[0], nova[1], nova[2], c[3])
                        chave = '#%02x%02x%02x' % c[:3]
                        registro['cores_mapeadas'][chave] = registro['cores_mapeadas'].get(chave, 0) + 1

            # 3c) pixels invisíveis mas com cor
            for y in range(altura):
                for x in range(largura):
                    c = px[x, y]
                    if c[3] == 0 and c[:3] != (0, 0, 0):
                        px[x, y] = (0, 0, 0, 0)
                        registro['transparentes_zerados'] += 1

            # 3d) deslocamento horizontal da animação
            dx = shifts.get(tag_de.get(i), 0)
            if dx:
                nova = Image.new('RGBA', (largura, altura), (0, 0, 0, 0))
                nova.paste(cel, (dx, 0))
                cel = nova
                self.celulas[i] = cel
                registro['shift'] = dx

            if registro['solto_removido'] or registro['cores_mapeadas'] or registro['transparentes_zerados'] or dx:
                edits['frames'][str(i)] = registro

        # 4) grava o PNG mantendo o layout original
        saida = self.img.copy()
        for i, frame in self.frames:
            r = frame['frame']
            saida.paste(self.celulas[i], (r['x'], r['y']))
        return edits, saida


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def descobrir_sheets(diretorio: str) -> List[Tuple[str, str]]:
    pares = []
    for arq in sorted(os.listdir(diretorio)):
        if not arq.lower().endswith('.png'):
            continue
        png = os.path.join(diretorio, arq)
        js = os.path.join(diretorio, arq[:-4] + '.json')
        if os.path.exists(js):
            pares.append((png, js))
        else:
            print(f'  ! {arq}: sem JSON do Aseprite ao lado — ignorado')
    return pares


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Limpa e corrige spritesheets Aseprite (PNG+JSON).')
    ap.add_argument('--dir', default='Sprite/Enemies', help='pasta com os pares PNG+JSON')
    ap.add_argument('--report', action='store_true', help='apenas diagnostica')
    ap.add_argument('--fix', action='store_true', help='aplica as correções (sobrescreve o PNG)')
    ap.add_argument('--max-solto', type=int, default=MAX_SOLTO, help='px máx. de um componente solto')
    ap.add_argument('--dist-solto', type=int, default=DIST_SOLTO,
                    help='distância mínima (px) do desenho para tratar como lixo')
    ap.add_argument('--min-cor', type=int, default=MIN_COR, help='px mínimos para uma cor ser canônica')
    ap.add_argument('--margem', type=int, default=MARGEM, help='folga mínima até a borda da célula')
    ap.add_argument('--shift-vertical', action='store_true', help='permite corrigir também o eixo Y')
    ap.add_argument('--alinhamento', choices=['minimo', 'centro'], default='minimo',
                    help="como corrigir a margem: 'minimo' desloca o menos possível; "
                         "'centro' centraliza a arte na célula")
    ap.add_argument('--edits', default=None, help='arquivo JSON de auditoria das correções')
    ap.add_argument('--print-json', action='store_true', help='imprime o relatório em JSON')
    args = ap.parse_args(argv)

    if not args.report and not args.fix:
        args.report = True

    pares = descobrir_sheets(args.dir)
    if not pares:
        print(f'nenhum par PNG+JSON em {args.dir}')
        return 1

    relatorios, auditoria = [], {}
    for png, js in pares:
        sheet = Sheet(png, js)
        rel = sheet.diagnosticar(args.max_solto, args.min_cor, args.margem, args.dist_solto)

        if args.fix:
            edits, saida = sheet.corrigir(args.max_solto, args.min_cor, args.margem,
                                          args.shift_vertical, args.dist_solto, args.alinhamento)
            saida.save(png)
            auditoria[sheet.nome] = edits

            # reconfere o resultado
            verif = Sheet(png, js)
            rel_pos = verif.diagnosticar(args.max_solto, args.min_cor, args.margem, args.dist_solto)
            rel['depois'] = {
                'solto': len(rel_pos['solto']),
                'cores_orfas': len(rel_pos['cores_orfas']),
                'transparentes_coloridos': rel_pos['transparentes_coloridos']['pixels'],
                'borda': len(rel_pos['borda']),
            }
        relatorios.append(rel)

        # ---- impressão legível ----
        print(f'\n=== {rel["sheet"]} ({rel["tamanho_sheet"][0]}x{rel["tamanho_sheet"][1]}, '
              f'célula {rel["tamanho_celula"][0]}x{rel["tamanho_celula"][1]}, {rel["frames"]} frames) ===')
        for t in rel['tags']:
            print(f'   tag {t["nome"]:24s} frames {t["de"]:>2}-{t["ate"]:<2} ({t["frames"]})')
        print(f'   durações distintas: {rel["duracao_ms"]}')
        if rel['frames_iguais']:
            for g in rel['frames_iguais']:
                print(f'   frames idênticos: {g}')
        print(f'   pixels soltos removíveis (<= {args.max_solto}px, >= {args.dist_solto}px do desenho): {len(rel["solto"])}')
        for s in rel['solto']:
            print(f'      frame {s["frame"]:>3}  {s["px"]}px em ({s["x"]},{s["y"]}) {s["cor"]} dist={s["dist"]}')
        print(f'   partículas soltas preservadas (coladas ao desenho): {len(rel["soltos_colados"])}')
        for s in rel['soltos_colados']:
            print(f'      frame {s["frame"]:>3}  {s["px"]}px em ({s["x"]},{s["y"]}) dist={s["dist"]}')
        print(f'   cores órfãs (< {args.min_cor}px): {len(rel["cores_orfas"])}')
        for c in rel['cores_orfas']:
            print(f'      {c["cor"]} ({c["px"]}px) -> {c["sugerida"]}')
        tc = rel['transparentes_coloridos']
        print(f'   pixels transparentes com cor: {tc["pixels"]} {tc["cores"]}')
        print(f'   frames encostando na borda: {len(rel["borda"])}')
        for b in rel['borda']:
            print(f'      frame {b["frame"]:>3} [{b["tag"]}] bbox={b["bbox"]} tag_bbox={b["tag_bbox"]}')
        if args.fix and args.alinhamento != 'minimo':
            print(f'   alinhamento: {args.alinhamento}')
        if args.fix:
            d = rel['depois']
            print(f'   -> DEPOIS: soltos={d["solto"]} órfãs={d["cores_orfas"]} '
                  f'transparentes_coloridos={d["transparentes_coloridos"]} borda={d["borda"]}')

    if args.edits and args.fix:
        os.makedirs(os.path.dirname(args.edits) or '.', exist_ok=True)
        with open(args.edits, 'w', encoding='utf-8') as fh:
            json.dump(auditoria, fh, ensure_ascii=False, indent=2)
        print(f'\nauditoria salva em {args.edits}')

    if args.print_json:
        print(json.dumps(relatorios, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
