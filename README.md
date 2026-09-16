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
Sprite/Enemies/                  sheets exportados + os .aseprite de origem
Sprite/Background/Floor.png      piso (desenhado em modo "cover")
tools/                           limpeza e verificação dos assets
docs/limpeza/                    relatório da limpeza dos sprites
```

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
```

Requer `pillow` (`pip install pillow`) para as ferramentas em Python.
