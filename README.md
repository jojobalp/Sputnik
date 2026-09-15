# Sobreviva à Noite

Protótipo de survival horror top-down em Canvas e JavaScript, sem assets externos de jogo. Interface em português.

## Executar

```sh
npm install
npm run dev
```

Abra a URL exibida pelo Vite. Requer navegador moderno e teclado/mouse.

## Jogar

- WASD / setas: movimento; mouse: orientar a tocha; E: interação; Esc: pausa.
- A noite dura seis minutos reais (um segundo equivale a um minuto do jogo).
- Óleo restaura 40% de combustível. Sem luz, a entidade ataca em três segundos.
- Ligue o gerador no sudoeste, recolha duas tábuas e sele as janelas ao norte do cômodo central, reúna três fragmentos e alcance a porta ao sul às 06:00.
- Aponte para as sombras por 1,3 segundo para afastá-las.
- Itens e posições das portas são sorteados em cada partida. As seis salas permanecem conectadas.
- Som ambiente sintetizado com Web Audio, ativado pelo botão de som. Pausa automática ao sair da aba.

## Escopo

Protótipo com arte pixel procedural, colisões, iluminação radial, tempestades, aparições, medo, notas aleatórias, inventário e estados de vitória/derrota. Não inclui arte final, salvamento, controles de toque ou áudio de vozes. O amanhecer não causa derrota automática: se faltarem tarefas, a porta permanece selada até sua conclusão.

## Compilar executável completo para Windows

```sh
npm ci
npm test
npm run build:windows
```

Saída em `out/windows/`: um `.exe` portátil (contém o runtime e não precisa de instalação) e um `.zip` com a aplicação completa. No ZIP, preserve os arquivos que acompanham o executável. O jogo funciona offline e F11 alterna tela cheia. O executável não possui assinatura digital.

O workflow `.github/workflows/windows.yml` compila no Windows e disponibiliza o pacote em **Actions → Compilar jogo para Windows → Artifacts → Sobreviva-a-Noite-Windows-64bits**. Downloads de artifacts exigem login no GitHub e expiram após 30 dias. Depois de baixar, você pode enviar o `.exe` portátil ao amigo pelo serviço de arquivos de sua preferência.

Esta cópia recuperada ainda não contém a dificuldade por hora nem os três subsolos. Os testes verificam a configuração da janela e o empacotamento; não representam uma partida testada em Windows real.
