# Tiny RPG Character Asset Pack 01 V2.0 — Free Soldier & Orc

Pack de terceiros que você subiu no GitHub (`Tiny RPG Character Asset Pack 01 v2.0
-Free Soldier&Orc.zip`), organizado e conferido. **A arte deste pack não está no
Git** — o motivo está na seção da licença, mais abaixo.

- Origem: <https://zerie.itch.io/tiny-rpg-character-asset-pack> (autor: **Zerie**)
- Versão: **01 V2.0**, edição gratuita "Free Soldier & Orc" (a versão completa tem
  22 personagens: esqueletos, necromante, mago, slime, lobisomem, arqueiro…)
- Célula: **100×100 px**, o personagem fica mais ou menos no centro da célula

## ⚠️ Licença (importante para este repositório)

Do próprio texto da licença do pack:

> **✔️ Permitido**
> - Usar os assets em projetos de jogo pessoais e comerciais.
> - Editar ou modificar os assets para o seu projeto.
>
> **❌ Não permitido**
> - Redistribuir, revender ou reenviar estes assets, modificados ou não.
> - Usar os assets para treino de IA ou projetos NFT.
>
> Crédito é apreciado, mas não obrigatório.

Como `jojobalp/Sputnik` é um repositório **público**, subir a arte do pack aqui
seria "reenviar os assets" — o que a licença proíbe. Por isso:

- `.gitignore` mantém `art/tiny-rpg-pack/*` fora do Git (só o `LEIA-ME.md` e o
  `manifest.json` são versionados: documentação e números, não a arte);
- o zip original ficou em `art/referencia/tiny-rpg-pack-01-v2-free-soldier-orc.zip`,
  também ignorado pelo Git.

**Atenção:** o zip **está publicado** no `main` do repositório (commit
`a1acfec`). Vale resolver isso — as opções são tornar o repositório privado
(1 clique nas configurações do GitHub) ou apagar o arquivo de lá.

**Os arquivos continuam nesta pasta** para o trabalho do jogo — só não vão para o
GitHub. Se algum dia clonar o repositório em outra máquina, baixe o pack de novo
no link acima e reponha a mesma estrutura.

## O que tem aqui

```
art/tiny-rpg-pack/
├── aseprite/            Soldier.aseprite, Orc.aseprite    (fontes, com sombra)
├── soldier/             Soldier.png (grade 9×7) + 7 tiras de animação
├── orc/                 Orc.png (grade 8×6) + 6 tiras — versão SEM sombra
├── orc-com-sombra/      Orc.png + 6 tiras — versão COM sombra
├── flecha/              Arrow01(32x32).png, Arrow01(100x100).png
├── jogo/                sheets convertidos p/ o jogo (gerados; fora do Git)
├── manifest.json        inventário (versionado no Git)
└── previa-*.png         pranchas de conferência (fora do Git, como a arte)
```

Cada tira é uma animação, com os quadros lado a lado em células de 100×100.

## Inventário

Tudo abaixo saiu do `manifest.json`, que é gerado lendo os `.aseprite` de origem
(`tools/inventariar_pack.py`) — não é estimativa:

### Soldier — 43 quadros, 7 animações

| animação  | quadros | duração | corpo (px) | caixa na célula |
| --------- | ------- | ------- | ---------- | --------------- |
| Idle      | 6       | 600 ms  | 17×22      | x41-57 y38-59   |
| Walk      | 8       | 800 ms  | 17×22      | x41-57 y38-59   |
| Attack01  | 6       | 600 ms  | 34×27      | x36-69 y33-59   |
| Attack02  | 6       | 600 ms  | 29×29      | x41-69 y31-59   |
| Attack03  | 9       | 900 ms  | 36×22      | x41-76 y38-59   |
| Hurt      | 4       | 400 ms  | 18×21      | x40-57 y39-59   |
| Death     | 4       | 900 ms  | 27×21      | x41-67 y39-59   |

Corpo em repouso: **17×22 px**, pés na linha **y=59**, centro em **x≈49**.

### Orc — 34 quadros, 6 animações

| animação  | quadros | duração | corpo (px) | caixa na célula |
| --------- | ------- | ------- | ---------- | --------------- |
| Idle      | 6       | 600 ms  | 23×19      | x43-65 y41-59   |
| Walk      | 8       | 800 ms  | 23×19      | x43-65 y41-59   |
| Attack01  | 6       | 600 ms  | 37×29      | x36-72 y33-61   |
| Attack02  | 6       | 600 ms  | 38×33      | x36-73 y33-65   |
| Hurt      | 4       | 400 ms  | 23×18      | x42-64 y42-59   |
| Death     | 4       | 900 ms  | 30×21      | x36-65 y39-59   |

Corpo em repouso: **23×19 px**, pés em **y=59** (na animação de ataque, y=65).

O Orc não tem `Attack03`; é o único que vem em duas versões — `orc/` (sem sombra)
e `orc-com-sombra/` (com a sombra desenhada no chão).

### Flecha

`Arrow01(32x32).png` e `Arrow01(100x100).png` — projétil pronto para o ataque à
distância (o jogo já tem projétil, então dá para trocar o desenho dele).

## Como o pack foi conferido

`tools/inventariar_pack.py` lê os `.aseprite` e compara **quadro a quadro** com as
tiras exportadas do próprio pack:

```bash
python3 tools/inventariar_pack.py \
  --aseprite art/tiny-rpg-pack/aseprite/*.aseprite \
  --conferir-pasta art/tiny-rpg-pack/soldier \
  --conferir-pasta art/tiny-rpg-pack/orc-com-sombra \
  --saida art/tiny-rpg-pack/manifest.json
```

Resultado: **Soldier 43/43** e **Orc 34/34** quadros idênticos às tiras. Uma
exceção conhecida: o quadro 5 da tira `Orc_Attack02` difere da fonte em **6
pixels** (a fonte tem 6 pixels escuros que a tira não tem — provavelmente a tira
foi exportada antes de um ajuste do autor). **A fonte é a verdade.**

Para isso o leitor de `.aseprite` ganhou três recursos que este pack exigiu (e que
o verifica nos arquivos antigos do projeto também usa): mais de uma camada por
quadro, **célula vinculada** (quando a camada repete, o Aseprite guarda só uma
referência — é o caso da sombra) e opacidade de célula.

## Escala — como isso encaixa no jogo

| sprite                    | corpo em repouso |
| ------------------------- | ---------------- |
| bruxo do jogo (32×32)     | 12×17            |
| esqueletos do jogo (32×32)| 15×16 e 16×16    |
| **Soldier do pack**       | **17×22**        |
| **Orc do pack**           | **23×19**        |

Ou seja: o pack está na **mesma escala do jogo** (um pouco maior — o soldado tem
~30% mais altura que o esqueleto). Dá para usar sem reescalar, ou reduzir ~25%
para casar exatamente com os inimigos atuais.

## Convertido para o jogo

O pack foi recortado para o formato que o jogo usa (`Sprite/Enemies/*.png` +
`.json`, uma tira de uma linha por animação, âncora nos pés). Quem faz isso é
`tools/importar_pack.py`, que lê os `.aseprite` de origem — não as tiras — para
poder **tirar a camada de sombra** (o jogo desenha a sombra de contato dele) e
usar a duração real de cada quadro:

```bash
python3 tools/importar_pack.py --mapa tools/mapas/pack_tiny.json \
    --saida-dir art/tiny-rpg-pack/jogo
cp art/tiny-rpg-pack/jogo/{soldier,orc,flecha}.{png,json} Sprite/Enemies/
```

O que o de/para (`tools/mapas/pack_tiny.json`) diz:

| no jogo        | Soldier        | Orc            |
| -------------- | -------------- | -------------- |
| `idle`         | Idle (6)       | Idle (6)       |
| `movement`     | Walk (8)       | Walk (8)       |
| `attack`       | **Attack03** (9) | **Attack01** (6) |
| `take_damage`  | Hurt (4)       | Hurt (4)       |
| `death`        | Death (4)      | Death (4)      |

| outros números | Soldier | Orc |
| -------------- | ------- | --- |
| célula         | 64×64   | 64×64 |
| quadros na tira | 31     | 28  |
| pé na célula   | linha 58 | linha 58 |
| pés por linha  | 5 px de margem até a base | idem |

Por que não 32×32 como os esqueletos: o golpe do soldado chega a ocupar 45 px de
largura (quadro 8 do Attack03) e o do orc, 37–38 px. Em 32×32 sobraria cortar ou
reduzir ~0,84×, e o pixel art perderia a grade. A célula 64×64 mantém a arte em
1:1; o `scale` do jogo cuida do tamanho na tela.

O importador confere o próprio recorte: **100% da tinta preservada** nos dois
(soma do canal alfa antes/depois). Duas observações que ele reporta:

- nos 3 últimos quadros do golpe do orc o tacape **chega à última linha** da
  célula (folga zero, nada cortado) — é o pack desenhando abaixo da linha dos pés;
- a sombra do pack fica de fora de propósito (o jogo já desenha a elipse de
  contato, na mesma âncora).

### Onde os arquivos ficam

Os sheets convertidos **não entram no Git** (mesma licença da arte de origem):
`art/tiny-rpg-pack/jogo/` fica ignorado inteiro e, dentro de `Sprite/Enemies/`,
só `soldier.*`, `orc.*`, `flecha.*` (e o `gerado.json` do importador) estão no
`.gitignore`. Num clone novo, o jogo roda sem eles — os dois tipos aparecem
desenhados com o círculo de fallback — e `node tools/verificar_assets.mjs` avisa
que faltam (não é erro).

A prancha `previa-no-jogo.png` (bruxo + soldado + orc na escala e na âncora do
jogo, sobre o piso do projeto) também é gerada e ignorada:

```bash
python3 tools/prancha_inimigos.py --saida art/tiny-rpg-pack/previa-no-jogo.png
```

## O que já entrou no jogo

- **Soldado** — atirador: para a 200 px do bruxo, toca `attack` e solta a flecha
  0,7 s depois (o quadro em que ele estica o braço), a cada ~1,9 s. Flecha: sprite
  do pack (célula 32×32) girando pelo ângulo do voo, 9 de dano. Nunca dá dano de
  contato.
- **Orc** — brutamontes: lento (0,55), 6 de vida e 26 de dano por pancada.

Números e comportamento: [`docs/inimigos/LEIA-ME.md`](../../docs/inimigos/LEIA-ME.md).

## Próximos passos possíveis

1. **Attack02 do soldado** (o golpe de lâmina branca) está sem uso — pode virar
   uma segunda variante de ataque à distância ou um golpe corpo a corpo curto.
2. **Pack completo** ($2.50, 22 personagens): traz esqueletos, necromante e mago
   que combinam com o tema do jogo — mas aí a licença continua valendo, então a
   arte segue fora do Git.
