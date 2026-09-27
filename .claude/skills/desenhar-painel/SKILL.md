---
name: desenhar-painel
description: Propõe e desenha a frente de um módulo (painel de seção) do cockpit KSP, em algumas versões para comparar, na identidade visual do projeto, e publica uma página com os desenhos. Use quando o usuário pedir para desenhar, organizar ou sugerir o layout de um painel ou módulo (ex.: "/desenhar-painel sistemas de controle").
---

# Desenhar um painel do cockpit

O objetivo é o mesmo da primeira rodada do editor de manobras: **mostrar algumas versões diferentes do painel, lado a lado, com prós e contras, para o usuário escolher e ir mudando no chat.** Depois que ele escolhe, a versão entra no repositório.

O argumento é o módulo a desenhar (ex.: `sistemas de controle`, `action groups`, `tempo`). Sem argumento, pergunte qual.

## 1. Ler o que o repositório já diz

Antes de perguntar ou desenhar, leia:

- `hardware/identidade_visual.md`: cores, letras, painel de 150 × 150 mm, peças e as regras para organizar. **Siga à risca.**
- `hardware/construcao.md`: formato da caixa (onde o painel fica e qual mão usa), korry e os painéis já desenhados. A seção "Painel do editor de manobras" é o exemplo pronto.
- `hardware/korry/README.md`: o korry, a peça mais usada.
- `hardware/README.md`, tabela "Qual placa e qual etiqueta em cada seção": quantas entradas e LEDs o módulo tem hoje e em qual placa (8, 16 ou 24 entradas).
- `README.md`: princípios, decisões e a fase do roteiro em que o módulo aparece. Procure o nome do módulo.
- `docs/protocolo.md` e o doc do módulo em `docs/`, se existir: as mensagens que os controles mandam.

Anote o que **já está fixado** (controles, mensagens, decisões) e o que **está aberto**. O desenho tem que respeitar o fixado, ou dizer claramente o que propõe mudar.

## 2. Perguntar antes de desenhar

O usuário prefere ser perguntado quando a tarefa é grande ou ambígua. Use a ferramenta de perguntas com opções, a recomendada primeiro e marcada "(Recomendado)". Até 4 perguntas, só as que mudam o desenho. As que valeram na primeira rodada:

- Quais controles entram (se o roteiro não fecha a lista).
- Se o desenho respeita o número de entradas e LEDs da placa ou fica livre.
- Algo do módulo que tenha duas saídas razoáveis (ex.: um botão que alterna ou um botão por opção).

Não pergunte o que a identidade visual já responde (estilo, cores, tamanho do painel, peças).

## 3. Pensar as versões

Faça **3 versões que mudam a ideia**, e não só a posição dos botões. Os ângulos que funcionaram no editor de manobras:

- **Clássico:** a lista do roteiro, em faixas. O mais simples de fazer; serve de base.
- **Direção física:** cada controle se mexe como a coisa no jogo (a tecla do TEMPO deitada, porque o nó anda para os lados na órbita), com as cores do KSP onde a cor diz qual coisa é. Foi a escolhida no editor.
- **Completo ou diferente:** junta uma função vizinha (o ARM e o EXEC no editor) ou muda a forma (um painel de dois quadrados).

Use as regras de "Como organizar um painel" da identidade visual, que saíram das rodadas do editor: um controle por coisa que se mexe junto (um encoder para os três eixos do Δv), o estado visível sem olhar a tela, o que é perigoso longe e protegido.

Para cada versão, anote: a ideia em uma frase, o que é bom, o que é ruim, o tamanho, as entradas e os LEDs.

## 4. Desenhar

Use as peças de `hardware/desenho/pecas.js`, que já estão no tamanho real e na identidade visual (ver `hardware/desenho/README.md`):

1. Crie um arquivo por versão em `hardware/desenho/paineis/`, copiando `editor_manobras.js`. Os rascunhos das versões podem ficar ali enquanto você trabalha, mas só a versão escolhida é commitada.
2. Gere com `node hardware/desenho/desenhar.js <nome>`, confira o SVG e cole o conteúdo dele na página.
3. Painel de 150 × 150 mm (ou 300 × 150), grupos a 10 mm das bordas dos lados e 6 mm entre si, 3 mm entre peças, título em cima, legendas em maiúsculas sem acento.
4. Mostre o painel ligado: o korry do estado atual aceso, o knob numa posição.

## 5. Publicar a página

Uma página (artifact) com, nesta ordem:

1. **Cabeçalho:** o módulo, o que o roteiro já fixou e a escala.
2. **Legenda:** as cores das luzes e, se houver, as cores do KSP usadas.
3. **Uma seção por versão:** o desenho à esquerda; à direita a etiqueta (A, B, C; a sugerida em destaque), um título que diz a ideia, uma frase de explicação, "Bom" e "Ruim" em listas curtas e a linha `tamanho · entradas · LEDs`.
4. **Peças que servem em qualquer versão:** as escolhas que dá para trocar entre as versões (ex.: como mostrar o passo), em cartões pequenos com um desenho.
5. **Comparação** numa tabela, **a sugestão** com o porquê em duas frases e **"Para decidir"**, uma lista numerada de perguntas.

Olhe a página renderizada uma vez, corrija o que estiver quebrado e publique. Na resposta do chat: o link, uma tabela curta das versões e a sugestão. Diga que o repositório não mudou.

## 6. Iterar e registrar

O usuário vai mudar a versão escolhida pelo chat. A cada mudança, atualize os desenhos e republique a mesma página. Quando ele pedir para registrar:

- Uma seção do painel em `hardware/construcao.md` (ou em `hardware/<peça>/README.md`, se for uma peça nova usada em vários painéis), com o SVG, os grupos e a tabela de peças com medidas.
- O arquivo do painel em `hardware/desenho/paineis/` e o SVG em `hardware/img/`.
- O que mudar fora do desenho: o roteiro no `README.md`, a lista de compras, as mensagens em `docs/protocolo.md` (marcadas como planejadas se a ponte ainda não as trata), a tabela de placas e etiquetas em `hardware/README.md` e uma lista "A fazer" no roteiro para o código.
- Siga o `CLAUDE.md`: merge do `main`, verificação (os testes e o `pyflakes`, mais `node hardware/desenho/desenhar.js`), commit, PR e merge com squash.
