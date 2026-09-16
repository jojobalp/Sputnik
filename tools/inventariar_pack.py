#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inventariar_pack.py — lê um pack de terceiros e escreve o inventário dele.

Pack comprado/baixado chega com uma estrutura própria (uma tira por animação,
células grandes com o desenho no meio, às vezes duas versões — com e sem sombra).
Antes de usar essa arte é preciso saber exatamente o que tem dentro: quantos
quadros tem cada animação, quanto dura, onde o desenho fica dentro da célula e se
as tiras exportadas batem com os .aseprite de origem.

Este script responde isso e grava um `manifest.json`, sem tocar em nenhum arquivo
do pack.

Uso:
    python3 tools/inventariar_pack.py --aseprite art/pack/aseprite/*.aseprite \\
        --saida art/pack/manifest.json --conferir-pasta art/pack
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    'verificar_aseprite', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       'verificar_aseprite.py'))
va = importlib.util.module_from_spec(_spec)
sys.modules['verificar_aseprite'] = va
_spec.loader.exec_module(va)          # o main() só roda sob __main__, então é seguro


def achatado(frame: dict, canvas: Tuple[int, int]) -> Optional[Image.Image]:
    """Frame achatado (todas as camadas coladas no canvas)."""
    if not (frame.get('cels') or frame.get('cel')):
        return None
    return va.achatado(frame, canvas)


def caixa_do_desenho(frames: List[dict], canvas: Tuple[int, int],
                     alfa_min: int = 200) -> Optional[Tuple[int, int, int, int]]:
    """Menor retângulo que contém todo o desenho de uma animação."""
    x0 = y0 = 10 ** 9
    x1 = y1 = -1
    for f in frames:
        tela = achatado(f, canvas)
        if tela is None:
            continue
        a = np.asarray(tela)[..., 3] > alfa_min
        ys, xs = np.where(a)
        if xs.size == 0:
            continue
        x0, y0 = min(x0, int(xs.min())), min(y0, int(ys.min()))
        x1, y1 = max(x1, int(xs.max())), max(y1, int(ys.max()))
    return None if x1 < 0 else (x0, y0, x1, y1)


def inventariar(caminho: str) -> Dict:
    frames, tags, canvas = va.ler_arquivo(caminho)
    personagem = os.path.basename(caminho).rsplit('.', 1)[0]
    animacoes = []
    for t in tags:
        qs = frames[t['de']:t['ate'] + 1]
        caixa = caixa_do_desenho(qs, canvas)
        animacoes.append({
            'nome': t['nome'],
            'quadros': len(qs),
            'quadros_ms': [f['dur'] for f in qs],
            'duracao_ms': sum(f['dur'] for f in qs),
            'caixa': list(caixa) if caixa else None,
        })
    caixa = caixa_do_desenho(frames, canvas)
    return {
        'aseprite': caminho.replace('\\', '/'),
        'canvas': list(canvas),
        'quadros': len(frames),
        'animacoes': animacoes,
        'desenho': None if not caixa else {
            'caixa': list(caixa),
            'largura': caixa[2] - caixa[0] + 1,
            'altura': caixa[3] - caixa[1] + 1,
            'pe': caixa[3],                       # linha dos pés (pivô no jogo)
            'centro_x': round((caixa[0] + caixa[2]) / 2, 1),
        },
    }


def conferir_com_tiras(arquivo: Dict, pastas: List[str]) -> List[Dict]:
    """Compara cada animação do .aseprite com a tira exportada do pack.

    O pack traz uma tira por animação (`Soldier_Idle.png`, `Orc_Walk.png`…) com a
    célula do mesmo tamanho do canvas. Aqui o frame achatado do .aseprite é
    comparado pixel a pixel com a célula da tira: é o que prova se a fonte e as
    tiras são a mesma arte (e qual das variantes — com ou sem sombra — a fonte
    contém).
    """
    frames, tags, canvas = va.ler_arquivo(arquivo['aseprite'])
    personagem = os.path.basename(arquivo['aseprite']).rsplit('.', 1)[0]
    cw, ch = canvas
    resultados = []
    for t in tags:
        alvo = f'{personagem}_{t["nome"]}.png'
        candidatos = []
        for pasta in pastas:                       # a primeira pasta que tiver a tira
            achados = sorted(glob.glob(os.path.join(pasta, alvo))) or \
                sorted(glob.glob(os.path.join(pasta, '**', alvo), recursive=True))
            if achados:
                candidatos = achados
                break
        if not candidatos:
            continue
        tira = Image.open(candidatos[0]).convert('RGBA')
        n_tira = max(1, tira.width // cw)
        iguais = 0
        for k in range(min(n_tira, t['ate'] - t['de'] + 1)):
            cel = tira.crop((k * cw, 0, (k + 1) * cw, ch))
            flt = achatado(frames[t['de'] + k], canvas)
            if flt is None:
                continue
            if np.array_equal(np.asarray(cel), np.asarray(flt)):
                iguais += 1
        resultados.append({
            'animacao': t['nome'],
            'tira': candidatos[0].replace('\\', '/'),
            'quadros_na_tira': n_tira,
            'quadros_na_fonte': t['ate'] - t['de'] + 1,
            'quadros_identicos': iguais,
        })
    return resultados


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Inventaria um pack de sprites de terceiros.')
    ap.add_argument('--aseprite', nargs='+', required=True)
    ap.add_argument('--saida', default=None, help='onde gravar o manifest.json')
    ap.add_argument('--conferir-pasta', action='append', default=[],
                    help='pasta com as tiras do pack, para comparar com a fonte '
                         '(pode repetir: a primeira que tiver a tira vale)')
    ap.add_argument('--nome', default=None, help='nome do pack no manifest')
    args = ap.parse_args()

    inventario = {'pack': args.nome or os.path.basename(os.path.abspath(args.aseprite[0])),
                  'personagens': {}}
    for caminho in sorted(args.aseprite):
        dados = inventariar(caminho)
        personagem = os.path.basename(caminho).rsplit('.', 1)[0]
        if args.conferir_pasta:
            dados['conferencia_tiras'] = conferir_com_tiras(dados, args.conferir_pasta)
        inventario['personagens'][personagem] = dados

        d = dados['desenho']
        print(f'{personagem}: {dados["quadros"]} quadros, canvas {dados["canvas"][0]}x{dados["canvas"][1]}')
        if d:
            print(f'   desenho: {d["largura"]}x{d["altura"]} px, pés na linha y={d["pe"]}, centro x={d["centro_x"]}')
        for a in dados['animacoes']:
            extra = ''
            conf = next((c for c in dados.get('conferencia_tiras', []) if c['animacao'] == a['nome']), None)
            if conf:
                marca = 'ok' if conf['quadros_identicos'] == conf['quadros_na_fonte'] else 'DIVERGE'
                extra = (f'  | tira {conf["tira"]}: {conf["quadros_identicos"]}/'
                         f'{conf["quadros_na_fonte"]} quadros idênticos [{marca}]')
            print(f'   {a["nome"]:10s} {a["quadros"]:2d} quadros, {a["duracao_ms"]:5d} ms, '
                  f'caixa {a["caixa"]}{extra}')

    if args.saida:
        os.makedirs(os.path.dirname(os.path.abspath(args.saida)), exist_ok=True)
        with open(args.saida, 'w', encoding='utf-8') as fh:
            json.dump(inventario, fh, ensure_ascii=False, indent=2)
        print(f'\ninventário gravado em {args.saida}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
