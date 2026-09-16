# Limpeza e correção dos spritesheets

Relatório da limpeza feita em `Sprite/Enemies/*.png` antes de integrar o sprite do
personagem à Unity. Os **JSONs do Aseprite não precisaram mudar** — o layout
(mesma ordem de frames, mesma célula 32x32, mesmos retângulos) foi preservado, então
nem `assets.js` nem a Unity precisam de ajuste de importação.

## Como rodar

```bash
# diagnóstico (não altera nada)
python3 tools/limpar_sprites.py --dir Sprite/Enemies --report

# aplica as correções e grava a auditoria
python3 tools/limpar_sprites.py --dir Sprite/Enemies --fix --edits tools/relatorio-limpeza.json

# confere o contrato PNG + JSON que o jogo espera
node tools/verificar_assets.mjs
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

* `tools/limpar_sprites.py` — ferramenta de diagnóstico e correção (idempotente:
  rodar de novo não muda mais nada).
* `tools/relatorio-limpeza.json` — auditoria: cada pixel removido, cada cor
  mapeada e o deslocamento aplicado por animação. Permite reverter ou conferir.
* `tools/verificar_assets.mjs` — valida manifesto, IHDR dos PNGs, retângulos dos
  frames, tags e cobertura das animações.
* `docs/limpeza/antes-depois_*.png` — comparações visuais das animações corrigidas.
* `docs/limpeza/final_*.png` — contact sheet do resultado final, por animação.

## O que corrigir no Aseprite (arquivo-fonte)

O `Sprite/Enemies/enemies.aseprite` (e as duas cópias `enemies - Copia*.aseprite`,
todas idênticas — MD5 `513eaa05…`) tem o mesmo conteúdo dos sheets. Se quiser que a
correção valha também para o arquivo-fonte:

1. Apagar os px soltos listados em `tools/relatorio-limpeza.json`
   (`solto_removido`).
2. Renomear/limpar a paleta para as cores canônicas (as 9 hex listadas acima).
3. Mover `skeleton1_attack`/`skeleton1_death` 1px à esquerda e
   `skeleton2_attack` -1px / `skeleton2_death` / `skeleton2_death2` +1px.
4. Reexportar PNG+JSON com o **mesmo nome de arquivo e mesma grade de 32x32**.
