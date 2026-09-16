#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verificar_aseprite.py — valida os .aseprite contra os PNG+JSON exportados.

É uma checagem independente (parser próprio, escrito do zero, sem reusar o código
de correção) que confirma se a fonte e a exportação continuam idênticas. Serve
para qualquer .aseprite de tira de frames 32x32 com um personagem por faixa de
tags, como os deste repositório.

O que confere:
  - cabeçalho: assinatura, tamanho declarado == tamanho real, profundidade 32bit;
  - estrutura: cada frame tem cabeçalho válido, os chunks cabem no arquivo e o
    arquivo termina exatamente no fim;
  - cels: dentro do canvas, com o número de bytes certo (raw ou zlib);
  - tags: mesmos nomes, mesmas faixas e mesmas direções do JSON do Aseprite;
  - frames: mesma duração, e o frame achatado do .aseprite é pixel a pixel igual
    à célula correspondente no PNG exportado.

Uso:
    python3 tools/verificar_aseprite.py --aseprite Sprite/Enemies/enemies.aseprite \
        --sheets-dir Sprite/Enemies
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import zlib
from typing import Dict, List, Tuple

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow é necessário: pip install pillow")

ERROS: List[str] = []
OKS = 0


def ok(cond: bool, msg: str) -> bool:
    global OKS
    if cond:
        OKS += 1
    else:
        ERROS.append(msg)
    return cond


def ler_arquivo(caminho: str):
    with open(caminho, 'rb') as fh:
        d = fh.read()
    (tam, magic, n_frames, largura, altura, profundidade, flags) = struct.unpack('<IHHHHH I', d[:18])
    ok(magic == 0xA5E0, f'{caminho}: assinatura Aseprite ausente')
    ok(profundidade == 32, f'{caminho}: profundidade {profundidade} (esperado 32)')
    frames, tags = [], []
    off = 128
    for i in range(n_frames):
        ok(off + 16 <= len(d), f'{caminho}: frame {i} começa fora do arquivo')
        fbytes, fmagic, _old, dur = struct.unpack('<IHHH', d[off:off + 10])
        n_chunks = struct.unpack('<I', d[off + 12:off + 16])[0]
        ok(fmagic == 0xF1FA, f'{caminho}: frame {i} sem assinatura de frame')
        pos = off + 16
        cel = None
        cels = []
        for _ in range(n_chunks):
            csize, ctype = struct.unpack('<IH', d[pos:pos + 6])
            body = d[pos + 6:pos + csize]
            ok(pos + csize <= len(d), f'{caminho}: chunk estourou o arquivo no frame {i}')
            if ctype == 0x2005:
                layer, x, y, op = struct.unpack('<HhhB', body[:7])
                tipo = struct.unpack('<H', body[7:9])[0]
                # Onde estão largura/altura da célula depende da versão do
                # Aseprite: >= 1.3 põe WORD z-index + 5 bytes reservados antes
                # delas (offset 16); arquivos antigos vão direto (offset 9).
                # Não há campo de versão no cabeçalho, então vale a checagem:
                # o tamanho tem de caber no canvas e os pixels têm de fechar.
                pixels = w = h = None
                vinculo = None
                if tipo == 1:
                    # célula vinculada: não guarda pixels, aponta para o quadro
                    # que tem a arte (o Aseprite faz isso quando a camada repete)
                    vinculo = struct.unpack('<H', body[9:11])[0] if len(body) >= 11 else None
                    w, h = largura, altura
                else:
                    for inicio in (16, 9):
                        if len(body) < inicio + 4:
                            continue
                        w, h = struct.unpack('<HH', body[inicio:inicio + 4])
                        if not (0 < w <= largura and 0 < h <= altura):
                            continue
                        dados = body[inicio + 4:]
                        if tipo == 0:
                            if len(dados) < w * h * 4:
                                continue
                            pixels = dados[:w * h * 4]
                        else:
                            try:
                                pixels = zlib.decompress(dados)
                            except zlib.error:
                                continue
                            if len(pixels) != w * h * 4:
                                continue
                        break
                if pixels is not None:
                    ok(len(pixels) == w * h * 4,
                       f'{caminho}: frame {i} com {len(pixels)} bytes de pixel, esperado {w*h*4}')
                    ok(-32 <= x and -32 <= y and x + w <= largura + 32 and y + h <= altura + 32,
                       f'{caminho}: cel do frame {i} muito fora do canvas ({x},{y},{w},{h})')
                    imagem = Image.frombytes('RGBA', (w, h), pixels)
                    if op < 255:          # opacidade da célula (camada semitransparente)
                        r, g, b, a = imagem.split()
                        imagem = Image.merge('RGBA', (r, g, b, a.point(lambda v: (v * op) // 255)))
                    cels.append({'x': x, 'y': y, 'img': imagem,
                                 'layer': layer, 'link': vinculo})
                    if cel is None:
                        cel = cels[0]
                elif tipo == 1:
                    # entra na lista mesmo sem pixels: o vínculo é resolvido depois
                    cels.append({'x': x, 'y': y, 'img': None,
                                 'layer': layer, 'link': vinculo})
            elif ctype == 0x2018:
                tags = ler_tags(body)
            pos += csize
        ok(pos == off + fbytes, f'{caminho}: frame {i} não fecha com o tamanho declarado')
        if tipo == 1 and cels:
            pass
        frames.append({'dur': dur, 'cel': cel, 'cels': cels})
        off += fbytes
    resolver_vinculos(frames, largura, altura)
    ok(off == len(d), f'{caminho}: sobrou {len(d) - off} byte(s) no fim do arquivo')
    ok(tam == len(d), f'{caminho}: cabeçalho diz {tam} bytes, arquivo tem {len(d)}')
    return frames, tags, (largura, altura)


def resolver_vinculos(frames: List[dict], largura: int, altura: int) -> None:
    """Traz a arte das células vinculadas para o quadro que só aponta para ela.

    Uma célula vinculada (tipo 1) diz "sou igual à célula da camada tal no quadro
    N". Aqui a corrente é seguida até achar pixels de verdade — sem isso o quadro
    fica sem a parte repetida (num pack, a sombra costuma ser assim).
    """
    for f in frames:
        for c in f['cels']:
            if c.get('img') is not None:
                continue
            atual, visto = c.get('link'), set()
            while atual is not None and atual not in visto:
                visto.add(atual)
                if not (0 <= atual < len(frames)):
                    break
                igual = next((x for x in frames[atual]['cels'] if x.get('layer') == c.get('layer')), None)
                if igual is None:
                    break
                if igual.get('img') is not None:
                    c['img'], c['x'], c['y'] = igual['img'], igual['x'], igual['y']
                    atual = None
                else:
                    atual = igual.get('link')
            if c.get('img') is not None and c.get('link') is not None:
                c['link'] = None


def achatado(frame: dict, canvas: Tuple[int, int]) -> Image.Image:
    """Frame achatado: todas as células coladas na posição dentro do canvas.

    Um .aseprite pode ter mais de uma camada por quadro (o pack "Tiny RPG", por
    exemplo, guarda a sombra numa camada e o personagem noutra) — o export do
    Aseprite achata tudo, então a conferência precisa fazer o mesmo.
    """
    tela = Image.new('RGBA', canvas, (0, 0, 0, 0))
    for c in frame.get('cels') or ([frame['cel']] if frame.get('cel') else []):
        if c.get('img') is None:            # vínculo que não pôde ser resolvido
            continue
        tela.alpha_composite(c['img'], (max(0, c['x']), max(0, c['y'])))
    return tela


def ler_tags(corpo: bytes) -> List[dict]:
    """Mesma descoberta de layout do parser de escrita, mas independente."""
    for cabecalho in range(4, 16):
        for pad in range(0, 9):
            try:
                total = struct.unpack('<I', corpo[:4])[0]
                pos, saida = cabecalho, []
                for _ in range(total):
                    de, ate = struct.unpack('<HH', corpo[pos:pos + 4])
                    pos += 4 + 13 + pad
                    tam = struct.unpack('<H', corpo[pos:pos + 2])[0]
                    pos += 2
                    nome = corpo[pos:pos + tam].decode('ascii')
                    pos += tam
                    if de > ate or not nome:
                        raise ValueError
                    saida.append({'nome': nome, 'de': de, 'ate': ate})
                if pos == len(corpo):
                    return saida
            except Exception:
                continue
    return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Valida .aseprite contra os PNG+JSON exportados.')
    # (as opções estão logo abaixo)
    ap.add_argument('--aseprite', required=True)
    ap.add_argument('--sheets-dir', default='Sprite/Enemies')
    ap.add_argument('--sem-sheets', action='store_true',
                    help='confere só o .aseprite (útil para arquivo de terceiros, '
                         'que não tem sheet no projeto)')
    ap.add_argument('--alias', action='append', default=[], metavar='ORIGEM=DESTINO',
                    help='tag exportada com outro nome, ex.: "vampire=Sprite/Characters/bruxo" '
                         '(no .aseprite a linha ainda se chama vampire; o PNG+JSON saiu '
                         'como bruxo)')
    args = ap.parse_args(argv)

    frames, tags, canvas = ler_arquivo(args.aseprite)
    print(f'{args.aseprite}: {len(frames)} frames, canvas {canvas[0]}x{canvas[1]}, {len(tags)} tags')

    aliases = {}
    for item in args.alias:
        if '=' not in item:
            raise SystemExit(f'--alias inválido: {item!r} (use "origem=destino")')
        origem, destino = item.split('=', 1)
        aliases[origem.strip()] = destino.strip()

    if args.sem_sheets:
        print('(--sem-sheets: só a fonte, sem comparar com PNG+JSON)')
        return 0 if not ERROS else 1

    por_personagem: Dict[str, List[Tuple[int, int]]] = {}
    for t in tags:
        por_personagem.setdefault(t['nome'].split('_', 1)[0], []).append((t['de'], t['ate']))

    for personagem, faixas in sorted(por_personagem.items(), key=lambda kv: min(f[0] for f in kv[1])):
        destino = aliases.get(personagem, os.path.join(args.sheets_dir, personagem))
        # o prefixo das tags segue o nome do arquivo exportado
        prefixo_json = os.path.basename(destino)
        png = f'{destino}.png'
        js = f'{destino}.json'
        if not (os.path.exists(png) and os.path.exists(js)):
            ERROS.append(f'{personagem}: falta {png} ou {js}')
            continue
        with open(js, encoding='utf-8') as fh:
            dados = json.load(fh)
        img = Image.open(png).convert('RGBA')
        celulas = {}
        duracoes = {}
        for nome, f in dados['frames'].items():
            i = int(nome.rsplit(' ', 1)[-1].replace('.aseprite', ''))
            r = f['frame']
            celulas[i] = img.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h']))
            duracoes[i] = f['duration']
        base = min(f[0] for f in faixas)

        # tags: nome, faixa e ordem
        do_json = {t['name']: (t['from'], t['to']) for t in dados['meta']['frameTags']}
        do_asp = {}
        for t in tags:
            if t['nome'].split('_', 1)[0] != personagem:
                continue
            sufixo = t['nome'].split('_', 1)[1] if '_' in t['nome'] else ''
            nome_local = f'{prefixo_json}_{sufixo}' if sufixo else prefixo_json
            do_asp[nome_local] = (t['de'] - base, t['ate'] - base)
        ok(set(do_json) == set(do_asp),
           f'{personagem}: tags divergentes — só no JSON: {sorted(set(do_json)-set(do_asp))}; '
           f'só no .aseprite: {sorted(set(do_asp)-set(do_json))}')
        for nome in set(do_json) & set(do_asp):
            ok(do_json[nome] == do_asp[nome],
               f'{personagem}: tag {nome} — JSON {do_json[nome]} vs .aseprite {do_asp[nome]}')

        # conteúdo e duração de cada frame
        diferentes, duracoes_diferentes = [], []
        for local in range(len(celulas)):
            asp_frame = frames[base + local]
            if asp_frame['cel'] is None:
                diferentes.append(local)
                continue
            tela = achatado(asp_frame, canvas)
            if tela.tobytes() != celulas[local].tobytes():
                diferentes.append(local)
            if asp_frame['dur'] != duracoes[local]:
                duracoes_diferentes.append((local, asp_frame['dur'], duracoes[local]))
        ok(not diferentes, f'{personagem}: {len(diferentes)} frame(s) divergem do PNG: {diferentes[:8]}')
        ok(not duracoes_diferentes, f'{personagem}: durações divergentes: {duracoes_diferentes[:5]}')
        print(f'   {personagem:12s} {len(celulas):>3} frames conferidos'
              f'{" (ok)" if not diferentes else " (DIVERGENTE)"}')

    print(f'\nchecagens: {OKS}')
    if ERROS:
        print('ERROS:')
        for e in ERROS:
            print('  x', e)
        return 1
    print('tudo certo: .aseprite e PNG+JSON exportados são idênticos.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
