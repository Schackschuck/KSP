# Identidade visual do cockpit

Como todo painel do cockpit tem que parecer: cores, letras, medidas e peças. Vale para os painéis de verdade (laser e impressora) e para os desenhos. O exemplo de referência é o painel do editor de manobras:

![Painel do editor de manobras, o exemplo da identidade visual](img/editor_manobras.svg)

A referência são os painéis de avião, como o overhead do A320 e o MCP do Boeing: sóbrios, cinza escuro, legendas brancas e botões iluminados. O KSP entra nos detalhes, como as cores das alças do nó de manobra.

## Painel

| O quê | Como é |
|---|---|
| Tamanho | **150 × 150 mm**, igual em todos. Uma seção que precise de mais espaço ocupa dois quadrados (300 × 150 mm) |
| Material | MDF ou acrílico de 3 mm, cortado e gravado a laser |
| Cor | Cinza escuro fosco, `#30353a` nos desenhos, com borda `#15181b` e cantos arredondados de 2,5 mm |
| Fixação | 4 parafusos M3 nos cantos, com o centro a 6 mm das bordas |
| Título | O nome da seção, gravado em cima e centrado, com letras de 4 mm. Ex.: `EDITOR DE MANOBRAS` |
| Margem | Os grupos começam a 10 mm das bordas dos lados, para não bater nos parafusos |

## Grupos

Dentro do painel, os controles ficam em **grupos**, cada um com uma linha em volta e o nome interrompendo a linha de cima, como nos painéis de avião. Assim a mão acha o grupo sem olhar.

- Linha branca de 0,35 mm, cantos de 1,2 mm.
- Nome em cima, centrado, com letras de 2,8 mm.
- 6 mm entre grupos vizinhos.
- **O nome diz o que o grupo faz, e não o nome de um controle:** o grupo com o TEMPO, o ANT e o PROX se chama `PERCURSO`, porque anda pelo caminho da nave. Não repetir o nome de outra seção do cockpit (já existe uma `NAVEGACAO`).
- Em cima, o que ajusta; embaixo, o que age (criar, apagar, executar).

## Letras

- **Fonte:** [B612](https://fonts.google.com/specimen/B612), feita pela Airbus para as telas de cockpit e livre. Negrito nas legendas. Para números alinhados, B612 Mono.
- **Sempre maiúsculas e em ASCII, sem acentos**, como no LCD e na serial: `NO`, e não `NÓ`; `AMBAR`, e não `ÂMBAR`.
- **Cor:** branco `#eef0ea` para as legendas; cinza `#b9bfc5` para as legendas de apoio (unidades, lembretes como `M/S · TEMPO`).

| Onde | Altura das letras (tamanho no desenho) |
|---|---|
| Título do painel | 4 mm |
| Nome do grupo, nome de um controle | 2,8 a 3,2 mm |
| Legenda dos lados de um controle (`ANTES` / `DEPOIS`) | 2,4 a 2,6 mm |
| Legenda de apoio | 1,9 a 2,4 mm |

## Cores das luzes

Sempre com o mesmo significado:

| Cor | Significa | Exemplos |
|---|---|---|
| Verde | Sistema ligado, tudo normal; o modo assumiu | SAS, RCS, trem baixado; modo do SAS segurando |
| Azul | Armado: escolhido, mas ainda não assumiu | Modo do SAS com a nave virando para o marcador; ALT do piloto automático subindo até a altitude |
| Branco | Informação, modo escolhido | Página da tela |
| Âmbar | Atenção | Combustível baixo, script armado, pedido recusado |
| Vermelho | Perigo | ABORT, script abortado |

**A luz mostra o estado do jogo**, nunca a posição da chave nem o toque. O azul e o verde seguem os modos do piloto automático do Airbus: azul armado, verde ativo.

**Exceção: cores do KSP** onde a cor diz *qual* coisa é, e não um estado. Nos eixos do nó de manobra: verde-amarelo `#c6e04a` para o pró-grado, magenta `#d24fe0` para o normal e ciano `#40c9e3` para o radial, como as alças do nó no jogo.

## Peças

Sempre as mesmas peças, no mesmo tamanho, para os painéis combinarem e as peças servirem em qualquer lugar. Medidas de catálogo, a conferir no paquímetro.

| Peça | Na frente | Furo | Para quê |
|---|---|---|---|
| [Korry](korry/README.md) | 22,5 × 22,5 mm | 23 × 23 mm | Tudo que liga, desliga ou escolhe: a legenda acesa é o estado do jogo. Nos modos do SAS, a legenda é o marcador da navball, com a palavra embaixo |
| LED de 3 mm com anel de metal | anel Ø 5 mm | Ø 5 mm | Mostrar um estado sem gastar um botão: os modos do piloto automático |
| Encoder EC11 com knob de alumínio | knob Ø 30 mm | Ø 7 mm | Ajustar um valor. Horário soma, anti-horário tira, com um arco `-` / `+` gravado em volta |
| Chave rotativa, 12 posições com batente | knob de ponteiro Ø 22 mm | Ø 9,5 mm | Escolher entre poucas opções fixas, com a legenda gravada em volta |
| Tecla basculante com mola para o centro | 21 × 15 mm | 19 × 13 mm | Mover para um lado ou outro, como o TIME WARP. Segurando, repete |
| Botão de metal sem trava | Ø 14 mm | Ø 12 mm | Ações pequenas, como ANT e PROX |
| Chave alavanca com capa vermelha | capa 14 × 22 mm | Ø 6 mm | Só o que precisa de duas ações de propósito: ARM |
| Botão grande com capa | a definir | a definir | STAGE e ABORT, na faixa zebrada |

- **3 mm de borda a borda** entre peças vizinhas, no mínimo.
- **Zona de perigo:** faixa zebrada amarela e preta em volta, com capa de proteção.
- **Sem tela nos módulos:** os números vão para a tela multifunção, no meio do cockpit, que troca para a página do módulo em uso.

## Como organizar um painel

As regras que saíram do desenho do editor de manobras:

1. **Um controle por coisa que se mexe junto.** O Δv nunca é mexido nos três eixos ao mesmo tempo, então é um encoder só, com korry para escolher o eixo.
2. **O controle se mexe como a coisa no jogo.** A tecla do TEMPO fica deitada: para a esquerda o nó volta na órbita, para a direita avança. ANT e PROX, embaixo, no mesmo sentido.
3. **Mostrar o estado sem olhar a tela** quando der de graça: a posição do knob da chave rotativa mostra o passo.
4. **O que se usa mais é maior ou fica mais à mão.**
5. **O que é perigoso fica longe e protegido.**

## Desenhos

- **Unidades em milímetros**, com as peças no tamanho real e as cotas do painel.
- Feitos com as peças de [`desenho/pecas.js`](desenho/pecas.js); cada painel é um arquivo em [`desenho/paineis/`](desenho/paineis/), e `node hardware/desenho/desenhar.js` gera o SVG em `hardware/img/`. Como fazer um painel novo: [desenho/README.md](desenho/README.md).
- O desenho mostra o painel como ele fica ligado: o korry do estado atual aceso, o knob numa posição.
