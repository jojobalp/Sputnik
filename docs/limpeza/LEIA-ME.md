# Limpeza e correção dos spritesheets

Relatório da limpeza feita em `Sprite/Enemies/*` antes de integrar o sprite do
personagem à Unity. Os **JSONs do Aseprite não precisaram mudar** — o layout
(mesma ordem de frames, mesma célula 32x32, mesmos retângulos) foi preservado, então
nem `assets.js` nem a Unity precisam de ajuste de importação.

A limpeza foi aplicada **nos dois lugares**: nos PNGs exportados (o que o jogo lê)
e dentro dos `.aseprite` de origem (o que a Unity importa direto pelo
[Aseprite Importer](https://docs.unity3d.com/Packages/com.unity.2d.aseprite@latest/manual/index.html)).
Sem isso, quem importasse a fonte receberia a arte defeituosa de volta.

## Como rodar

```bash
# diagnóstico (não altera nada)
python3 tools/limpar_sprites.py --dir Sprite/Enemies --report

# aplica as correções nos PNGs e grava a auditoria
python3 tools/limpar_sprites.py --dir Sprite/Enemies --fix --edits tools/relatorio-limpeza.json

# aplica as mesmas correções dentro do .aseprite de origem
python3 tools/corrigir_aseprite.py --aseprite "Sprite/Enemies/enemies.aseprite" --antes-dir <pngs antigos>

# conferências
node tools/verificar_assets.mjs                       # contrato PNG + JSON do jogo
python3 tools/verificar_aseprite.py --aseprite "Sprite/Enemies/enemies.aseprite"
```

Dependência: `pip install pillow`.

## O que estava errado

| Sheet | Frames | Defeito encontrado | Ação |
|---|---|---|---|
| skeleton1 | 47 | 3 px soltos de "rastro" da arma (frames 24) | removidos |
| skeleton1 | 47 | `attack` e `death` cortavam na borda x=31 (frame 22 era cortado de verdade) | animação deslocada 1px p/ esquerda |
| skeleton2 | 66 | 3 px soltos de rastro da arma (frames 23 e 29) | removidos |
| skeleton2 | 66 | `attack` cortava em x=31; `death` e `death2` cortavam/encostavam em x=0 | `attack` -1px, `death`/`death2` +1px |
| vampire | 49 | 9 cores "órfãs" (ruído de anti-alias: `#7f755d`, `#c26a20`, `#f0df54`…) | aproximadas da cor canônica |
| vampire | 49 | 198 px **invisíveis** mas com cor `#5e4e3a` (halo que vaza ao filtrar em atlas) | zerados para transparente puro |
| enemies.aseprite | 162 cels | a fonte trazia a tag `skeleton2_movemen` (nome cortado) enquanto o JSON exportado dizia `skeleton2_movement` — na Unity o clipe sairia com o nome errado | renomeada para `skeleton2_movement` |

Depois da limpeza, a arte do bruxo (que estava dentro de `enemies.aseprite`, na
faixa de frames 47-95) foi separada em `Sprite/Characters/`: `bruxo.aseprite`
(49 frames, 5 tags renomeadas para `bruxo_*`, numeração reiniciada em 0),
`bruxo.png` e `bruxo.json`. Assim a Unity importa **só o protagonista**, sem os
dois esqueletos junto — antes o arquivo trazia os três personagens e 16 tags.

O `Floor.png` também foi auditado: é RGB puro (sem canal alfa), não é tileável
(divergência média de ~15 níveis entre bordas opostas) e tem ~111 mil cores com
36 mil usadas em um único pixel. O jogo já o desenha em modo *cover*, então nada
foi alterado — mas vale reexportar em uma resolução/paleta menor.

## Decisões para não destruir arte legítima

Algumas coisas que **parecem** defeito e foram mantidas de propósito:

* **Pixels soltos colados ao desenho** (`dist < 3px`): partículas de fumaça/poeira
  da morte e do ataque. Só é removido o que está a 3px ou mais do desenho principal.
* **Animações com sobreposição de frames** (ex.: `death` e `death2` do skeleton2 são
  idênticos nos primeiros 8 frames): é intencional para as duas mortes começarem igual.
* **`idle` com frames repetidos** (`#0 = #5`, `#2 = #3`): a animação tem só 3 poses.
* **Duração 300ms nos frames 50 e 65 do skeleton2**: pausa final da morte, de propósito.

## Resultado

Antes → depois, medido pela própria ferramenta:

```
skeleton1: soltos=3  órfãs=0  transparentes_coloridos=0  borda=2   -> 0 0 0 0
skeleton2: soltos=3  órfãs=0  transparentes_coloridos=0  borda=18  -> 0 0 0 0
vampire  : soltos=0  órfãs=9  transparentes_coloridos=198 borda=0   -> 0 0 0 0
```

* nenhum frame ficou vazio (mínimo 79 px, máximo 313 px);
* nenhum frame encosta na borda da célula → seguro para gerar atlas com padding;
* a contagem de evidência: **534 checagens** passam em `node tools/verificar_assets.mjs`.

Impacto real no sheet: 5,96% dos pixels do skeleton1 e 7,56% do skeleton2
(movidos 1px, ou cores de 1–3px normalizadas); no vampire só 0,47%.

## Arquivos

* `tools/limpar_sprites.py` — diagnóstico e correção dos PNGs (idempotente:
  rodar de novo não muda mais nada).
* `tools/corrigir_aseprite.py` — grava nos `.aseprite` os mesmos frames limpos,
  reescrevendo só os cels (tags, paleta, slices, layer e durações ficam intactos)
  e consertando nomes de tag truncados. Sempre relê e confere antes de gravar.
* `tools/verificar_assets.mjs` — valida manifesto, IHDR dos PNGs, retângulos dos
  frames, tags e cobertura das animações (534 checagens).
* `tools/verificar_aseprite.py` — parser independente que compara `.aseprite` com
  os PNG+JSON exportados: estrutura, cels, tags, durações e pixel a pixel
  (1021 checagens, 162 frames).
* `tools/relatorio-limpeza.json` — auditoria: cada pixel removido, cada cor
  mapeada e o deslocamento aplicado por animação. Permite reverter ou conferir.
* `docs/limpeza/antes-depois_*.png` — comparações visuais das animações corrigidas.
* `docs/limpeza/final_*.png` — contact sheet do resultado final, por animação.

## Como reverter

Tudo o que foi alterado está no Git, em um único commit:

```bash
git revert <commit>            # desfaz tudo
git checkout <commit>~1 -- Sprite/Enemies/enemies.aseprite   # só a fonte
```

Os `.aseprite` corrigidos foram validados abrindo e reconstruindo os 162 frames
por um parser independente; se quiser garantia extra, abra um deles no Aseprite e
salve — o arquivo é um `.aseprite` comum, com os cels regravados em zlib.

## Arquivos-fonte `.aseprite`

`enemies.aseprite` e as duas cópias `enemies - Copia*.aseprite` são **byte a byte
idênticas** (MD5 igual) e receberam a mesma correção. Eles já contêm agora os 162
frames limpos, os mesmos dos PNGs exportados — conferido frame a frame por
`tools/verificar_aseprite.py`.

Se você reexportar pelo Aseprite, mantenha o **mesmo nome de arquivo e a mesma
grade de 32x32** para não precisar mexer no `assets.js` nem no projeto Unity.
Depois de qualquer reexportação, rode as duas conferências acima — elas avisam se a
fonte voltou a divergir da exportação.

## Sobre a atualização de 1px por animação

`limpar_sprites.py` alinha a animação inteira (nunca um frame sozinho), usando o
menor deslocamento possível — no máximo 1px aqui. Isso preserva o "pulo" natural do
personagem e só corrige o que encostava na borda. Se preferir centralizar a arte na
célula, use `--alinhamento centro`.
