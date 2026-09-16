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

## Ajustes quando a grade automática erra

```bash
# grade informada na mão (x0,y0 = canto do primeiro quadro; célula = largura x altura)
python3 tools/extrair_spritesheet.py --entrada prancha.jpg --grade manual \
    --x0 22 --y0 44 --celula 148x72 --colunas 7 --linhas 6
```

* `--forca-pico 0.4` (mais frouxo) acha grades mais claras; `0.7` (mais rígido)
  evita falsos positivos em prancha com muito contraste interno.
* `--fracao-rotulo 0.3` descarta uma faixa maior embaixo (rótulos altos).
* `--tolerancia 30` remove mais fundo (útil se o papel tem sombra/vinheta);
  `--tolerancia 15` preserva mais detalhe claro (arte com muita cor clara).
* `--debug` salva `grade-detectada.png` com as linhas que ele encontrou.

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
