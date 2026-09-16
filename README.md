# Sputnik — Arcana Grove

Roguelike de arena em Canvas: você é um mago que sobrevive a ondas de criaturas
enquanto sobe de nível e escolhe melhorias.

## Rodar

```bash
python3 -m http.server 8080    # abra http://localhost:8080
```

WASD/setas movem; o cajado ataca sozinho.

Para ver a arte das pranchas (as 6 direções do bruxo rodando, os 42 quadros
soltos e os elementos da cena) numa página só:

```bash
python3 tools/servir_previa.py 8081   # abre direto em /previa-animacoes.html
```

A página é `previa-animacoes.html` (também funciona em `http://localhost:8080/previa-animacoes.html`).

## Estrutura

```
index.html, style.css, game.js   o jogo (Canvas 2D, sem build)
assets.js                        carrega os sprites do Aseprite (PNG + JSON)
Sprite/Characters/               o bruxo (protagonista): .aseprite + PNG + JSON
Sprite/Enemies/                  inimigos: .aseprite de origem + PNG + JSON
Sprite/Background/Floor.png      piso (desenhado em modo "cover")
art/referencia/                  pranchas de referência que você enviou
art/bruxo-casting/               animações do bruxo, quadro a quadro (6 direções)
art/terrenos-mobs-itens/         cena separada em itens, mobs, efeitos e grupos
tools/                           limpeza, extração, verificação e testes dos assets
docs/limpeza/                    relatório da limpeza e como as pranchas são extraídas
docs/cenario/                    pranchas de contato da cena (revisão rápida)
docs/unity/                      como importar o personagem na Unity
```

## Personagem

O protagonista é o bruxo (`Sprite/Characters/`): 49 frames em células de 32x32
com as tags `idle`, `movement`, `attack`, `take_damage` e `death`. Ele usa a mesma
convenção dos inimigos — âncora nos pés e espelhamento horizontal — e cai no
desenho vetorial antigo (círculo + cajado) se o sprite não carregar.

Instruções de importação na Unity (Aseprite Importer ou Sprite Editor), PPU,
pivot e mapeamento das animações: [`docs/unity/LEIA-ME.md`](docs/unity/LEIA-ME.md).

## Assets

Os sheets são exportados do Aseprite em células de **32x32**, uma tira horizontal
por personagem, com as animações identificadas por tags
(`idle`, `movement`, `attack`, `take_damage`, `death`). Cada sheet tem um JSON com
os retângulos dos frames e as durações.

A limpeza e as correções já aplicadas (pixels soltos, cores fora da paleta,
margem até a borda da célula, nome de tag truncado na fonte) estão descritas em
[`docs/limpeza/LEIA-ME.md`](docs/limpeza/LEIA-ME.md).

```bash
# conferir se PNG+JSON continuam consistentes com o jogo
python3 tools/limpar_sprites.py --dir Sprite/Enemies --report
node tools/verificar_assets.mjs
python3 tools/verificar_aseprite.py --aseprite Sprite/Enemies/enemies.aseprite
python3 tools/verificar_aseprite.py --aseprite Sprite/Characters/bruxo.aseprite --sheets-dir Sprite/Characters

# o bruxo carrega, anima, ataca, reage ao dano e morre (sem navegador)
node tools/smoke_personagem.mjs

# a página de prévia monta os cartões, roda os quadros e responde aos controles
node tools/smoke_previa.mjs
```

### Pranchas de referência → arte limpa

As referências que chegam como prancha (com grade, título e rótulos) viram arte
limpa em `art/` pelas duas ferramentas de extração:

```bash
# prancha com grade e animação (6 direções x 7 fases do bruxo)
python3 tools/extrair_spritesheet.py --entrada art/referencia/bruxo-casting.jpg \
    --grade componentes --colunas-x "18,175,346,520,691,858,1049,1238" \
    --linhas-y "47,163,273,390,511,635,753" \
    --saida-dir art/bruxo-casting --mapa tools/mapas/wizard_casting.json --colunas 7 --gif

# ilustração de cena, sem grade (itens, mobs, efeitos)
python3 tools/extrair_cena.py --entrada art/referencia/terrenos-mobs-itens.png \
    --saida-dir art/terrenos-mobs-itens --zonas "0:400=itens" \
    --zonas "400:1050=centro" --zonas "1050:=mobs" --min-area-zona "mobs=420"
```

Cada pasta extraída tem o seu `LEIA-ME.md`; o método e as armadilhas estão em
[`docs/limpeza/LIMPEZA-PRANCHAS.md`](docs/limpeza/LIMPEZA-PRANCHAS.md).

Requer `pillow`, `numpy` e `scipy` (`pip install pillow numpy scipy`) para as
ferramentas em Python.
