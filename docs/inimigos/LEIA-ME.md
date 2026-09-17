# Inimigos: soldado e orc (pack Tiny RPG)

Dois inimigos novos entraram no jogo, os dois vindos do
[Tiny RPG Character Asset Pack 01 V2.0](../tiny-rpg-pack/LEIA-ME.md) que você
subiu no GitHub: o **soldado** (atira flecha) e o **orc** (brutamontes corpo a
corpo).

> **Licença:** a arte do pack não é versionada (o repositório é público e a
> licença proíbe reenviar os arquivos). Este repositório guarda o **conversor**,
> o **de/para** e os **testes**; os PNG+JSON saem do conversor na máquina de quem
> clona. Sem eles o jogo funciona igual, com o desenho de fallback.

## Como os sheets são gerados

```bash
python3 tools/importar_pack.py --mapa tools/mapas/pack_tiny.json \\
    --saida-dir art/tiny-rpg-pack/jogo
cp art/tiny-rpg-pack/jogo/{soldier,orc,flecha}.{png,json} Sprite/Enemies/
```

Isso produz três pares no mesmo contrato dos sheets que já existiam (uma tira de
uma linha, `<nome> N.aseprite` em ordem, tags `<nome>_estado`, âncora nos pés):

| sheet     | célula | quadros | animações (quadros)                              |
| --------- | ------ | ------- | ------------------------------------------------ |
| `soldier` | 64×64  | 31      | idle 6 · movement 8 · attack 9 · take_damage 4 · death 4 |
| `orc`     | 64×64  | 28      | idle 6 · movement 8 · attack 6 · take_damage 4 · death 4 |
| `flecha`  | 32×32  | 1       | (projétil, aponta para a direita)                |

Detalhes da conversão (camada de sombra fora, 5 px de margem abaixo dos pés,
100% da tinta preservada) e o porquê da célula 64×64:
[`art/tiny-rpg-pack/LEIA-ME.md`](../../art/tiny-rpg-pack/LEIA-ME.md).

## O que mudou no jogo

`ENEMY_TYPES` (em `game.js`) ganhou dois tipos — os outros três continuam iguais:

| tipo      | sheet      | r  | vida | velocidade | escala | dano | como age                           |
| --------- | ---------- | -- | ---- | ---------- | ------ | ---- | ---------------------------------- |
| `goblin`  | skeleton1  | 11 | 1    | 0,70       | 1,60   | 18   | corpo a corpo                      |
| `runner`  | skeleton2  | 9  | 1    | 1,50       | 1,30   | 18   | corpo a corpo, rápido              |
| `elite`   | skeleton2  | 16 | 7    | 1,05       | 2,40   | 18   | corpo a corpo, com aura            |
| `soldier` | soldier    | 11 | 2    | 0,85       | 1,50   | 9    | **para a 200 px e atira flecha**   |
| `orc`     | orc        | 15 | 6    | 0,55       | 1,75   | 26   | **brutamontes: bate mais forte**   |

**Soldado.** Anda até chegar a 200 px do bruxo e para ali. A cada ~1,9 s (±15 %)
toca `attack` e, **0,7 s depois** (o quadro em que ele estica o braço), solta a
flecha — assim a flecha sai junto com o gesto, e não no primeiro quadro. Ele só
se aproxima de novo se o bruxo se afastar (até 340 px). Não dá dano de contato:
encostar nele não machuca.

**Flecha.** Sai da altura da mão (o desenho é ancorado nos pés), voa em linha
reta a 4,6 px por quadro e some ao acertar ou depois de 150 quadros. Acerta
quando chega a 17 px do centro do bruxo e tira 9 de vida — o escudo arcano
absorve a primeira. No desenho ela **gira pelo ângulo do voo** (o sprite aponta
para a direita, então basta girar); sem o sheet, sai um traço claro no lugar.

**Orc.** Lento e pesado. Encosta e bate 26 por pancada — 44 % mais que o contato
dos esqueletos (18). Aguenta 6 golpes de cajado.

**Mistura de inimigos.** O sorteio agora abre por tempo de partida (peso de cada
tipo no sorteio):

| tempo   | tipos que podem nascer            |
| ------- | --------------------------------- |
| 0 s     | goblin                            |
| 60 s    | + soldier (0,55)                  |
| 120 s   | + runner (0,70)                   |
| 180 s   | + orc (0,45)                      |
| 300 s   | + elite (0,20)                    |

**Sem os sheets.** Se `Sprite/Enemies/soldier.*`, `orc.*` ou `flecha.*` não
existirem (clone novo, sem rodar o conversor), o jogo não quebra: o tipo continua
nascendo, desenhado com o círculo de fallback (cinza-azulado para o soldado,
verde-oliva para o orc), e o `Assets.anyFailed` mostra o aviso no rodapé.

## Como isso foi conferido

```bash
node tools/verificar_assets.mjs    # contrato dos PNG+JSON (célula, tiras, tags)
node tools/smoke_inimigos.mjs      # 68 checagens: soldado, flecha, escudo, orc
node tools/smoke_personagem.mjs    # 34 checagens: o bruxo continua inteiro
python3 tools/limpar_sprites.py --report    # relatório dos sheets de Sprite/Enemies
```

O `smoke_inimigos.mjs` funciona nos dois estados: com os sheets do pack, confere
sprite e animação; sem eles (clone novo), **pula** as checagens de arte com aviso
e segue verificando o comportamento — são 41 checagens + 10 puladas.

Duas observações do relatório que **não** são problema: as tiras do pack ficam em
célula 64×64 (o verificador sabe disso e o `limpar_sprites.py` marca "3 frames
encostando na borda" no orc — é o tacape chegando à última linha, sem corte) e
aparecem 48 "cores órfãs" (tons de sombreamento da arte original: os sheets do
pack entram 1:1, como o autor desenhou, sem passar pela limpeza).

O `smoke_inimigos.mjs` carrega `assets.js` + `game.js` de verdade num DOM falso
(`tools/apoio/falso_navegador.mjs`) e dirige o jogo quadro a quadro:

1. os três sheets carregam no formato do jogo (célula e tags certas);
2. os cinco tipos existem e apontam para sheets que carregam;
3. o soldado anda até a distância de tiro, para e toca `attack`;
4. a flecha não sai no começo do ataque, sai no meio, é desenhada do sheet,
   voa na direção do bruxo e tira os 9 de vida;
5. com escudo, a flecha é absorvida (vida igual, escudo consumido);
6. soldado encostado não machuca;
7. o orc toca `attack` ao encostar e tira 26;
8. os dois morrem com animação, contam abate e saem da lista;
9. a mistura de tipos abre conforme o tempo;
10. sem os sheets, o jogo continua desenhando (fallback) sem quebrar.

Nada disso é verificação só de código: as checagens olham o mesmo `drawImage`
que o navegador receberia, e o dano é lido do `hp` do jogo.

## Próximos passos possíveis

1. `Attack02` do soldado (golpe de lâmina) está sem uso — pode virar um ataque
   corpo a corpo curto de quem está sem flecha, ou uma variante.
2. Flecha com sombra de contato na parede/árvore, ou atravessando o cenário.
3. Sorteio por onda em vez de por tempo (hoje é tempo de partida).
