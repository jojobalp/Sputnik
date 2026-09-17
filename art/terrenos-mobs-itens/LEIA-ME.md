# terrenos-mobs-itens — elementos soltos da cena

Separação da ilustração `art/referencia/terrenos-mobs-itens.png` (1697×927) em
elementos soltos, com fundo branco virou transparência. A imagem é uma **cena de
batalha**, não um atlas: não há grade nem animação para "retirar frame a frame",
então o que se extrai é cada desenho.

```
art/terrenos-mobs-itens/
├── itens/    21  moedas, gemas, poções, frascos, ossos, armas quebradas
├── mobs/     28  zumbis (verdes, vermelhos, roxos), esqueletos e variantes grandes
├── centro/   23  o que está na faixa do meio: itens e respingos de sangue
├── cena/      1  bruxo-com-relampago.png — o quadro central da cena
├── grupos/    1  grupos_001.png — a horda: mobs sobrepostos numa massa só
├── manifest.json        onde cada recorte estava na imagem (coordenadas) e o tamanho
└── mapa-numerado.png    a prancha original com um retângulo em cada recorte
```

As três primeiras pastas são **organização por posição** na prancha (x < 400,
400–1050, x > 1050), não classificação por tipo: um zumbi que está no canto
esquerdo cai em `itens/`. Se preferir por tipo, é só mover os arquivos — o
`manifest.json` guarda a posição de cada um para conferência.

## Como foi feito

```bash
python3 tools/extrair_cena.py \
  --entrada art/referencia/terrenos-mobs-itens.png \
  --saida-dir art/terrenos-mobs-itens \
  --zonas "0:400=itens" --zonas "400:1050=centro" --zonas "1050:=mobs" \
  --min-area-zona "mobs=420" --min-area-zona "centro=420"
```

1. o fundo branco vira transparência, com alfa suave na borda anti-aliasada;
2. o que sobra é agrupado em massas (componentes conexos), depois de uma
   abertura que quebra as pontes finas entre um desenho e outro;
3. cada massa grande o bastante vira um PNG com folga;
4. massa maior que 20000 px² é aglomerado (a horda do centro) e vai para
   `grupos/` — nenhum corte automático separa mobs que estão desenhados um por
   cima do outro;
5. o `mapa-numerado.png` mostra todos os recortes sobre a imagem original.

O bruxo com o relâmpago (`cena/bruxo-com-relampago.png`) foi o maior recorte da
faixa central e ficou nomeado à parte — é o quadro que interessa como referência
de efeito.

## Limites (para não gerar expectativa errada)

* **mobs sobrepostos ficam juntos**: 9 recortes de `mobs/` têm 2 ou 3 zumbis que
  se encostam (o manifesto/contato mostra o tamanho de cada um). A horda inteira
  é um recorte só, em `grupos/`.
* **sangue e fragmentos menores que o mínimo** (420 px² na faixa central/direita)
  não viram arquivo: são respingos e pedaços de membro de mobs que estão dentro
  do aglomerado. Se algum deles interessar, reduza `--min-area` e rode de novo.
* **nada foi reescalado** e nada foi ligado ao jogo: é material de arte para
  revisão.

## Revisão rápida

`docs/cenario/` traz as pranchas de contato: `terrenos-itens.png`,
`terrenos-mobs.png`, `terrenos-centro.png`, `terrenos-cena-bruxo.png` e
`terrenos-horda.png`.
