# Personagem na Unity — o que importar e como configurar

O protagonista é o **bruxo** (figura encapuzada com cajado, olhos vermelhos e
amuleto). A arte está em `Sprite/Characters/`:

| Arquivo | Para que serve |
|---|---|
| `bruxo.aseprite` | fonte, 49 frames, 5 tags — **use este se tiver o pacote Aseprite Importer** |
| `bruxo.png` + `bruxo.json` | exportação do Aseprite: tira de 1568x32, células de 32x32 |

Os três arquivos foram gerados/validados juntos: o `.aseprite` e o PNG+JSON têm
exatamente os mesmos pixels (`python3 tools/verificar_aseprite.py --aseprite
Sprite/Characters/bruxo.aseprite --sheets-dir Sprite/Characters`).

## Opção A — Aseprite Importer (recomendada)

1. `Window > Package Manager > Unity Registry > 2D Aseprite Importer`, instalar.
2. Copie `Sprite/Characters/bruxo.aseprite` para `Assets/Sprites/` do projeto Unity.
3. Selecione o arquivo importado e no Inspector:
   * **Pixels Per Unit: 32** (a célula tem 32x32, então 1 célula = 1 unidade);
   * **Pivot: Bottom Center** (a arte está ancorada nos pés);
   * **Filter Mode: Point (no filter)** — pixel art;
   * **Compression: None**;
   * **Generate Animation Clips: ligado** e **Animation Clip Name: por tag**.
4. O importador cria um clipe por tag:
   `bruxo_idle` (6 frames), `bruxo_movement` (8), `bruxo_attack` (16),
   `bruxo_take_damage` (5), `bruxo_death` (14) — as durações de cada frame vêm
   do arquivo (100 ms; 300 ms no último frame da morte).

## Opção B — PNG + Sprite Editor (sem pacote extra)

1. Copie `bruxo.png` para `Assets/Sprites/`.
2. No Inspector: **Sprite Mode: Multiple**, **Pixels Per Unit: 32**,
   **Filter Mode: Point**, **Compression: None**.
3. `Sprite Editor > Slice > Grid By Cell Size: 32 x 32`, **Pivot: Bottom Center**,
   `Slice`. Ficam 49 sprites nomeados `bruxo_0` … `bruxo_48`.
4. Crie os clipes montando os frames na ordem das tags (a faixa é a mesma do JSON):

   | Clipe | Frames (índice no PNG) | Duração |
   |---|---|---|
   | `idle` | 0–5 | 0,6 s, loop |
   | `movement` | 6–13 | 0,8 s, loop |
   | `attack` | 14–29 | 1,6 s, uma vez |
   | `take_damage` | 30–34 | 0,5 s, uma vez |
   | `death` | 35–48 | 1,7 s, uma vez (último frame segura 0,3 s) |

   O `bruxo.json` tem os mesmos números em `meta.frameTags`, caso queira gerar os
   clipes por script em vez de na mão.

## Convenções que a arte já segue

* **Célula 32x32**, tira horizontal, um PNG por personagem.
* **Ancoragem nos pés**: o desenho encosta no máximo até 1 px da borda inferior
  da célula; o resto abaixo é folga. Use **Pivot: Bottom Center** e desenhe o
  sprite com a base na posição do personagem no chão.
* **O bruxo olha para a direita**; para a esquerda, espelhe em X
  (`localScale.x = -1` ou `SpriteRenderer.flipX`).
* **1 px de margem** em todas as bordas — seguro para ativar **padding** no atlas
  (evita "sangramento" de pixel vizinho).
* Cores exatas da paleta (8 no total, 21 tons no bruxo): sem anti-alias, sem
  pixels semi-transparentes.

## Estados do jogo web → clipes da Unity

O `game.js` usa exatamente as mesmas tags, então o comportamento é comparável:

| Estado no jogo | Tag | Quando dispara |
|---|---|---|
| parado | `idle` | sem tecla de movimento |
| andando | `movement` | WASD/setas (vira para o lado do movimento) |
| atacando | `attack` | o cajado atira sozinho a cada 0,65 s; a animação toca 2,4x mais rápido para caber no intervalo |
| levando dano | `take_damage` | toca até o fim, depois volta para idle/movement |
| morrendo | `death` | ao zerar o HP; o fim de jogo só aparece depois da animação |

Se quiser o mesmo ritmo na Unity, o ataque do bruxo no jogo está em
`PLAYER.animSpeed = { attack: 2.4 }` (`game.js`).

## Especificação para uma nova arte de personagem

Se um dia você desenhar um bruxo novo, mantendo isto ele entra sem mudar nada:

1. Aseprite com **canvas 32x32** por frame, exportando como tira horizontal.
2. Tags com os nomes `idle`, `movement`, `attack`, `take_damage`, `death`
   (o prefixo do arquivo, ex. `bruxo_`, é aceito e recomendado).
3. Exportar PNG + JSON (o mesmo export que gerou `skeleton1/2`).
4. Rodar as ferramentas deste repositório:

```bash
python3 tools/limpar_sprites.py --dir Sprite/Characters --report   # diagnóstico
python3 tools/limpar_sprites.py --dir Sprite/Characters --fix      # limpeza
node tools/verificar_assets.mjs                                    # contrato
node tools/smoke_personagem.mjs                                    # o bruxo anima no jogo
```

A limpeza garante margem de 1 px, remove pixel solto, normaliza cor fora da
paleta e zera pixels invisíveis com cor — os três problemas que apareceram nos
sheets dos inimigos.
