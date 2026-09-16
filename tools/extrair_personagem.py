#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrair_personagem.py — recorta um personagem do enemies.aseprite e gera um
.aseprite próprio, pronto para a Unity (Aseprite Importer) e para o Aseprite.

Por que: a arte do bruxo vive dentro de `enemies.aseprite`, junto com os dois
esqueletos (162 frames, 16 tags). Importar esse arquivo na Unity traria os três
personagens misturados e os clipes dos inimigos junto. Aqui os frames do
personagem viram um arquivo independente, com as tags renomeadas (`bruxo_*`) e a
numeração reiniciada em 0.

O arquivo gerado reaproveita os chunks originais (userData, paleta e layer) e os
blobs crus de cada tag, trocando só os nomes e as faixas — assim ele é aceito
tanto pelo Aseprite quanto pelo importador da Unity.

Uso:
    python3 tools/extrair_personagem.py \
        --aseprite "Sprite/Enemies/enemies.aseprite" \
        --personagem bruxo --de 47 --ate 95 \
        --saida Sprite/Characters/bruxo.aseprite
"""

from __future__ import annotations

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corrigir_aseprite import Aseprite, CHUNK_CEL, CHUNK_LAYER, CHUNK_TAGS  # noqa: E402

CHUNK_USERDATA = 0x2007
CHUNK_PALETTE = 0x2019

# layout do chunk de tags (descoberto em corrigir_aseprite._parse_tags):
#   [count 4][cabeçalho 6][ por tag: from 2, to 2, +13 bytes ][ len 2 ][ nome ]
CABECALHO_TAGS = 6
EXTRA_TAG = 13


def blobs_das_tags(corpo: bytes):
    """Devolve (cabeçalho, [(extra, nome, de, ate)]) do chunk de tags."""
    count = struct.unpack('<I', corpo[:4])[0]
    cabecalho = corpo[4:4 + CABECALHO_TAGS]
    pos = 4 + CABECALHO_TAGS
    itens = []
    for _ in range(count):
        de, ate = struct.unpack('<HH', corpo[pos:pos + 4])
        extra = corpo[pos + 4:pos + 4 + EXTRA_TAG]
        pos += 4 + EXTRA_TAG
        tam = struct.unpack('<H', corpo[pos:pos + 2])[0]
        pos += 2
        nome = corpo[pos:pos + tam].decode('ascii')
        pos += tam
        itens.append((extra, nome, de, ate))
    return cabecalho, itens


def montar_tags(cabecalho: bytes, itens) -> bytes:
    corpo = struct.pack('<I', len(itens)) + cabecalho
    for extra, nome, de, ate in itens:
        bruto = nome.encode('ascii')
        corpo += struct.pack('<HH', de, ate) + extra + struct.pack('<H', len(bruto)) + bruto
    return corpo


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Extrai um personagem para um .aseprite próprio.')
    ap.add_argument('--aseprite', required=True, help='.aseprite de origem (com os três personagens)')
    ap.add_argument('--personagem', required=True, help='nome do personagem (ex.: bruxo)')
    ap.add_argument('--de', type=int, required=True, help='primeiro frame do personagem (global)')
    ap.add_argument('--ate', type=int, required=True, help='último frame do personagem (global)')
    ap.add_argument('--saida', required=True, help='caminho do .aseprite gerado')
    args = ap.parse_args(argv)

    asp = Aseprite(args.aseprite)
    total = args.ate - args.de + 1
    if not (0 <= args.de <= args.ate < asp.n_frames):
        raise SystemExit(f'faixa {args.de}-{args.ate} fora dos {asp.n_frames} frames do arquivo')

    # chunks de contexto (vêm do frame 0 do original) e cels do personagem
    contexto = {}
    for ctype, body in asp.frames[0]['chunks']:
        if ctype in (CHUNK_USERDATA, CHUNK_PALETTE, CHUNK_LAYER):
            contexto[ctype] = body

    # tags do personagem, renomeadas e rebaseadas para 0
    cabecalho, itens = blobs_das_tags(next(b for t, b in asp.frames[0]['chunks'] if t == CHUNK_TAGS))
    novas = []
    for extra, nome, de, ate in itens:
        if de < args.de or ate > args.ate:
            continue
        prefixo = nome.split('_')[0]
        if prefixo == args.personagem:
            novo_nome = nome
        else:
            novo_nome = args.personagem + '_' + nome.split('_', 1)[1]
        novas.append((extra, novo_nome, de - args.de, ate - args.de))
    if not novas:
        raise SystemExit('nenhuma tag caiu nessa faixa: confira --de/--ate')
    print(f'tags extraídas ({len(novas)}): ' + ', '.join(f'{n} {d}-{a}' for _, n, d, a in novas))

    # monta os frames novos, preservando o cabeçalho original de cada um
    origem = asp.frames
    telas_originais = {i: asp.tela(i) for i in range(args.de, args.ate + 1)}
    frames = []
    for local in range(total):
        fonte = origem[args.de + local]
        chunks = [(CHUNK_CEL, c) for t, c in fonte['chunks'] if t == CHUNK_CEL]
        if local == 0:
            ordem = [CHUNK_USERDATA, CHUNK_PALETTE]
            chunks = ([(t, contexto[t]) for t in ordem if t in contexto]
                      + [(CHUNK_TAGS, montar_tags(cabecalho, novas))]
                      + ([(CHUNK_LAYER, contexto[CHUNK_LAYER])] if CHUNK_LAYER in contexto else [])
                      + chunks)
        frames.append({'cabecalho': fonte['cabecalho'], 'dur': fonte['dur'], 'chunks': chunks})

    # serializa no mesmo formato do Aseprite
    asp.frames = frames
    asp.n_frames = total
    asp.tags = [{'nome': n, 'de': d, 'ate': a, 'offset': 0} for _, n, d, a in novas]
    saida = asp.serializar()

    os.makedirs(os.path.dirname(args.saida) or '.', exist_ok=True)
    with open(args.saida, 'wb') as fh:
        fh.write(saida)
    print(f'gravado: {args.saida} ({len(saida)} bytes, {total} frames)')

    # relê para conferir
    novo = Aseprite(args.saida)
    print(f'relido: {novo.n_frames} frames, {len(novo.tags)} tags, canvas {novo.largura}x{novo.altura}')
    if novo.n_frames != total:
        raise SystemExit('contagem de frames não bateu na releitura')
    for i in range(total):
        if novo.tela(i).tobytes() != telas_originais[args.de + i].tobytes():
            raise SystemExit(f'frame {i} divergiu do original')
    print('conferido: todos os frames idênticos ao original')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
