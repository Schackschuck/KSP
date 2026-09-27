# Construção física: carcaça, aparência, korry switches e joystick

Este documento trata da parte física do cockpit: o formato da caixa, a aparência, como fabricar as peças, os korry switches e onde entra o joystick. A eletrônica dos módulos está no [README do hardware](README.md); a arquitetura e o roteiro, no [README principal](../README.md).

**Status: ideias, nada construído.** A caixa definitiva é da [fase 7](../README.md#fase-7--hardware-definitivo), mas protótipos (um korry, um painel de seção) podem ser feitos antes, junto com os módulos da fase 2.

## Ferramentas disponíveis

| Ferramenta | Onde | Serve para |
|---|---|---|
| **Impressora 3D** | em casa | Peças pequenas e com forma complicada: korry switches, knobs, suportes de placa, moldura da tela, base do joystick, passa-cabos. |
| **Corte a laser** | no colégio | Peças planas e grandes: as paredes da caixa e os painéis frontais, com furos e legendas gravadas. |
| **Logitech Extreme 3D Pro** | em casa | Joystick de 3 eixos com acelerador. Substitui o joystick e o potenciômetro da lista de compras. |

**Anotar aqui quando souber:**
- o tamanho da mesa da impressora 3D (limita o tamanho de cada peça impressa);
- o tamanho da mesa da laser do colégio e quais materiais ela aceita;
- a potência da laser (diz se corta MDF de 6 mm ou só de 3 mm).

## Aparência

A referência são os painéis de avião, como o overhead do A320 e o MCP do Boeing: sóbrios, cinza escuro, legendas brancas e botões iluminados. O KSP entra nos detalhes.

- **Painel:** cinza escuro ou preto, fosco. Legendas brancas, em maiúsculas, com fonte sem serifa e sem acentos (como no LCD).
- **Cores das luzes, sempre com o mesmo significado:**

  | Cor | Significa | Exemplos |
  |---|---|---|
  | Verde | Sistema ligado, tudo normal | SAS, RCS, trem baixado |
  | Branco | Informação, modo escolhido | Modo do SAS, página da tela |
  | Âmbar | Atenção | Combustível baixo, script armado |
  | Vermelho | Perigo | ABORT, script abortado |

  Como nos LEDs dos módulos, **a luz mostra o estado do jogo**, nunca a posição da chave.
- **Zona de perigo:** o ABORT fica numa área com faixa zebrada amarela e preta, com capa de proteção vermelha. O STAGE e as chaves ARM também ficam debaixo de capas.
- **Seções bem separadas:** cada seção do painel tem o nome gravado em cima e uma linha em volta, como nos painéis de avião. Assim a mão acha a seção sem olhar.
- **Iluminação das legendas (ideia):** gravadas num acrílico pintado, as legendas deixam passar a luz de LEDs brancos por trás e acendem no escuro. Um knob de brilho no painel (um potenciômetro, ou PWM do Mega) regula todas juntas.

## Formato da caixa

Um console de mesa em cunha: a parte de baixo, perto das mãos, quase deitada; a de cima, com as telas, mais em pé.

```
 vista de cima (proposta inicial, sem medidas)

 ┌──────────────────────────────────────────────────────────────────┐
 │  TEMPO    │      TELA MULTIFUNÇÃO      │   TELEMETRIA (displays)  │  ← mais em pé
 ├───────────┴──────┬─────────────────────┼──────────────────────────┤
 │ SISTEMAS (korry) │ EDITOR DE MANOBRAS  │  ACTION GROUPS 1–10       │
 ├──────────────────┼─────────────────────┼──────────────────────────┤
 │ EVA   │ CÂMERA   │ NAVEGAÇÃO           │  AÇÃO EXECUTIVA           │  ← perto das mãos
 │       │          │                     │  STAGE, ABORT, ARM, EXEC  │
 └──────────────────┴─────────────────────┴──────────────────────────┘
                                                         ┌──────────┐
                                                         │ Extreme  │  joystick à direita,
                                                         │  3D Pro  │  fora da caixa
                                                         └──────────┘
```

- **Mão direita no joystick, mão esquerda no painel.** Por isso o que se aperta com pressa (STAGE, ABORT, ARM) fica embaixo, ao alcance da mão esquerda, e o que se mexe com calma (action groups, câmera) pode ficar mais longe.
- **Inclinação:** uns 15° na parte de baixo e 45° a 60° na parte das telas. Testar no protótipo de papelão antes de cortar.
- **Profundidade:** a caixa precisa de altura por dentro para os módulos, o backplane, o Mega, o Pi e os cabos flat. As chaves alavanca e os botões arcade ocupam uns 30 a 40 mm atrás do painel.
- **Tela do Pi:** a compra foi adiada, mas a caixa deixa um espaço para ela na parte de cima (ou o celular num suporte impresso, enquanto isso).

## Construção

### Um painel por seção

Cada seção do painel é **um painel frontal removível, com o seu módulo parafusado atrás**. Para tirar uma seção basta soltar os parafusos e o cabo flat. É a mesma ideia dos módulos do backplane, agora na caixa.

- **Painel frontal:** MDF ou acrílico de 3 mm, cortado e gravado a laser. Furos, legendas e linhas das seções saem no mesmo corte.
- **Módulo:** preso atrás do painel com espaçadores M3.
- **Fixação na caixa:** parafusos M3 em insertos roscados, colocados a quente em peças impressas, ou em porcas cativas. Parafuso direto no MDF espana depois de algumas desmontagens.
- **Tamanho padronizado (ideia):** painéis com a mesma largura e alturas múltiplas de uma medida, como os trilhos Dzus dos aviões (146 mm de largura). Assim um painel troca de lugar com outro, e seções novas cabem sem refazer a caixa.

### Estrutura

- **Paredes em MDF de 3 mm cortado a laser**, com encaixe dentado (*finger joint*), colado com cola branca. Geradores prontos: [boxes.py](https://boxes.hqs.de/) e [MakerCase](https://en.makercase.com/).
- Peças maiores que a mesa da laser são divididas e unidas por dentro com uma tala.
- **Traseira**, com os recortes:
  - entrada da fonte de 5 V (P4 ou borne) e uma chave liga/desliga;
  - passagem do cabo de rede do Pi (ou só um furo com passa-cabo);
  - extensão USB de painel para o joystick, que liga no Pi dentro da caixa;
  - ventilação para o Pi: grade de furos e uma ventoinha de 5 V e 40 mm.
- **Fundo removível**, para chegar no backplane sem desmontar o painel.
- **Pés de borracha** embaixo: a caixa não pode andar na mesa quando o ABORT é apertado com força.

### Acabamento

- **Protótipos:** MDF cru, sem pintura.
- **MDF definitivo:** lixar, passar primer e tinta spray fosca. A gravação a laser sobre a tinta deixa a legenda na cor do MDF, marrom, e não branca.
- **Legendas brancas:** acrílico preto gravado. A gravação fica branca fosca.
- **Legendas iluminadas:** acrílico branco leitoso pintado de preto por cima. A laser tira a tinta só nas letras, e a luz de trás passa por elas.
- **Segurança na laser:** MDF e acrílico podem; **PVC e vinil nunca**, porque soltam cloro, que é tóxico e corrói a máquina. Na dúvida sobre um material, perguntar no colégio antes.

### Peças impressas

- Korry switches (abaixo).
- Knobs dos encoders dos displays (eixo de 6 mm com lado chato), com um risco que marca a posição.
- Teclas basculantes do editor de manobras (como a do TIME WARP, com seta para cima e para baixo), uma cor ou forma por ajuste (PRO, NRM, RAD, TEMPO), para achar sem olhar. Podem ser uma tecla impressa sobre dois botões táteis, com uma mola que a traz de volta ao meio.
- Moldura da mikromedia e suporte do celular.
- Suportes das placas, do Mega e do Pi, com os furos no lugar certo.
- Passa-cabos e presilhas para os cabos flat.
- Berço do joystick (ver abaixo).

PLA serve para tudo. Peças que ficam perto do Pi ou de LEDs fortes podem amolecer com o calor; nesse caso, PETG.

### Medir antes de cortar

Cada chave, botão e encoder tem um diâmetro de rosca e uma espessura máxima de painel. Antes do painel de verdade:

1. Medir cada peça com paquímetro e anotar numa tabela aqui.
2. Cortar uma **plaquinha de teste** com um furo de cada tipo, em vários diâmetros (por exemplo 6,0 / 6,2 / 6,4 mm). A laser queima um pouco de material em volta do corte, e o furo sai maior que o desenho.
3. Conferir que a porca da chave alavanca e a trava do botão arcade prendem no painel de 3 mm.

## Korry switches

O **korry** é o botão iluminado quadrado dos aviões: a legenda fica no próprio botão e acende. Muitos têm a legenda dividida em duas metades, cada uma com a sua luz: em cima o sistema (`SAS`), embaixo um aviso (`OFF`, `FAULT`).

### Por que usar

O korry combina com o princípio do painel: **o botão só manda "apertei", e a luz mostra o estado do jogo.**

Com uma chave alavanca, a chave pode ficar para cima com o SAS desligado pelo jogo, e o piloto tem que olhar o LED para saber a verdade. O korry não tem posição: cada toque pede "troque o estado", e a legenda acesa é sempre o que o jogo diz. Não há como a chave e o jogo discordarem.

- **Bons candidatos:** tudo que o jogo também pode mudar sozinho, ou pelo teclado. SAS, RCS, luzes, freios, trem de pouso, action groups, modos do piloto automático de avião (HDG, ALT, V/S, SPD).
- **Continuam como chave alavanca com capa:** ARM e tudo que precisa de duas ações de propósito. STAGE e ABORT continuam como botões grandes, com capa.

### Como fazer

Korry de avião de verdade custa caro. Dá para fazer um bem parecido:

```
  vista em corte

   ┌─────────────────┐  ← tampa: acrílico leitoso 3 mm, cortado a laser,
   │   S A S         │    pintado de preto e com a legenda gravada
   │─────────────────│  ← divisória impressa: a luz de cima não vaza para baixo
   │    O F F        │
   ├─┬─────────────┬─┤
   │ │ LED   LED   │ │  ← um LED para cada metade da legenda
   │ │  ▲     ▲    │ │  ← corpo impresso, desliza para baixo quando apertado
   │ └──┬───────┬──┘ │
   │   [microswitch] │  ← botão tátil de 12 × 12 mm ou microswitch
   └─────────────────┘  ← base impressa, presa atrás do painel frontal
```

- **Corpo e base:** impressos em PLA preto, com uns 20 a 25 mm de lado. A base passa pelo furo quadrado do painel frontal e é presa por trás.
- **Tampa:** acrílico branco leitoso de 3 mm, cortado a laser. Duas opções de legenda:
  - pintar de preto e gravar a laser as letras, que ficam iluminadas;
  - deixar sem pintura e colar uma legenda impressa em transparência.
- **Divisória:** uma parede no meio do corpo impresso separa as duas metades da legenda.
- **Contato:** um botão tátil de 12 × 12 mm ou um microswitch. O clique dá a sensação de botão de avião.
- **LEDs:** dois LEDs de alto brilho de 3 mm, das cores da tabela de aparência. Atrás do acrílico, a luz perde força: testar o brilho no protótipo.

**Alternativa pronta:** botões quadrados iluminados de 16 mm, vendidos no AliExpress. São mais fáceis, mas têm uma luz só, de uma cor, e a legenda fica por conta própria.

### No painel e no firmware

- **Cada korry usa 1 entrada e 1 ou 2 LEDs** de um módulo. A legenda de duas metades gasta mais LEDs que entradas, o contrário das chaves: a tabela de seções do [README do hardware](README.md#qual-placa-e-qual-etiqueta-em-cada-seção) precisa ser revista quando for decidido quais chaves viram korry.
- **Brilho:** o resistor de 1 kΩ da placa dá uns 3 mA por LED. Atrás do acrílico pode ser pouco. Se for, trocar o resistor daquela saída por um menor, lembrando o limite de 70 mA por 74HC595.
- **Protocolo:** o korry manda um evento de botão (`BTN SAS 1`) em vez de chave (`SW SAS 1`), e a ponte inverte o estado no jogo. A mudança fica toda na ponte: o firmware já manda botões.

## Joystick: Logitech Extreme 3D Pro

O Extreme 3D Pro já está em casa e substitui o joystick de 3 eixos e o potenciômetro deslizante da lista de compras.

**O que ele tem:** 4 eixos (X, Y, torção do manche e uma alavanca de acelerador na base), 12 botões e um chapéu (*hat*) de 8 direções no topo. Liga por USB e o computador o vê como um joystick comum (HID).

### Como entra no projeto

**Ligado na USB do Pi e lido pela ponte**, que manda os comandos para o jogo pelo kRPC. O jogo não enxerga o joystick.

```
 Extreme 3D Pro ──USB──▶ Raspberry Pi (ponte) ──kRPC──▶ KSP
```

- **Por que assim:** o joystick passa pelo mesmo lugar que o painel. A ponte pode aplicar zona morta, curva de resposta e os modos (voo, câmera e translação), e sabe na hora quando o piloto mexe no manche. Isso é o que devolve o controle ao piloto quando um script está voando (ver a [base comum dos scripts](../README.md#base-comum)).
- **Sem abrir o joystick:** ele continua inteiro e pode voltar a ser usado em outros jogos.
- **Leitura:** pelo `pygame`, que a ponte já usa, ou pelo `evdev`, direto no Linux. Decidir quando for escrever o código.
- **Durante o desenvolvimento no PC:** com o joystick ligado no PC, o KSP também o lê. Deixar os eixos do joystick sem nada nas configurações de controle do KSP, senão os comandos chegam em dobro.
- **O Pi 4 tem 4 portas USB:** Mega, mikromedia e joystick cabem, e sobra uma.

### Um joystick, três modos

**Um joystick só**, sem um segundo para a translação: uma **chave de 3 posições no painel** (ON-OFF-ON, sem mola, 2 entradas) escolhe o que o manche faz. A ponte lê a chave e manda o manche para um lugar ou outro.

| Posição | Modo | O manche mexe em |
|---|---|---|
| Cima | **VOO** | A atitude da nave (ou do avião, pelo [fly by wire](../docs/fbw.md)) |
| Meio | **CÂMERA** | A câmera: a de voo, ou a do mapa quando ele está aberto. Substitui os botões de câmera provisórios do [editor de manobras](../docs/manobras.md#câmera-do-mapa-temporário) |
| Baixo | **TRANSLAÇÃO** | O RCS, para mover a nave sem girar: frente, trás, lados, cima e baixo. É o modo do acoplamento (no KSP, *docking mode*) |

Só uma proposta de mapeamento, para testar no jogo e mudar à vontade. O código fica para outra tarefa.

| Controle do joystick | VOO | CÂMERA | TRANSLAÇÃO (RCS) |
|---|---|---|---|
| Y (frente e trás) | Pitch | Inclina a câmera (cima e baixo) | Para cima e para baixo |
| X (lados) | Roll | Gira a câmera em volta do foco | Para os lados |
| Torção | Yaw | Aproxima e afasta (zoom) | Frente e trás |
| Alavanca da base | Acelerador | Acelerador | Acelerador |
| Chapéu | Olhar em volta, sem sair do modo | No mapa: troca o foco (nave, nó de manobra, planeta) | Olhar em volta |
| Gatilho | Segurar para mexer devagar (precisão) | Idem | Idem |
| Botão do polegar | Livre (a troca de modo foi para a chave) | Livre | Livre |
| Botões da base | Livres: action groups, trocar de nave | — | — |

- **Fora do modo VOO, a nave não recebe o manche:** a ponte manda pitch, roll e yaw zerados, e o SAS segura a atitude. No modo CÂMERA dá para olhar em volta com a nave parada no rumo.
- **A chave mostra o modo:** um LED por posição, ou o modo escrito na tela multifunção. Mudar de modo com o manche fora do centro não pode dar um tranco: a ponte só passa o manche para o modo novo depois que ele volta ao centro.
- **TRANSLAÇÃO pede o RCS ligado.** Se estiver desligado, a ponte avisa (LED do RCS piscando ou na tela); ligar sozinha fica a decidir.
- **STAGE e ABORT não vão no joystick:** ficam só no painel, debaixo das capas, para não serem apertados sem querer.
- **O botão MAPA** (liga e desliga o mapa) fica na seção da câmera do painel, junto da chave de modo.

### Acelerador

A alavanca da base do joystick é curta (uns 3 cm de curso). Serve para começar. Uma alavanca própria no painel, com curso longo, fica como ideia: um potenciômetro deslizante de 60 mm ou um quadrante de manete impresso em 3D, lido pelo módulo "Acelerador" do backplane. Se ela existir, a ponte usa a que se mexeu por último.

### Na mesa

O joystick fica à direita da caixa, solto na mesa. Se a base escorregar, um berço impresso em 3D, ou uma placa de MDF com recorte da base, prende o joystick ao lado do console.

## Arquivos

Quando os desenhos começarem, ficam em `hardware/caixa/`:

- o **arquivo-fonte** de cada peça, paramétrico, para mudar uma medida e gerar tudo de novo;
- os **SVG ou DXF** para a laser e os **STL ou 3MF** para a impressora, gerados a partir do fonte.

Ferramenta de CAD: **a decidir.** O OpenSCAD desenha a peça com código, em texto, e o histórico fica legível no git, como o resto do projeto. O FreeCAD e o Fusion desenham com o mouse, o que é mais fácil para formas livres.

## Ordem para fazer

1. **Protótipo de papelão**, na escala real, com os furos desenhados à mão. O objetivo é testar o alcance das mãos, a inclinação e o lugar do joystick.
2. **Um korry**, impresso e montado, ligado direto num pino do Mega como na [fase 2](../docs/fase2.md). Testar o brilho, o clique e a legenda.
3. **Plaquinha de teste na laser**, com os furos de cada peça, e a tabela de medidas preenchida.
4. **Um painel de seção de verdade**, por exemplo a ação executiva: gravado, com o módulo atrás e as capas no lugar.
5. **Caixa completa (fase 7)**, quando as seções e os módulos estiverem decididos.

## A decidir

- Quais chaves viram korry, e a revisão da tabela de seções por causa dos LEDs a mais.
- O que fazer com as seções "Analógicos: rotação" e "Analógicos: translação" do backplane. Não vai ter segundo joystick: o Extreme 3D Pro faz rotação, câmera e translação pela chave de modo. Podem ficar só com botões e LEDs (a chave de modo do joystick, por exemplo) ou sair.
- Em que seção fica a chave de modo do joystick: na da câmera, junto do MAPA, ou numa das analógicas.
- Alavanca de acelerador própria ou só a do joystick.
- Ferramenta de CAD.
- MDF pintado ou acrílico nos painéis definitivos, e se as legendas serão iluminadas.
