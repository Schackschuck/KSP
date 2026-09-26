# Tela multifunção: simulador e navball

**Pronto quando:** a navball da janela acompanha a do jogo, os números batem com os do KSP e os botões de toque ligam e desligam o SAS e o RCS.

A mikromedia for ARM ainda não tem firmware: é a fase 6 do [roteiro](../README.md#fase-6--tela-multifunção-mikromedia-for-arm). Enquanto isso, a tela roda num **simulador**, uma janela de 320x240 no PC que fala exatamente o protocolo que a placa vai falar. A ponte (`mfd.py`) não sabe se do outro lado está o simulador ou a placa. Quando o firmware existir, basta trocar a janela pela porta serial, e o simulador vira a referência do que o firmware tem que desenhar.

![O simulador no modo SUP perto do chão: navball com o pró-grado em amarelo e o alvo em roxo, e à direita RADAR, velocidades e botões de toque](img/mfd_simulador.png)

## O que já se sabe da placa

- Ela tem **duas mini-USB**:
  - **USB** vai direto no LPC2148. Alimenta a placa e roda o demo de fábrica.
  - **PROG** tem um **FT232RL**, um conversor USB-serial. É por ela que o PC vai conversar com a placa, como uma porta COM comum, igual ao Mega. O firmware não precisa implementar USB.
- No primeiro teste, a PROG alimentou a placa, mas o Windows mostrou "Dispositivo USB desconhecido (falha na solicitação do descritor)". A suspeita é o cabo mini-USB, que é antigo e falha nos fios de dados.
  - Com um cabo bom, deve aparecer **USB Serial Port (COMx)** em *Portas (COM e LPT)*.
  - Se aparecer **FT232R USB UART** em *Outros dispositivos*, falta o driver VCP da FTDI (ftdichip.com → Drivers → VCP).
- **Ainda falta** o manual e o esquemático, no site da MikroE. Eles dizem qual é o controlador da tela, em que pinos estão a tela e o touch, e como gravar programas.

## Onde está o código

| Arquivo | O que é |
|---|---|
| [`bridge/mfd.py`](../bridge/mfd.py) | A ponte kRPC ⇄ tela: lê o jogo, manda as mensagens e executa os toques |
| [`bridge/mfd_simulador.py`](../bridge/mfd_simulador.py) | O simulador: faz o papel do firmware da mikromedia |
| [`bridge/navball.py`](../bridge/navball.py) | A conta da navball, escrita para ser passada para C |
| [`docs/protocolo.md`](protocolo.md#tela-multifunção-mikromedia) | O protocolo da tela, mensagem por mensagem |

## Instalar

No PC, além do que a ponte do painel já usa:

```
pip install krpc pyserial pygame-ce numpy
```

O **pygame-ce** é a versão do pygame mantida pela comunidade, e o código usa do mesmo jeito (`import pygame`). O pygame original não tem pacote para o Python 3.14. Não instale os dois juntos: se o pygame original já estiver instalado, rode `pip uninstall pygame` antes.

## O que a tela mostra

- **Navball:** o "W" laranja no centro é para onde o nariz aponta. Em amarelo, o pró-grado (para onde a nave vai) e o retrógrado. Em roxo, o alvo e o anti-alvo, quando há um alvo escolhido no jogo.
- **Altitude:** `ALT` acima do nível do mar. Abaixo de 5 km do chão vira `RADAR`, a altura acima do chão ou do mar; volta para `ALT` acima de 5,5 km.
- **Velocidade e o resto dependem do modo**, escrito no botão `MODO` e ao lado de `VEL`:

  | Modo | Velocidade e pró-grado em relação a | Mostra também |
  |---|---|---|
  | `SUP` | Superfície | `V VERT` (negativa descendo) e `V HOR` |
  | `ORB` | Órbita | `AP` e `PE` |
  | `ALVO` | Alvo | `DIST`, a distância até o alvo |

- **O modo troca sozinho, como no KSP:** vai para `ORB` acima de 36 km e volta para `SUP` abaixo de 33 km, em Kerbin. Em outros planetas, 6% e 5,5% do raio. Escolher ou trocar o alvo no jogo leva para `ALVO`, e tirar o alvo volta para `SUP` ou `ORB`. Tocar em `MODO` passa para o próximo; a escolha vale até a próxima troca automática.
- **SAS e RCS:** verde quando o sistema está ligado **no jogo**. Tocar liga ou desliga.

## Testar sem o KSP

```
cd bridge
python mfd.py --demo
```

A nave de mentira desce até perto do chão e sobe até 55 km a cada 2 minutos, e a cada minuto ganha um alvo por 30 segundos.

| Você faz | Resultado esperado |
|---|---|
| Roda o comando | A janela abre. A navball gira devagar, sobe, desce e rola, e os números mudam. O marcador amarelo acompanha o nariz com um pouco de atraso. |
| Espera | `ALT` vira `RADAR` perto do chão. O modo passa sozinho para `ORB` acima de 36 km e volta para `SUP` abaixo de 33 km. Quando o alvo aparece, vai para `ALVO`, com `DIST` e os marcadores roxos; quando o alvo some, volta. O terminal mostra cada troca. |
| Clica em **SAS** | O terminal mostra `SAS: ligar` e o botão fica verde. Outro clique apaga. |
| Clica em **RCS** | Igual ao SAS |
| Clica em **MODO** | Passa para o próximo modo. `ALVO` só entra na roda enquanto há alvo. |
| Clica fora dos botões | Nada acontece |
| Fecha a janela | O programa termina |

Janela pequena? `python mfd.py --demo --zoom 3`.

## Testar com o KSP

Com o jogo na cena de voo e o servidor kRPC iniciado:

```
cd bridge
python mfd.py
```

A ponte do painel (`ponte.py`) pode rodar ao mesmo tempo, em outro terminal: o kRPC aceita as duas conexões.

**Pronto quando:**

- [x] Na plataforma, a navball da janela fica igual à do jogo: o centro no azul, olhando para cima.
- [x] **Pitch** (W/S), **yaw** (A/D) e **roll** (Q/E): a navball da janela gira igual à do jogo, e o `RUMO` bate com o rumo do jogo.
- [x] O pró-grado da janela fica no mesmo lugar que o do jogo.
- [x] **SAS** e **RCS:** tocar o botão liga e desliga no jogo, e as teclas **T** e **R** mudam a cor do botão.
- [x] Voltar ao KSC mostra `SEM SINAL`. Lançar outra nave faz a tela voltar sozinha.
- [ ] Na plataforma e no pouso, a tela mostra `RADAR`, igual ao altímetro do jogo no modo radar. Acima de 5,5 km volta para `ALT`.
- [ ] Na subida, o modo passa sozinho para `ORB` perto dos 36 km, junto com a navball do jogo. Na descida, volta para `SUP` perto dos 33 km. `AP` e `PE` só aparecem em `ORB` e batem com o mapa (tecla **M**).
- [ ] Em `SUP`, `V VERT` fica negativa descendo e positiva subindo.
- [ ] **Alvo:** escolher uma nave ou um planeta como alvo leva a tela para `ALVO`. Os marcadores roxos ficam no mesmo lugar que os do jogo, e `VEL` e `DIST` batem com os do jogo no modo *Target*. Tirar o alvo volta para `SUP` ou `ORB`.
- [ ] **MODO:** tocar passa por `SUP`, `ORB` e `ALVO` (só com alvo).

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `No module named 'pygame'` (ou `numpy`) | Faltou instalar | `pip install pygame-ce numpy` |
| O `pip install pygame` falha dizendo que não há versão para o Python 3.14 | O pygame original parou no Python 3.13 | Instalar o `pygame-ce` no lugar |
| Fica parado em `Conectando ao kRPC...` | O jogo está esperando você aceitar a conexão | Aceitar na janela do kRPC, dentro do jogo |
| Tocar em SAS não deixa o botão verde | A nave não tem SAS (sem piloto nem núcleo de sonda com SAS) | É o comportamento certo: o botão mostra o jogo |
| `SEM SINAL` com o foguete voando | A ponte parou, ou o terminal mostra `Nenhuma nave ativa` | Ver a mensagem no terminal |
| `DIST`, `AP` ou `PE` mostram `---` longe de casa | A distância passou de 2,1 milhões de km, o limite de um inteiro de 32 bits | Normal com planetas distantes |

## Como a navball é desenhada

A conta está em [`navball.py`](../bridge/navball.py), escrita para caber num ARM7 a 60 MHz sem ponto flutuante, e sem memória para guardar a tela inteira (320x240x2 = 150 KB contra 32 KB de RAM).

1. **Uma vez por quadro:** os três ângulos viram os eixos da nave no mundo (frente, direita e cima). São os únicos senos e cossenos do quadro, 6 consultas a uma tabela.
2. **Para cada ponto da bola:**
   - A posição (x, y) na bola tem uma altura z = √(1 − x² − y²), que depende só da posição e fica numa tabela.
   - A direção do mundo que o ponto mostra é `x·direita + y·cima + z·frente`: 9 multiplicações.
   - **Céu ou chão:** o sinal do componente vertical.
   - **Linhas de pitch:** a latitude é o arco-seno do componente vertical, lido de uma tabela.
   - **Meridianos:** o meridiano de cada rumo fica num plano vertical, e a distância do ponto ao plano sai de um produto escalar, sem arco-tangente. São 2 multiplicações por plano, com 6 planos.
   - **Sombra e cor:** escurece a borda e arredonda para 16 bits por ponto (RGB565).
3. **Marcadores e letras:** cada um é um vetor projetado na bola por 3 produtos escalares, e só aparece se estiver na metade visível.

São cerca de 31 mil pontos por quadro, cada um com umas 30 operações de inteiros. Na placa, a bola vai ser desenhada linha a linha, direto na memória do controlador da tela. Os números só são redesenhados quando mudam. A velocidade de verdade só dá para saber medindo na placa.

## Próximos passos

1. **Cabo mini-USB novo** para a PROG virar uma porta COM.
2. **Manual e esquemático** da mikromedia for ARM, no site da MikroE: controlador e pinos da tela e do touch, e como gravar. Pode ser pelo bootloader serial do LPC2148, pela PROG, com o Flash Magic ou o `lpc21isp`; ou pelo bootloader USB da MikroE, pela outra porta. **Antes de gravar qualquer coisa**, baixar o `.hex` do demo de fábrica, se estiver disponível: gravar um programa novo apaga o demo.
3. **Firmware, fase 6:** piscar um LED, depois a serial (eco, e em seguida este protocolo), depois a tela (pintar, texto), a navball e o touch. Quando a placa responder `READY`, rodar `python mfd.py --porta COMx`.
