#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""servir_previa.py — servidor local que abre direto na prévia das animações.

igual ao `python3 -m http.server`, mas a raiz ("/") entrega
`previa-animacoes.html` em vez do jogo — assim a prévia das animações abre
sozinha no navegador. O jogo continua em /index.html.

Uso:
    python3 tools/servir_previa.py [porta] [--dir DIR]
"""

from __future__ import annotations

import argparse
import functools
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PAGINA = '/previa-animacoes.html'


class Handler(SimpleHTTPRequestHandler):
    """Serve a pasta do projeto, mandando a raiz para a página da prévia."""

    def do_GET(self):                                  # noqa: N802
        if self.path in ('/', ''):
            self.path = PAGINA
        return super().do_GET()

    def do_HEAD(self):                                 # noqa: N802
        if self.path in ('/', ''):
            self.path = PAGINA
        return super().do_HEAD()

    def end_headers(self):
        # durante a montagem da arte, nada fica em cache no navegador
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


def main():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description='Servidor da prévia das animações.')
    ap.add_argument('porta', nargs='?', type=int, default=8081)
    ap.add_argument('--dir', default=raiz, help='pasta servida (padrão: a do projeto)')
    args = ap.parse_args()

    handler = functools.partial(Handler, directory=args.dir)
    with ThreadingHTTPServer(('0.0.0.0', args.porta), handler) as httpd:
        print(f'prévia em http://0.0.0.0:{args.porta}/  →  {PAGINA}')
        print(f'servindo {args.dir}  (jogo em /index.html)')
        httpd.serve_forever()


if __name__ == '__main__':
    main()
