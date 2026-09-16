# Sputnik — Arcana Grove

Roguelike de arena em Canvas: você é um mago que sobrevive a ondas de criaturas
enquanto sobe de nível e escolhe melhorias.

## Rodar

```bash
python3 -m http.server 8080    # abra http://localhost:8080
```

WASD/setas movem; o cajado ataca sozinho.

## Estrutura

```
index.html, style.css, game.js   o jogo (Canvas 2D, sem build)
assets.js                        carrega os sprites do Aseprite (PNG + JSON)
Sprite/Characters/               o bruxo (protagonista): .aseprite + PNG + JSON
Sprite/Enemies/                  inimigos: .aseprite de origem + PNG + JSON
Sprite/Background/Floor.png      piso (desenhado em modo "cover")
tools/                           limpeza, verificação e testes dos assets
docs/limpeza/                    relatório da limpeza dos sprites
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
```

Requer `pillow` (`pip install pillow`) para as ferramentas em Python.
