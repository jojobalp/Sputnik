# Limpeza de pranchas de referência (IA) → frames soltos

Pranchas como a do "wizard casting / lightning ball" não são spritesheets: são
folhas de planejamento com grade desenhada, título, numeração de célula, rótulos
(IDLE S, CHARGE, CAST, RELEASE…) e uma coluna de referência à direita. Este
documento explica como transformá-las em frames limpos com fundo transparente.

## Ferramenta

```bash
# 1) ver o que ela encontrou (grade, linhas, colunas) sem gravar nada
python3 tools/extrair_spritesheet.py --entrada prancha.jpg --diagnostico

# 2) extrair (o mapa diz o nome de cada quadro, na ordem das colunas)
python3 tools/extrair_spritesheet.py --entrada prancha.jpg \
    --mapa tools/mapas/wizard_casting.json \
    --saida-dir Sprite/Characters/casting \
    --colunas 7 --linhas 6 --gif
```

Requer `pillow`, `numpy` e `scipy` (`pip install pillow numpy scipy`).

## O que ela faz

1. **Encontra a grade** medindo, em cada coluna/linha da imagem, quanto de borda
   existe ao longo de toda a figura. Linha de grade atravessa a prancha inteira;
   contorno de personagem só aparece num trecho — por isso a detecção não
   confunde o cajado ou os ombros com uma divisória.
2. **Descarta o que não é quadro**: título, legendas, a coluna de referência
   (basta limitar `--colunas`) e faixas sem desenho (o critério é a extensão do
   conteúdo: texto é baixo, personagem ocupa boa parte da faixa).
3. **Tira o fundo** por preenchimento a partir da borda da célula, com barreira
   de borda: a bola de magia branca sobre fundo claro tem contorno definido, então
   o preenchimento não atravessa e o miolo dela é preservado. O alfa é suave nas
   bordas anti-aliasadas.
4. **Limpa resíduo**: respingos, poeira de JPEG e a numeração pequena impressa no
   topo da célula. Efeitos destacados do corpo (a magia na ponta do cajado) são
   preservados de propósito.
5. **Alinha pela base** (pés) dentro de cada animação, sem matar a variação do
   corpo, e grava:

```
saida/
  frames/sul/idle.png, charge_1.png, ...
  sul.png              # sheet remontado, sem grade nem rótulos
  sul.gif              # prévia animada
  manifest.json        # nomes, ordem, célula, cobertura
```

## Conferência

Cada linha sai com a **cobertura mínima**: a fração do desenho que sobreviveu à
extração, comparada com o conteúdo da célula. Em arte limpa o valor fica acima de
90%; abaixo de 85% a ferramenta avisa no terminal, o que indica que algum pedaço
foi removido por engano (geralmente ajustando `--tolerancia`).

## Modos de grade

| modo                    | quando usar                                                                 |
| ----------------------- | --------------------------------------------------------------------------- |
| `auto` (padrão)         | prancha de grade regular, sem linhas desenhadas dentro da célula            |
| `manual`                | grade regular, mas a detecção automática erra o passo                       |
| `explicita`             | fronteiras medidas na mão (`--colunas-x` / `--linhas-y`), grade irregular   |
| `componentes`           | o desenho **atravessa** a fronteira (magia, partículas) — ver abaixo        |

```bash
# fronteiras medidas na mão (o que a prancha do bruxo exigiu)
python3 tools/extrair_spritesheet.py --entrada prancha.jpg --grade explicita \
    --colunas-x "18,175,346,520,691,858,1049,1238" \
    --linhas-y  "47,163,273,390,511,635,753" --colunas 7

# mesmo recorte, mas deixando cada quadro levar tudo que é dele
python3 tools/extrair_spritesheet.py --entrada prancha.jpg --grade componentes \
    --colunas-x "..." --linhas-y "..." --colunas 7 --gif
```

### `--grade componentes`: por que existe

Numa prancha regular a célula decide o recorte — e a bola de magia, que viaja
para longe do corpo, acaba cortada na divisória (e um pedaço dela aparece no
quadro vizinho). No modo `componentes` a decisão é do **desenho**:

1. o conteúdo da prancha é afinado (erosão) até a grade fina e o texto sumirem;
2. cada massa que resta é rotulada e atribuída à célula onde está o seu **centro**;
3. o recorte de cada quadro é a **união** das massas dele — corpo, cajado, bola e
   partículas, mesmo que uma peça passe da fronteira.

Como o recorte passa a ser o desenho, a conferência muda de nome: sai a
*cobertura* (fração da célula) e entra a **preservação** (fração do desenho que
ficou de fato, medida contra a máscara original). Abaixo de 90% a ferramenta
avisa — na prancha do bruxo o resultado ficou entre 89% e 91%, e o que "falta" é
a grade interna, a numeração e o anti-aliasing, todos removidos de propósito.

### O rótulo não tem altura fixa

`--fracao-rotulo` corta uma porcentagem fixa do rodapé — se o personagem tem os
pés baixos, o corte come o pé (foi o que aconteceu na primeira tentativa). Por
isso o modo `componentes` procura o **vazio** entre o desenho e o texto impresso
(`vale_do_rotulo`) e usa essa linha como base da célula. A linha encontrada é
impressa no terminal (`fim do desenho por linha: L1=143, ...`), o que serve de
conferência.

## Ajustes quando a grade automática erra

* `--forca-pico 0.4` (mais frouxo) acha grades mais claras; `0.7` (mais rígido)
  evita falsos positivos em prancha com muito contraste interno.
* `--ajustar-fronteiras 60` procura, em cada linha, o vazio mais próximo para
  cada fronteira de coluna (útil quando o desenho é descentralizado; substituído
  por `--grade componentes` quando a arte atravessa a divisória).
* `--fracao-rotulo 0.3` descarta uma faixa maior embaixo (rótulos altos).
* `--tolerancia 30` remove mais fundo (útil se o papel tem sombra/vinheta);
  `--tolerancia 15` preserva mais detalhe claro (arte com muita cor clara).
* `--debug` salva `grade-detectada.png` com as linhas que ele encontrou.

## Caso real: `bruxo-casting.jpg`

O que a prancha do personagem principal ensinou (o resultado está em
`art/bruxo-casting/`, com `LEIA-ME.md` próprio):

* a detecção automática **não** serve aqui: as linhas de grade são só 4–6 níveis
  de luminância mais claras que o fundo da célula, e o modo automático acaba
  achando o contorno dos desenhos (27 colunas em vez de 7). As fronteiras foram
  medidas com `--diagnostico` + inspeção de luminância e escritas na mão;
* as células trazem grade **dentro** delas (linhas finas, cinzas e brancas). Elas
  são removidas pela linearidade (`remover_grade_interna`): linha que cobre boa
  parte da célula e é neutra — o miolo branco da magia é neutro, mas não é
  linear, e sobrevive;
* o alfa não pode vir da luminância do fundo no interior do desenho: o miolo
  branco da bola de relâmpago é **mais claro** que o fundo da prancha e sumia. O
  interior agora fica opaco e a rampa de alfa só vale na primeira camada de
  pixels em volta do fundo (anti-aliasing);
* a coluna da direita (`Original S/N/E/W`) é referência: `--colunas 7` a descarta.

## Próximo passo (depois de extrair)

Os frames saem grandes (≈80x70) e não têm o padrão do resto do projeto (célula
32x32, âncora nos pés, tags do Aseprite). Para entrar no jogo e na Unity:

1. reduza para a célula do projeto (32x32 ou 48x48) mantendo o pixel art;
2. monte a tira horizontal e o JSON de animação (mesmo formato do Aseprite);
3. rode as ferramentas de conferência:

```bash
python3 tools/limpar_sprites.py --dir <pasta> --report
node tools/verificar_assets.mjs
node tools/smoke_personagem.mjs
```

A especificação de célula, pivot e nomes de tag está em
[`../unity/LEIA-ME.md`](../unity/LEIA-ME.md).
