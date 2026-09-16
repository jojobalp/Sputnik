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
art/tiny-rpg-pack/               pack de terceiros (Soldier & Orc) — arte fora do Git, ver licença
art/bruxo-casting/               animações do bruxo, quadro a quadro (6 direções)
art/terrenos-mobs-itens/         cena separada em itens, mobs, efeitos e grupos
tools/                           limpeza, extração, verificação e testes dos assets
docs/limpeza/                    relatório da limpeza e como as pranchas são extraídas
docs/cenario/                    pranchas de contato da cena (revisão rápida)
docs/inimigos/                   soldado e orc: de onde vêm e como agem no jogo
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

# soldado e orc nascem, atiram, batem, morrem e caem no fallback sem os sheets
node tools/smoke_inimigos.mjs

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

### Pack de terceiros (Tiny RPG Character Asset Pack 01 V2.0)

O pack "Free Soldier & Orc" (autor **Zerie**, itch.io) está organizado em
`art/tiny-rpg-pack/` — Soldier (43 quadros, 7 animações) e Orc (34 quadros, 6
animações), ambos em células de 100×100. **A arte dele não é versionada**: a
licença permite usar e modificar em projetos comerciais, mas proíbe redistribuir
ou reenviar os arquivos, e este repositório é público. Ficam no Git apenas o
`LEIA-ME.md` e o inventário `manifest.json`; o resto é ignorado pelo `.gitignore`.

```bash
# inventário do pack (lê os .aseprite e confere com as tiras exportadas)
python3 tools/inventariar_pack.py \
    --aseprite art/tiny-rpg-pack/aseprite/*.aseprite \
    --conferir-pasta art/tiny-rpg-pack/soldier \
    --conferir-pasta art/tiny-rpg-pack/orc-com-sombra \
    --saida art/tiny-rpg-pack/manifest.json
```

**Convertidos para o jogo** (soldado atirador e orc brutamontes) por
`tools/importar_pack.py`, que lê os `.aseprite` originais, tira a camada de
sombra (o jogo desenha a dele) e corta tudo em células de 64×64 com a âncora nos
pés:

```bash
python3 tools/importar_pack.py --mapa tools/mapas/pack_tiny.json \
    --saida-dir art/tiny-rpg-pack/jogo
cp art/tiny-rpg-pack/jogo/{soldier,orc,flecha}.{png,json} Sprite/Enemies/
```

Os sheets convertidos também ficam fora do Git (`art/tiny-rpg-pack/jogo/` inteiro
e `Sprite/Enemies/{soldier,orc,flecha}.*`): quem clona roda o comando acima — e,
sem eles, o jogo continua rodando com o desenho de fallback.

Detalhes, licença e escala comparada com os sprites do jogo:
[`art/tiny-rpg-pack/LEIA-ME.md`](art/tiny-rpg-pack/LEIA-ME.md). Os dois inimigos,
os números e o que os testes cobrem:
[`docs/inimigos/LEIA-ME.md`](docs/inimigos/LEIA-ME.md).

Requer `pillow`, `numpy` e `scipy` (`pip install pillow numpy scipy`) para as
ferramentas em Python.
