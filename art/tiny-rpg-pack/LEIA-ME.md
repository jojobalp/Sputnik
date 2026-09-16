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

## Próximos passos possíveis (nada feito ainda)

1. **Preparar no formato do jogo**: recortar cada quadro para a célula do projeto
   (32×32 ou 48×48), com âncora nos pés e as tags `idle`/`movement`/`attack`/
   `take_damage`/`death` — o mesmo PNG+JSON que `Sprite/Enemies/` usa hoje.
2. **Entrar no jogo como inimigos**: soldado como inimigo à distância (flecha) e
   orc como brutamontes corpo a corpo.
3. **Pack completo** ($2.50, 22 personagens): traz esqueletos, necromante e mago
   que combinam com o tema do jogo — mas aí a licença continua valendo, então a
   arte segue fora do Git.
