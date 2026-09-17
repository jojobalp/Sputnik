# bruxo-casting — animações do personagem principal (frame a frame)

Extração limpa da prancha `art/referencia/bruxo-casting.jpg` (1376×768), que traz
o bruxo em 6 direções × 7 quadros de conjuração. Nada aqui está ligado ao jogo
ainda: é material de arte pronto para revisão e para a futura integração.

## O que tem aqui

```
art/bruxo-casting/
├── frames/<animacao>/<fase>.png   42 PNGs individuais, fundo transparente
├── sul.png  norte.png  norte_repetida.png  leste.png  oeste.png  norte_2.png
│                                  tira pronta de cada animação (7 quadros)
├── *.gif                          prévia animada de cada direção (3× de zoom)
└── manifest.json                  nomes, célula e caminho de cada frame
```

Cada quadro saiu num PNG separado, alinhado pela base (pés) dentro da animação,
com a grade, o título, a numeração e os rótulos da prancha removidos.

| animação          | prancha | fases (7 colunas)                                                            | célula |
| ----------------- | ------- | ---------------------------------------------------------------------------- | ------ |
| `sul`             | S       | idle, charge_1, charge_2, cast, release, travel, recovery                    | 145×76 |
| `norte`           | N       | idem                                                                          | 147×79 |
| `norte_repetida`  | N       | idem — a IA gerou uma segunda linha "N"; confira se não deveria ser outra     | 155×79 |
| `leste`           | E       | idem                                                                          | 157×81 |
| `oeste`           | W       | idem                                                                          | 165×89 |
| `norte_2`         | N       | idle, charge_1, charge_2, cast, release, **post_cast**, **return_ready**      | 165×90 |

A magia é um quadro à parte: a bola de relâmpago viaja para longe do corpo nos
quadros `travel`, então o recorte de cada quadro é a união de tudo que pertence a
ele (corpo + cajado + bola + partículas) — a fronteira da grade não corta mais a
magia.

## Como foi feito

```bash
python3 tools/extrair_spritesheet.py \
  --entrada art/referencia/bruxo-casting.jpg \
  --grade componentes \
  --colunas-x "18,175,346,520,691,858,1049,1238" \
  --linhas-y  "47,163,273,390,511,635,753" \
  --saida-dir art/bruxo-casting \
  --mapa tools/mapas/wizard_casting.json --colunas 7 --gif
```

- a grade desta prancha não é regular e as linhas internas das células não são
  detectáveis com segurança pelo modo automático — as fronteiras vão escritas na
  mão (`--colunas-x` / `--linhas-y`, medidas em `--diagnostico`);
- `--grade componentes` decide a que quadro cada desenho pertence pelo **centro da
  massa**, não pela posição na grade: é isso que mantém a bola de magia inteira
  mesmo quando ela atravessa a linha divisória;
- a faixa do rótulo não tem altura fixa: a ferramenta procura o **vazio** entre o
  desenho e o texto impresso, então o pé do personagem não é cortado;
- `--colunas 7` descarta a última coluna da prancha (`Original S/N/E/W`), que é
  referência e não animação.

Detalhes do método e o histórico das correções: `docs/limpeza/LIMPEZA-PRANCHAS.md`.

## Escala

Os quadros têm ≈145–165 px de largura, na escala da prancha original. O jogo hoje
desenha o bruxo a 32×32 (`Sprite/Characters/bruxo.png`). Nada foi reescalado —
quando a integração for pedida, é só definir o fator de redução (≈4,5× para
chegar perto do tamanho atual) ou trocar a escala da câmera.

## Revisão

`docs/personagem/bruxo-casting-prancha.png` mostra as 42 poses lado a lado, com
fundo xadrez, para conferência rápida.
