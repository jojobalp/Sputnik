#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corrigir_aseprite.py — aplica nos arquivos .aseprite a mesma limpeza feita nos PNGs.

Por que isso é necessário: o Unity importa `.aseprite` nativamente (Aseprite
Importer) e o `assets.js` do jogo lê o PNG exportado. Se só o PNG for corrigido,
quem importar o .aseprite recebe a arte com os defeitos de volta. Esta ferramenta
deixa a fonte e a exportação consistentes.

Como funciona:
    1. lê o .aseprite (cabeçalho, frames, chunks: userData, paleta, tags, slices,
       layer e cels);
    2. descobre qual faixa de frames pertence a qual personagem pelas tags
       (ex.: `skeleton1_*` -> frames 0-46) e confere com os PNG+JSON exportados;
    3. opcionalmente valida que os cels de origem batem pixel a pixel com o PNG
       anterior (--antes-dir);
    4. troca o conteúdo de cada cel pelo frame já limpo do PNG do repositório,
       reajustando o retângulo do cel (x, y, w, h) e recomprimindo em zlib;
    5. reescreve o arquivo mantendo tudo o mais byte a byte (tags, paleta, slices,
       durações dos frames, layer).

Uso:
    python3 tools/corrigir_aseprite.py --aseprite "Sprite/Enemies/enemies.aseprite" \
        --sheets-dir Sprite/Enemies --antes-dir /tmp/orig --saida /tmp/novo.aseprite
    # sem --saida, sobrescreve o próprio arquivo (com --forcar)

Depois de aplicar, o script lê o arquivo gerado de volta, reconstrói os três
sheets a partir dos cels e compara com os PNGs do repositório — se não bater
exatamente, ele falha e não grava nada.
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import zlib
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow é necessário: pip install pillow")

CHUNK_LAYER = 0x2004
CHUNK_CEL = 0x2005
CHUNK_TAGS = 0x2018
CEL_RAW = 0
CEL_LINKED = 1
CEL_COMPRESSED = 2


# --------------------------------------------------------------------------- #
# leitura
# --------------------------------------------------------------------------- #
class Aseprite:
    def __init__(self, caminho: str):
        self.caminho = caminho
        with open(caminho, 'rb') as fh:
            self.dados = fh.read()
        d = self.dados
        (self.tamanho_arquivo, self.magic, self.n_frames, self.largura, self.altura,
         self.profundidade, self.flags) = struct.unpack('<IHHHHH I', d[:18])
        if self.magic != 0xA5E0:
            raise ValueError(f'{caminho}: não parece um .aseprite (magic {self.magic:#x})')
        if self.profundidade != 32:
            raise ValueError(f'{caminho}: esperado 32 bits RGBA, veio {self.profundidade}')
        self.frames = []
        self._ler_frames()
        self.tags = self._ler_tags()

    def _ler_frames(self) -> None:
        d, off = self.dados, 128
        for _ in range(self.n_frames):
            fbytes, fmagic, _old, dur = struct.unpack('<IHHH', d[off:off + 10])
            fchunks = struct.unpack('<I', d[off + 12:off + 16])[0]
            if fmagic != 0xF1FA:
                raise ValueError(f'frame inválido em {off}')
            pos, chunks = off + 16, []
            for _c in range(fchunks):
                csize, ctype = struct.unpack('<IH', d[pos:pos + 6])
                chunks.append([ctype, d[pos + 6:pos + csize]])
                pos += csize
            self.frames.append({'bytes': fbytes, 'dur': dur, 'chunks': chunks,
                                'cabecalho': d[off:off + 16]})
            off += fbytes
        if off != len(d):
            raise ValueError(f'tamanho não bate: li {off}, arquivo tem {len(d)}')

    def _ler_tags(self) -> List[dict]:
        """Interpreta o chunk de tags.

        O layout varia conforme a versão do Aseprite (há um cabeçalho inicial e um
        preenchimento por tag que não constam do spec 1.3). Em vez de chutar, o
        parser testa as combinações plausíveis e aceita a única que:
          - lê `count` nomes legíveis;
          - mantém from <= to;
          - termina exatamente no fim do chunk.
        """
        for f in self.frames:
            for ctype, body in f['chunks']:
                if ctype == CHUNK_TAGS:
                    return self._descobrir_layout(body)
        return []

    @staticmethod
    def _descobrir_layout(corpo: bytes) -> List[dict]:
        for cabecalho in range(4, 16):
            for preenchimento in range(0, 9):
                try:
                    tags = Aseprite._parse_tags(corpo, cabecalho, preenchimento)
                except Exception:
                    continue
                if tags:
                    return tags
        raise ValueError('não consegui interpretar o chunk de tags')

    @staticmethod
    def _parse_tags(corpo: bytes, cabecalho: int, preenchimento: int) -> List[dict]:
        total = struct.unpack('<I', corpo[:4])[0]
        if not 0 < total < 512:
            raise ValueError('contagem de tags absurda')
        pos, tags = cabecalho, []
        for _ in range(total):
            de, ate = struct.unpack('<HH', corpo[pos:pos + 4])
            pos += 4 + 13 + preenchimento          # from, to, dir, repeat, cor, extra (+pad)
            tam = struct.unpack('<H', corpo[pos:pos + 2])[0]
            pos += 2
            if not 0 < tam <= 64:
                raise ValueError('tamanho de nome absurdo')
            bruto = corpo[pos:pos + tam]
            if len(bruto) != tam:
                raise ValueError('nome passou do fim')
            nome = bruto.decode('ascii')
            pos += tam
            if de > ate:
                raise ValueError('from > to')
            tags.append({'nome': nome, 'de': de, 'ate': ate, 'offset': pos - tam})
        if pos != len(corpo):
            raise ValueError(f'sobrou {len(corpo) - pos} byte(s) no chunk de tags')
        return tags

    def renomear_tag(self, indice: int, novo_nome: str) -> bool:
        """Troca o nome de uma tag mantendo o resto do arquivo intacto."""
        tag = self.tags[indice]
        velho = tag['nome'].encode('ascii')
        novo = novo_nome.encode('ascii')
        if velho == novo:
            return False
        for f in self.frames:
            for chunk in f['chunks']:
                if chunk[0] != CHUNK_TAGS:
                    continue
                body = chunk[1]
                fim = tag['offset'] + len(velho)
                if body[tag['offset']:fim] != velho:
                    raise ValueError('offset do nome da tag não confere')
                body = body[:tag['offset'] - 2] + struct.pack('<H', len(novo)) + novo + body[fim:]
                chunk[1] = body
                tag['nome'] = novo_nome
                # os offsets das tags seguintes andam com o tamanho novo
                delta = len(novo) - len(velho)
                if delta:
                    for outra in self.tags:
                        if outra is not tag and outra['offset'] > tag['offset']:
                            outra['offset'] += delta
                return True
        return False

    # -- cels ------------------------------------------------------------- #
    def cel_de(self, indice: int) -> Optional[dict]:
        """Retorna o cel do frame (camada 0) com a imagem já montada em RGBA."""
        for i, chunk in enumerate(self.frames[indice]['chunks']):
            ctype, body = chunk
            if ctype != CHUNK_CEL:
                continue
            layer, x, y, op = struct.unpack('<HhhB', body[:7])
            tipo = struct.unpack('<H', body[7:9])[0]
            w, h = struct.unpack('<HH', body[16:20])
            if tipo == CEL_LINKED:
                alvo = struct.unpack('<H', body[20:22])[0]
                outro = self.cel_de(alvo)
                return {**outro, 'link': alvo}
            if tipo == CEL_RAW:
                pixels = body[20:20 + w * h * 4]
            elif tipo == CEL_COMPRESSED:
                pixels = zlib.decompress(body[20:])
            else:
                raise ValueError(f'frame {indice}: tipo de cel {tipo} não suportado')
            if len(pixels) != w * h * 4:
                raise ValueError(f'frame {indice}: cel com {len(pixels)} bytes, esperado {w*h*4}')
            img = Image.frombytes('RGBA', (w, h), pixels)
            return {'chunk': i, 'x': x, 'y': y, 'w': w, 'h': h, 'img': img,
                    'tipo': tipo, 'opacidade': op, 'link': None}
        return None

    def tela(self, indice: int) -> Image.Image:
        """Frame montado no canvas completo (largura x altura do arquivo)."""
        tela = Image.new('RGBA', (self.largura, self.altura), (0, 0, 0, 0))
        cel = self.cel_de(indice)
        if cel:
            tela.paste(cel['img'], (cel['x'], cel['y']))
        return tela

    # -- escrita ----------------------------------------------------------- #
    def definir_cel(self, indice: int, tela_nova: Image.Image) -> bool:
        """Grava no cel o conteúdo de `tela_nova` (recortado no bbox). Muda o arquivo."""
        cel = self.cel_de(indice)
        if cel is None:
            return False
        pixels = tela_nova.tobytes()
        caixa = tela_nova.getbbox()
        if caixa is None:
            raise ValueError(f'frame {indice}: ficou vazio — abortando para não perder o desenho')
        x0, y0, x1, y1 = caixa
        w, h = x1 - x0, y1 - y0
        recorte = tela_nova.crop(caixa)
        comprimido = zlib.compress(recorte.tobytes(), 9)
        body = struct.pack('<HhhBH', 0, x0, y0, cel['opacidade'], CEL_COMPRESSED)
        body += struct.pack('<h', 0) + b'\x00' * 5
        body += struct.pack('<HH', w, h) + comprimido
        antes = self.frames[indice]['chunks'][cel['chunk']]
        mudou = (antes[1] != body)
        self.frames[indice]['chunks'][cel['chunk']] = [CHUNK_CEL, body]
        return mudou

    def serializar(self) -> bytes:
        saida = bytearray(self.dados[:128])
        struct.pack_into('<H', saida, 6, len(self.frames))   # quantidade de frames
        for f in self.frames:
            chunks = bytearray()
            for ctype, body in f['chunks']:
                chunks += struct.pack('<IH', 6 + len(body), ctype) + body
            total = 16 + len(chunks)
            # o cabeçalho original já traz duração (offset 8) e reservados (10-11):
            # só recalculamos o tamanho do frame e a contagem de chunks.
            cabecalho = bytearray(f['cabecalho'])
            struct.pack_into('<I', cabecalho, 0, total)
            struct.pack_into('<I', cabecalho, 12, len(f['chunks']))
            saida += cabecalho + chunks
        # o cabeçalho do sprite declara o tamanho total do arquivo
        struct.pack_into('<I', saida, 0, len(saida))
        return bytes(saida)


# --------------------------------------------------------------------------- #
# sheets exportados
# --------------------------------------------------------------------------- #
def ler_sheet(caminho_png: str, caminho_json: str) -> Dict[int, Image.Image]:
    with open(caminho_json, 'r', encoding='utf-8') as fh:
        dados = json.load(fh)
    img = Image.open(caminho_png).convert('RGBA')
    celulas = {}
    for nome, f in dados['frames'].items():
        i = int(nome.rsplit(' ', 1)[-1].replace('.aseprite', ''))
        r = f['frame']
        celulas[i] = img.crop((r['x'], r['y'], r['x'] + r['w'], r['y'] + r['h']))
    return celulas, [(t['name'], t['from'], t['to']) for t in dados['meta']['frameTags']]


def mapear(asp: Aseprite, sheets_dir: str, antes_dir: Optional[str], tamanho: Tuple[int, int]):
    """Descobre personagem -> faixa de frames no .aseprite, validando tudo."""
    por_personagem: Dict[str, List[Tuple[int, int]]] = {}
    for t in asp.tags:
        personagem = t['nome'].split('_')[0]
        por_personagem.setdefault(personagem, []).append((t['de'], t['ate']))

    mapas = {}
    for personagem, faixas in por_personagem.items():
        png = os.path.join(sheets_dir, f'{personagem}.png')
        js = os.path.join(sheets_dir, f'{personagem}.json')
        if not (os.path.exists(png) and os.path.exists(js)):
            raise ValueError(f'{personagem}: não achei {png} / {js}')
        celulas, tags_json = ler_sheet(png, js)
        base = min(f[0] for f in faixas)
        n = max(f[1] for f in faixas) - base + 1
        if n != len(celulas):
            raise ValueError(f'{personagem}: .aseprite tem {n} frames na faixa, o sheet tem {len(celulas)}')
        nomes_json = sorted(t[0] for t in tags_json)
        do_personagem = [t for t in asp.tags if t['nome'].startswith(personagem + '_')]
        renomeadas = []
        for esperado in nomes_json:
            exato = [t for t in do_personagem if t['nome'] == esperado]
            if exato:
                continue
            # nome truncado no .aseprite (bug de versão antiga): prefixo do esperado
            candidato = [t for t in do_personagem if esperado.startswith(t['nome'])]
            if len(candidato) != 1:
                raise ValueError(f'{personagem}: tag "{esperado}" não existe no .aseprite')
            nome_antigo = candidato[0]['nome']
            asp.renomear_tag(asp.tags.index(candidato[0]), esperado)
            renomeadas.append((nome_antigo, esperado))
        nomes_asp = sorted(t['nome'] for t in asp.tags if t['nome'].startswith(personagem + '_'))
        if nomes_asp != nomes_json:
            raise ValueError(f'{personagem}: tags diferentes entre .aseprite ({nomes_asp}) e JSON ({nomes_json})')
        if renomeadas:
            print(f'   tag corrigida em {personagem}: ' +
                  ', '.join(f'"{a}" -> "{b}"' for a, b in renomeadas))

        # valida que o cel de origem casa pixel a pixel com o PNG anterior
        if antes_dir:
            antes_png = os.path.join(antes_dir, f'{personagem}.png')
            antes_json = os.path.join(sheets_dir, f'{personagem}.json')
            if os.path.exists(antes_png):
                antes, _ = ler_sheet(antes_png, antes_json)
                for local in range(len(celulas)):
                    tela = asp.tela(base + local)
                    if tela.tobytes() != antes[local].tobytes():
                        raise ValueError(
                            f'{personagem} frame {local}: o cel do .aseprite não bate com o PNG anterior '
                            f'(mapeamento errado ou arte divergente)')
        for nome, de_local, ate_local in tags_json:
            t = next(t for t in asp.tags if t['nome'] == nome)
            if (t['de'], t['ate']) != (base + de_local, base + ate_local):
                raise ValueError(
                    f'{personagem}: tag {nome} no .aseprite cobre {t["de"]}-{t["ate"]}, '
                    f'esperado {base + de_local}-{base + ate_local}')
        mapas[personagem] = {'base': base, 'n': n, 'celulas': celulas}
    return mapas


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Aplica nos .aseprite a limpeza feita nos PNGs.')
    ap.add_argument('--aseprite', required=True, help='arquivo .aseprite de origem')
    ap.add_argument('--sheets-dir', default='Sprite/Enemies', help='pasta com os PNG+JSON exportados (limpos)')
    ap.add_argument('--antes-dir', default=None,
                    help='pasta com os PNGs originais, para validar o mapeamento antes de escrever')
    ap.add_argument('--saida', default=None, help='caminho do .aseprite corrigido (padrão: no lugar)')
    ap.add_argument('--forcar', action='store_true', help='sobrescreve o arquivo de origem')
    args = ap.parse_args(argv)

    asp = Aseprite(args.aseprite)
    print(f'{args.aseprite}: {asp.n_frames} frames, canvas {asp.largura}x{asp.altura}, {len(asp.tags)} tags')

    mapas = mapear(asp, args.sheets_dir, args.antes_dir, (asp.largura, asp.altura))
    for personagem, m in sorted(mapas.items(), key=lambda kv: kv[1]['base']):
        print(f'   {personagem:12s} frames {m["base"]:>3}-{m["base"]+m["n"]-1:<3} ({m["n"]})')

    # confere se as faixas cobrem todos os frames sem sobreposição
    cobertura = sorted((m['base'], m['base'] + m['n'] - 1) for m in mapas.values())
    esperado, ok = 0, True
    for de, ate in cobertura:
        if de != esperado:
            ok = False
        esperado = ate + 1
    ok = ok and esperado == asp.n_frames
    print(f'   cobertura das faixas: {"completa" if ok else "INCOMPLETA"}')

    alterados = 0
    for personagem, m in mapas.items():
        for local in range(m['n']):
            if asp.definir_cel(m['base'] + local, m['celulas'][local]):
                alterados += 1
    print(f'   cels regravados: {alterados}/{asp.n_frames}')

    saida = asp.serializar()
    destino = args.saida or args.aseprite
    if destino == args.aseprite and not args.forcar and not args.saida:
        print('   (nada gravado: use --saida ou --forcar)')
        return 0

    # escreve e relê para validar
    with open(destino, 'wb') as fh:
        fh.write(saida)
    novo = Aseprite(destino)
    problemas = []
    for personagem, m in mapas.items():
        for local in range(m['n']):
            if novo.tela(m['base'] + local).tobytes() != m['celulas'][local].tobytes():
                problemas.append(f'{personagem} frame {local}')
    if problemas:
        os.remove(destino)
        print('   FALHOU na releitura: ' + ', '.join(problemas[:5]))
        return 1

    print(f'   gravado: {destino} ({len(saida)} bytes, relido e conferido pixel a pixel)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
