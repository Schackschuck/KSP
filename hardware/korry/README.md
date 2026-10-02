# Korry switch

O botão iluminado quadrado dos aviões, feito em casa: a legenda fica no próprio botão e acende. É uma peça só, **do mesmo tamanho em todo o cockpit**, usada em vários painéis. Por que usar korry e onde ele entra no painel está em [construcao.md](../construcao.md#korry-switches).

**Status: modelo pronto para o primeiro teste de impressão, nada construído.** São quatro peças impressas e não há placa perfurada, peça de laser nem placa fabricada: a chave e os LEDs encaixam direto num suporte impresso. Só a **legenda**, em duas cores, muda de korry para korry; o **corpo**, a **base** e o **suporte** são pretos e iguais para todos.

| Frente | Corte | Peças |
|---|---|---|
| ![Frente do korry de teste: SAS em cima e SEM EC na caixa embaixo](img/frente.png) | ![Corte do korry montado no painel](img/corte.png) | ![Korry explodido: legenda, corpo, base, suporte, chave e LEDs](img/explodida.png) |

## Arquivos

| Arquivo | O que é |
|---|---|
| [`korry.scad`](korry.scad) | O modelo no [OpenSCAD](https://openscad.org/), com as medidas e a legenda nas primeiras linhas. Para as letras saírem certas, instalar a fonte [B612](https://fonts.google.com/specimen/B612) Bold |
| [`stl/legenda_preto.stl`](stl/legenda_preto.stl) e [`stl/legenda_transparente.stl`](stl/legenda_transparente.stl) | A legenda do korry de teste (`SAS` / `SEM EC`), nas mesmas coordenadas, para imprimir junto com os dois bicos |
| [`stl/korry_corpo.stl`](stl/korry_corpo.stl) | O corpo, igual para todos. Preto, um bico só |
| [`stl/korry_base.stl`](stl/korry_base.stl) | A base, que fica atrás do painel. Preta, um bico só |
| [`stl/korry_suporte.stl`](stl/korry_suporte.stl) | O suporte da chave e dos LEDs. Preto, um bico só |
| [`stl/korry_teste.stl`](stl/korry_teste.stl) | O teste de folga: 5 encaixes de 0,1 a 0,3 mm e um pedaço do corpo |
| [`ligacao.js`](ligacao.js) | Gera [`ligacao.svg`](ligacao.svg), o desenho da ligação da chave e dos LEDs: `node hardware/korry/ligacao.js` |
| [`korry.svg`](korry.svg) | O desenho da primeira especificação, com a tampa de acrílico: os quatro estados da legenda continuam valendo |

Para gerar outra legenda: `openscad -D 'peca="legenda_preto"' -D 'texto_cima="RCS"' -D 'texto_baixo="SEM MP"' -o legenda_preto.stl korry.scad`, e o mesmo com `peca="legenda_transparente"`. Com `texto_baixo=""`, a legenda é única. O corpo, a base e o suporte não mudam.

Para gerar de novo os STL das peças iguais para todos, dentro de `hardware/korry/`: `openscad -D 'peca="corpo"' -o stl/korry_corpo.stl korry.scad`, e o mesmo com `peca="base"` e `peca="suporte"`.

As imagens saem do próprio `korry.scad`, dentro de `hardware/korry/` (no Linux sem tela, com `xvfb-run -a` na frente). O `peca="corte"` mostra a montagem cortada ao meio, com a face cortada nas cores das peças; o `peca="montagem"` é a montagem inteira, sem corte.

```
openscad -D 'peca="frente"' --imgsize=600,600 --projection=o --viewall --autocenter --camera=0,0,0,0,180,0,100 --colorscheme=Tomorrow -o img/frente.png korry.scad
openscad -D 'peca="corte"' --imgsize=800,560 --projection=o --viewall --autocenter --camera=0,0,0,0,180,0,100 --colorscheme=Tomorrow -o img/corte.png korry.scad
openscad -D 'peca="explodida"' --imgsize=800,600 --viewall --autocenter --camera=0,0,0,-25,210,0,200 --colorscheme=Tomorrow -o img/explodida.png korry.scad
```

## Referências

- **Aparência:** o botão START do A320, com a legenda em duas metades: em cima `AVAIL`, só as letras; embaixo `ON`, dentro de uma caixa. Cada metade acende sozinha, na sua cor. Apagadas, as legendas continuam legíveis.
- **Circuito:** uma chave e dois LEDs encaixados num suporte impresso atrás do corpo, ligados por um rabicho de 4 fios com um conector de 4 vias na ponta.

## Onde vai

Na [versão B do cockpit](../construcao.md#cockpit-versão-b) são 35:

| Painel | Korry | Legenda |
|---|---|---|
| Voo | 14 | 10 modos do SAS: o marcador da navball com a palavra embaixo, LED azul e verde. SAS, RCS e FBW: duas metades. TRAVA ALT: uma legenda |
| Ação executiva | 6 | Os scripts: POUSO e cinco vagos, LED vermelho e verde (âmbar com os dois) |
| Editor de manobras | 3 | PRO, NRM e RAD: uma legenda, acesa no eixo escolhido |
| Action groups | 4 | PARAQUEDAS, SOLAR, ANTENAS e CARGA: uma legenda, verde |
| Acelerador | 3 | TREM, FREIOS e LUZES: uma legenda, verde |
| Recursos e EVA | 2 | JATO e LUZ: uma legenda, verde |
| Câmera | 2 | MAPA e IVA: uma legenda, branca. O IVA com capa |
| Tempo | 1 | FISICO: uma legenda, branca |

Os botões que não têm luz para mostrar (os action groups 1 a 10, NOVO, APAGAR, CIRC) viraram botões de metal comuns.

## Medidas

| O quê | Medida | Observação |
|---|---|---|
| Frente | **22,5 × 22,5 mm** | Igual em todos |
| Furo no painel | 23 × 23 mm | 0,25 mm de folga por lado. Conferir na plaquinha de teste da laser, que queima um pouco em volta do corte |
| Saliência na frente do painel | 3 mm | A legenda. O corpo anda ~2,2 mm até a chave chegar ao fim (curso de 2,5 mm menos 0,3 mm de pré-carga) e a legenda ainda sai ~0,8 mm do painel |
| Corpo | 16 mm de fundo | Da frente até os ressaltos de trás |
| Base | 25,3 × 25,3 mm, 16 mm de fundo | Cabe no passo de 25,5 mm entre korry vizinhos |
| Suporte | 25,3 × 25,3 × 1,6 mm | Preso pelos ganchos da base |
| Atrás do painel | ~22 mm | Até as pernas da chave, que saem atrás do suporte. Somar os fios |
| Distância entre korry vizinhos | 3 mm | De borda a borda |
| Legenda | 22,5 × 22,5 × 3 mm | Encaixa por pressão na ponta do corpo, com duas abas |
| Legenda de cima | letras de 3 mm | B612 Bold |
| Legenda de baixo | letras de 2,4 mm, numa caixa de 15 × 5,6 mm | Como o `ON` do A320 |
| Legenda única | letras de 3 mm, centradas | Sem a divisória |
| Chave | PSW 8,5 × 8,5 mm, 8 mm de altura | O êmbolo sai 5,5 mm e tem 2 × 3 mm |
| Curso da chave | ~2,5 mm | Conferir na chave real |
| Divisória | No centro do korry | A do corpo começa 4 mm atrás da legenda. Na legenda única, a luz das duas metades se mistura nesse vão; na de duas metades, uma aleta preta da legenda fecha o vão |

## Peças

- **Legenda**, impressa em duas cores numa peça só, de frente para baixo na mesa. É a única peça que muda de korry para korry:
  - **Preto:** a borda de 1 mm, uma camada de 0,6 mm na frente com a legenda vazada e a divisória que separa a luz das duas metades. Atrás dela saem duas abas com dente, uma em cima e outra embaixo, que travam o corpo.
  - **Transparente:** as letras da legenda, nos furos da camada preta, e o bloco de 2,4 mm atrás dela, dividido em dois pela divisória. Apagada, a legenda aparece clara; acesa, na cor do LED.
- **Corpo:** um tubo preto de 16 mm de fundo, igual para todos, em que a legenda encaixa por pressão (as abas entram nas janelas das paredes de cima e de baixo). Na ponta de trás, dois ressaltos nos lados correm nos trilhos da base e seguram o corpo. Por dentro tem uma divisória, que continua a da legenda, com um apoio que empurra o êmbolo da chave e asas que separam a luz dos lados da chave.
- **Base:** um tubo preto atrás do painel, com os trilhos por onde o corpo desliza e dois ganchos que prendem o suporte. Fica colada atrás do painel, ou presa numa grade impressa para o grupo todo (os 10 modos do SAS numa peça), parafusada no painel. Não leva os parafusos M2 da primeira especificação: com 3 mm entre korry, as abas não cabem.
- **Suporte:** uma plaquinha preta de 1,6 mm, com 6 furos para as pernas da chave, 4 para as pernas dos LEDs, uma nervura de cada lado da chave, logo acima da divisória, para a luz não passar por baixo das asas e a palavra `CIMA` gravada atrás. É igual para todos.
- **Chave PSW 8,5 × 8,5 mm, sem trava**, de 6 pinos. Usa um polo só: o comum e o contato que fecha apertado. A mola da chave devolve o corpo. O curso é curto, como no botão do avião.

## Montagem do suporte

A chave e os LEDs entram pela frente do suporte e as pernas saem atrás. Os 4 fios são soldados direto nelas e terminam num conector JST-XH fêmea de 4 vias, um rabicho de uns 10 cm.

![Suporte: na frente a chave no meio e um LED acima e outro abaixo; no verso as pernas, os 4 fios e o conector JST-XH visto pelo lado dos fios](ligacao.svg)

1. **Chave** pela frente, com as pernas nos 6 furos e o êmbolo para a frente.
2. **LEDs de 3 mm**, um acima e outro abaixo da chave, pela frente. O catodo (perna curta, lado chato) vai para a esquerda, olhando a frente, como no desenho.
3. **Multímetro:** descobrir qual perna da fileira de cima fecha com a perna do meio só com a chave apertada. É a que vai para o BTN. O desenho mostra a ponta; se for a outra, trocar.
4. **Soldar os fios no verso**, como no desenho. O GND emenda o catodo do LED de cima, a perna do meio da chave (o comum) e o catodo do LED de baixo. O LC vai no anodo do LED de cima, o LB no anodo do de baixo e o BTN na perna que fecha.
5. **Isolar** cada solda com espaguete termo-retrátil.
6. **Crimpar o JST-XH fêmea de 4 vias** na ponta dos fios, na ordem 1 GND, 2 BTN, 3 LC, 4 LB. O desenho mostra o conector visto pelo lado dos fios, com os pinos 4 3 2 1 da esquerda para a direita.
7. **Prender o suporte** nos ganchos da base, com a palavra `CIMA` para cima.

- **Modos do SAS:** o LED azul e verde (3 pernas) vai no lugar do LED de cima: azul no LC, verde no LB, catodo no GND. A ordem das pernas muda de fabricante para fabricante: testar antes de soldar. Os furos do LED de baixo ficam vazios.
- **Korry sem luz:** só a chave e 2 fios (GND e BTN). Os furos dos LEDs ficam vazios.
- **Trocar a legenda:** soltar o suporte dos ganchos, puxar o corpo para trás, para fora da base, e apertar os dois dentes pelas janelas com uma chave de fenda pequena. A legenda nova entra empurrando, até os dentes estalarem nas janelas.
- **Montou errado?** Girado 90°, os LEDs batem nas asas da divisória e o suporte não encaixa. Girado 180° monta, mas troca cima e baixo: por isso o `CIMA` gravado.

## Circuito

```
  módulo                               korry
  ──────                               ─────
  INn   ─────────────── 2 BTN ────┐
                                  └─[ chave ]──┐
  LEDn  ──[1 kΩ]─────── 3 LC ───►|─ LED de cima ─┤
  LEDm  ──[1 kΩ]─────── 4 LB ───►|─ LED de baixo ┤
  GND   ─────────────── 1 GND ─────────────────┘
```

- **Não tem CI nem resistor no korry.** O pull-up da entrada e os resistores dos LEDs já estão no módulo (ver o [README do hardware](../README.md#no-módulo)). O korry é só chave, LEDs e fios.
- **Conector de 4 pinos:** 1 GND, 2 BTN, 3 LC (LED de cima), 4 LB (LED de baixo). JST-XH fêmea de 4 vias (passo de 2,5 mm) na ponta do rabicho, que liga direto no jack do módulo. O [módulo médio](../README.md#pcb-do-módulo-médio) já tem 12 jacks JST-XH nessa ordem: o korry do jack Kk usa a entrada IN(k−1) e as saídas LED(2k−2) e LED(2k−1).
- **Apertado lê 0**, como qualquer botão dos módulos.
- **Cada korry gasta 1 entrada e 0, 1 ou 2 saídas de LED:**
  - duas metades: 2 saídas;
  - legenda única acesa: 1 saída, com os dois LEDs em paralelo nela;
  - legenda única sem luz (NOVO, APAGAR, CIRC): nenhuma, e os LEDs nem são montados;
  - legenda única de duas cores (os modos do SAS): 2 saídas, com um LED azul e verde de catodo comum. O pino 3 (LC) acende o azul, o 4 (LB) o verde; o conector e o circuito não mudam.
- **A cor é a do LED**, escolhida na montagem, porque a tampa é branca. Uma cor fixa por metade, das cores da [identidade visual](../identidade_visual.md#cores-das-luzes): verde, azul, branco, âmbar ou vermelho. Os modos do SAS têm as duas cores no mesmo LED. A exceção são os korry de eixo do editor, nas cores das alças do nó no KSP (verde-amarelo, magenta e ciano), porque a cor ali diz qual é o eixo, e não um estado.

### Brilho

Com o resistor de 1 kΩ do módulo, cada LED recebe uns 3 mA (uns 2 mA os brancos). Atrás de 2,4 mm de PLA transparente pode ser pouco. O módulo médio usa 220 Ω, uns 13 mA por LED: bem mais forte, mas passa do limite do 74HC595 com os 8 LEDs dele acesos juntos.

1. Testar primeiro com 1 kΩ, no escuro e de dia.
2. Se ficar fraco, trocar o resistor daquela saída no módulo por 470 Ω: uns 6 mA por LED.
3. Não passar de uns 8 mA por LED: cada 74HC595 aguenta 70 mA no total, e com 8 LEDs acesos juntos 8 mA já dá 64 mA.
4. Na legenda única com dois LEDs na mesma saída, a corrente se divide entre os dois: é o caso que mais pede 470 Ω.

## O que as luzes dizem

Como em todo o painel, **a luz mostra o estado do jogo, nunca o toque**. O korry só avisa "apertei" (`BTN SAS 1`); a ponte decide e o LED acende quando o jogo confirma. O firmware não muda: já manda botões e acende LEDs.

| Metade | Acende quando | Exemplo |
|---|---|---|
| Cima | O sistema está ligado no jogo | `SAS` verde: o SAS está ligado |
| Baixo, na caixa | Algo pede atenção | `FAULT` âmbar: o pedido foi recusado, por exemplo a nave não tem SAS. A ponte acende por uns segundos |
| Única | O estado ou modo está escolhido | `PRO` verde-amarelo: o encoder mexe no pró-grado |
| Única, duas cores | Azul: o modo foi escolhido e ainda não assumiu. Verde: assumiu | Modo do SAS: azul com a nave virando, verde com ela no marcador |

## Como imprimir

Na FlashForge Inventor, que tem dois bicos, com o FlashPrint:

1. **Teste de folga** ([`korry_teste.stl`](stl/korry_teste.stl)), só em preto. A folga em que o pedaço de corpo desliza sem balançar vai para a variável `folga` do `korry.scad`, e o corpo e a base são gerados de novo.
2. **Uma legenda de teste:** abrir [`legenda_preto.stl`](stl/legenda_preto.stl) e [`legenda_transparente.stl`](stl/legenda_transparente.stl) juntos e aceitar quando o FlashPrint perguntar se é um modelo de duas cores, para as partes ficarem no lugar. PLA preto num bico, transparente no outro. Já estão de frente para baixo.
3. **Torre de limpeza** (*wipe wall*) ligada, para o transparente não sair sujo de preto.
4. **Corpo, base e suporte**, só em preto, um bico só. Já estão na posição certa (o corpo e o suporte de trás para baixo): não precisam de suporte de impressão.
5. Camada de 0,12 mm, 3 perímetros, sem suporte.

**O que pode dar errado no teste:**

- **Letras finas sumindo:** o `SEM EC` tem 2,4 mm, e os traços ficam perto da largura do bico. Se falhar, `letra_baixo = 2.8`, ou ligar a opção de paredes finas no FlashPrint.
- **Luz vazando de uma metade para a outra:** a divisória tem 1 mm. Se vazar, `divisoria_e = 1.6`.
- **Aba da legenda dura demais ou quebrando:** `dente = 0.4` ou `aba_e = 0.7`.
- **Luz vazando em cima da chave:** é o vão do curso, onde o corpo anda sobre a chave. Apagado não aparece; com uma metade acesa, a outra pode ganhar um brilho fraco. Se incomodar, passar tinta preta fosca ou fita isolante nas laterais de cima da chave.
- **Sombra da divisória na legenda única:** a divisória do corpo continua lá, atrás da legenda. Se a sombra dela aparecer, aumentar o `recuo`.
- **Furos das pernas apertados:** `furo_pino` (chave) e `furo_led` (LEDs).
- **Chave diferente do desenho:** conferir `pino_fileiras`, `curso` e `haste_h` com a chave real.

## Lista de peças (um korry)

- Legenda em PLA preto e transparente; corpo, base e suporte em PLA preto.
- 1 chave PSW 8,5 × 8,5 mm, sem trava, de 6 pinos.
- 0 a 2 LEDs de 3 mm, difusos, de alto brilho, na cor da legenda. Nos modos do SAS, 1 LED azul e verde de 3 mm, difuso, de catodo comum.
- 4 fios finos (~10 cm) e 1 conector JST-XH fêmea de 4 vias, com os terminais.
- Espaguete termo-retrátil para isolar as soldas.

## Ordem para fazer

1. **Teste de folga** e ajuste da `folga` no modelo.
2. **Um korry de teste**, ligado direto num pino do Mega como na [fase 2](../../docs/fase2.md): a legenda, o clique, a folga do corpo na base, a força do encaixe da legenda e o brilho, com 1 kΩ e com 470 Ω.
3. **Os 35**, cada um com a sua legenda, inclusive os ícones dos modos do SAS, depois que o teste der certo.

## A decidir

- A folga, depois do teste.
- O curso e as medidas reais da chave PSW (`curso`, `haste_h`, `pino_fileiras`).
- A força do encaixe da legenda: se as abas seguram sem quebrar nem soltar.
- Colar a base atrás do painel ou fazer uma grade impressa por grupo.
- Os ícones dos modos do SAS no modelo (hoje o `korry.scad` só faz letras).
