# Scripts de voo

Scripts que pilotam a nave, ou ajudam o piloto a pilotar, disparados pelo painel e acompanhados na tela. O primeiro é o pouso autônomo da [fase 5](roteiro.md#fase-5--protocolo-v1--scripts-de-voo) ([`scripts/pouso.py`](../scripts/pouso.py)); o segundo, o [fly by wire de avião](#fly-by-wire-de-avião) ([`scripts/fbw.py`](../scripts/fbw.py)); o terceiro, a [subida até a órbita](#subida-até-a-órbita) ([`scripts/subida.py`](../scripts/subida.py)); o quarto, o [rendezvous](#rendezvous) ([`scripts/rendezvous.py`](../scripts/rendezvous.py)). Os outros desta seção são ideias ainda sem código e sem ordem: cada um entra no roteiro quando o hardware de que precisa existir.

Os scripts ficam em [`scripts/`](../scripts/), fora da ponte: cada um roda sozinho pela linha de comando, no PC ou no Pi, mesmo sem o painel. No cockpit, a ponte só dispara o script pelo botão e mostra o estado dele no painel e na tela. Os testes, com naves simuladas e sem o KSP, ficam em `scripts/tests/`.

## Base comum

- **Um script ativo por vez.** No cockpit, liga segurando o korry do script 5 s, e segurar de novo 5 s aborta. ABORT, ou mexer no joystick, também devolve o controle ao piloto na hora (a fazer).
- O painel e a tela mostram o estado do script (armado, ativo, terminado, abortado). Como nos outros LEDs, o LED mostra o que o script está fazendo, não o botão que foi apertado.
- **Guiagem separada do kRPC**, como em `pouso.py`: recebe uma leitura da nave e devolve comandos. Assim ela é testada numa nave simulada, sem o KSP, antes de ir para o jogo.
- **Diretor de voo:** todo script pode rodar no automático ou só como guia. No modo guia, a tela mostra para onde apontar e quanto acelerar, e o piloto voa pelo joystick. Serve para testar a guiagem sem entregar a nave e para aprender a pilotar junto.

## Fly by wire de avião

**Status: script escrito e testado num avião simulado; falta testar no jogo.** Roteiro de testes, ajuste dos ganhos e problemas comuns em [docs/fbw.md](fbw.md).

Como nos caças, o manche não mexe nas superfícies: ele pede o que o avião deve fazer, e o FBW decide as superfícies. [`scripts/fbw.py`](../scripts/fbw.py) lê o joystick (o Extreme 3D Pro, ou um controle de Xbox) e pilota o avião pelo kRPC.

- **O manche:** para trás e para a frente pede carga, de −1 g a 4 g; solto, 1 g, e o caminho não curva. Para os lados pede velocidade de rolagem, até 90°/s; solto, a inclinação fica onde parou. A torção soma ao leme. O FBW não trava a altitude sozinho: numa curva, o piloto puxa.
- **Proteções:** com o manche, só a carga até 4 g: puxando tudo devagar, o avião estola. No piloto automático e na trava, ângulo de ataque entre −8° e 15°, asas até 60° e subida entre −30° e +30°.
- **Aviso de estol:** com o ângulo de ataque perto dos 15°, a luz ESTOL do painel pisca e a tela toca um alarme. É só aviso: o FBW não mexe no acelerador, no piloto automático, na trava nem no manche.
- **Nada liga sozinho:** os modos do piloto automático e a trava só ligam pelo painel.
- **Lei direta** no chão e com o botão do FBW desligado: o manche vai direto para as superfícies. O FBW assume 1 s depois da decolagem.
- **Sem joystick** (`--sem-joystick`): decola pelo teclado do jogo, na lei direta, e no ar o piloto automático voa pelo painel.
- **O acelerador fica com o piloto.** O acelerador automático (SPD) já existe por dentro, ainda sem interface.
- **Na tela:** com o piloto automático ou a trava, o caminho pedido aparece na navball da [tela multifunção](mfd.md), como os quatro cantos verdes de um quadrado. Com o avião nele, o pró-grado fica dentro do quadrado.
- **Por dentro, duas camadas:** a carga e a rolagem pedidas viram velocidades de giro; os giros viram superfícies, com proporcional e integral e o ganho dividido pela autoridade do avião.

**Pronto quando:** um avião decola na lei direta e, com o FBW, responde ao manche na hora, sem balançar: puxar dá carga, rolar dá rolagem, e soltar segura o que estava.

**Anotado depois dos primeiros voos no jogo** (a fazer):

- [x] **O FBW está muito instável no jogo.** O voo gravado mostrou o nariz oscilando a 1,5 vez por segundo (ganho de pitch alto para o atraso do kRPC) e um avião lento e "interventor". Refeito com a lei de caça e ganhos menores, testados com a leitura atrasada ([docs/fbw.md](fbw.md)). Falta confirmar no jogo.
- [ ] **Não ligar o FBW sozinho na decolagem.** Hoje ele assume 1 s depois de sair do chão; passa a começar desligado e só liga pelo korry FBW (ou pelo botão do joystick).
- [x] **Tirar a recuperação automática do estol**, que só deu problema no jogo. Saiu tudo: o acelerador no máximo, o piloto automático e a trava desligando, o nariz para baixo, a trava ligando sozinha depois e o limite de ângulo de ataque no manche. Fica só o aviso (luz ESTOL e alarme).
- [x] **Os modos do piloto automático ligavam sozinhos** ao ligar o FBW (o avião tentava subir para uma altitude): era a trava de altitude automática, que saiu. Falta confirmar no jogo.
- [ ] **Avisar o estol também fora do FBW** (na lei direta): a luz ESTOL e o alarme pelo ângulo de ataque, mesmo sem o FBW voando.

## Avisos de voo (GPWS)

**Status: código escrito e testado sem o jogo; falta ouvir no Pi e voar.** Roteiro, limites e como ligar o alto-falante em [docs/avisos.md](avisos.md).

Como o GPWS dos aviões de linha, a ponte da tela fala os avisos em inglês, num alto-falante USB ligado no Pi, em qualquer nave voando na atmosfera:

- **Vermelhos:** `PULL UP` (descendo rápido demais para a altura) e `TERRAIN` (o chão chegando rápido; vira `PULL UP` se continuar).
- **Âmbar:** `SINK RATE`, `DON'T SINK` (perdendo altura depois da decolagem), `TOO LOW, GEAR` e `TOO LOW, TERRAIN` (baixo com o trem recolhido), `BANK ANGLE` e `OVERSPEED`.
- **Chamadas de altura** no pouso: 100, 50, 40, 30, 20 e 10 pés.
- **Luz** GPWS (âmbar) / PULL UP (vermelha) no painel de sistemas; por enquanto, na página de botões.

- [x] `bridge/avisos.py`: os avisos, a prioridade e a voz (`espeak-ng` ou gravações em `bridge/sons/`); `--voz`, `--sem-voz` e `--testar-voz` no `mfd.py`; testes.
- [x] Luz GPWS / PULL UP na página de botões.
- [ ] Ouvir no Pi com o alto-falante USB e ajustar os limites no jogo.
- [ ] Luz GPWS no desenho do painel de sistemas.
- [ ] Olhar o terreno à frente (EGPWS), pela altura do terreno do kRPC.

## Piloto automático de avião

**Status: código escrito e testado com o avião simulado e a demonstração; falta testar no jogo.** O `fbw.py` voa HDG, ALT e V/S pedindo um caminho ao FBW ([docs/fbw.md](fbw.md#piloto-automático)), e o painel de sistemas é, por enquanto, uma página de botões aberta pela ponte da tela ([docs/mfd.md](mfd.md#painel-de-sistemas-de-controle)), com a roda do SAS e a página do piloto na tela.

- [x] Página de botões no celular, no lugar do painel, como a do editor de manobras.
- [x] Ponte da tela (`bridge/mfd.py` e `bridge/sistemas.py`): modos do SAS, SAS e RCS no jogo; azul ou verde pelo erro até o marcador; o menu do piloto; as páginas do SAS e do piloto, com a volta à navball.
- [x] Tela do celular e simulador: a roda dos modos do SAS e a página do piloto.
- [x] `scripts/fbw.py`: HDG, ALT e V/S pedindo um caminho; FBW e TRAVA pelo painel; estado e comandos por UDP com a ponte da tela; testes no avião simulado.
- [ ] Testar no jogo: os modos do SAS e as luzes ([roteiro](mfd.md#testar-o-painel-sem-o-ksp)), e o piloto automático num avião ([roteiro](fbw.md#piloto-automático)).
- [ ] **Tela: tirar os botões redondos SAS e RCS da navball.** Eles ficam só no painel.
- [ ] **Tela: as páginas que abrem sozinhas** (a roda do SAS, a do piloto e as outras que aparecem por cima da navball) **ficam 6 s** depois do último toque, em vez de 10 s.
- [ ] O painel de verdade: as mesmas linhas pela serial do Mega, e as pontes do painel e da tela juntas.

Inspirado no painel de piloto automático dos aviões de linha (o MCP do Boeing, o FCU do Airbus).

- **Modos:**
  - **HDG:** vira para o rumo escolhido e segura.
  - **ALT:** sobe ou desce até a altitude escolhida e segura. Enquanto não chega, fica **armado** (azul na tela); ao chegar, nivela e fica verde.
  - **V/S:** sobe ou desce com a velocidade vertical escolhida. Com o ALT ligado junto, nivela ao chegar na altitude escolhida.
  - **SPD:** acelerador automático, segura a velocidade escolhida. Fica para depois, como mais uma linha do menu.
  - Sem HDG ligado, a rolagem fica com o manche, e a inclinação fica onde o piloto deixou.
- **No painel de [sistemas de controle](../hardware/construcao.md#painel-de-sistemas-de-controle)**, junto do SAS, do RCS e do FBW:
  - **Um encoder só**, o AJUSTE, que também mexe nas outras páginas da tela, mexido pelo menu da página do piloto na tela multifunção: girar move o cursor entre HDG, ALT e V/S; apertar escolhe a linha, e girar muda o valor (horário soma); apertar de novo sai; segurar 1 s liga ou desliga o modo da linha. Girando devagar, o valor muda de 1 em 1 (1°, 10 m, 0,1 m/s); rápido, de 10 em 10.
  - **Uma luz verde por modo**, ao lado do encoder, acesa quando o modo está ligado no FBW. Sem displays de 7 segmentos: os valores ficam na tela.
  - Korry **FBW** (liga e desliga o FBW, como o botão do joystick) e **TRAVA ALT** (trava e destrava a altitude do momento).
- **Na tela:** a página do piloto, com os modos (azul armado, verde ligado) e os valores escolhidos, abre sozinha quando o encoder é mexido e volta para a navball uns 10 s depois. O caminho pedido aparece na navball: é o ponto verde do FBW.
- **Por dentro:** o piloto automático fica por cima do [fly by wire](#fly-by-wire-de-avião) e pede um caminho, como um piloto que não cansa:
  - HDG pede o rumo escolhido, que vira inclinação das asas; sem HDG, a rolagem fica com o manche;
  - ALT, V/S e a TRAVA ALT pedem o ângulo de subida, que vira carga; sem eles, o pitch fica com o manche;
  - SPD liga o acelerador automático que já existe no `fbw.py`;
  - as proteções do FBW continuam valendo, e mexer no manche devolve o eixo ao piloto.
- **Precisa de:** o encoder e as luzes do VOO. Para começar, uma página de botões no celular faz o papel do painel.

**Pronto quando:** um avião decola na mão, e o piloto automático leva ele até a altitude e o rumo escolhidos no painel e segura lá.

## Rover com controle de cruzeiro

- Os mesmos botões e encoders HDG e SPD do avião, e o mesmo PID: segura a velocidade e o rumo no chão, pelo acelerador e pela direção das rodas (`control.wheel_throttle` e `control.wheel_steering`).
- Freia nas descidas, para não passar da velocidade escolhida.
- Sai quase de graça depois do piloto automático de avião.

## Subida até a órbita

**Status: voou no jogo em 20/10/2026 e chegou em órbita sozinho, com um foguete de 552 t, a 80 e a 100 km; o giro está em ajuste.** [`scripts/subida.py`](../scripts/subida.py) leva a nave da plataforma até uma órbita circular, em qualquer planeta, com ar ou sem. Como funciona, as contas e o roteiro de teste no jogo estão em [docs/subida.md](subida.md).

- **O piloto escolhe** a altitude, a inclinação e, se quiser, o plano do alvo escolhido no jogo, na página SUBIDA da tela multifunção, por um encoder. Segura o korry LANCAR 5 s, e o script voa.
- **O rumo** desconta a rotação do planeta e é refeito a cada passo, pela velocidade que ainda falta. A inclinação final sai a menos de 0,1° da pedida.
- **O giro** da curva de gravidade é escolhido por simulação: antes de inclinar, o script simula a subida inteira com 16 giros e fica com o de menor Δv, somando a subida e a circularização. Depois, a cada 5 s, ele simula de novo o resto da subida e corrige o nariz em até 4°, em malha fechada.
- **Com o plano de um alvo**, o script espera a janela de lançamento, com time warp, e no fim iguala o plano numa queima na linha dos nós.
- **Os estágios** saem sozinhos; o corte é no apoastro pedido, e a circularização, em malha fechada, centrada no apoastro. O próprio script queima: o EXEC ainda não existe.
- Junto com o pouso, fecha o ciclo: do chão até a órbita e de volta.

- [x] `scripts/subida.py`: a guiagem, a simulação do giro, a janela, o kRPC, o `--demo` e as linhas `SUB`; testes em `scripts/tests/test_subida.py`, numa nave simulada em Kerbin e na Mun.
- [x] Ponte da tela: o korry LANCAR, o menu da subida (`ENC SUB`, `BTN SUB`) e a página SUBIDA; na página de botões, o LANCAR e um encoder para a configuração.
- [x] A página SUBIDA na mikromedia e no navegador (o celular e o tablet): a configuração e o voo. O simulador mostra a navball no lugar dela.
- [ ] O desenho do voo na página SUBIDA: o KSC na decolagem, a parábola na subida e a órbita na circularização, com dois zooms. No navegador, testado com o `--demo`; na placa, falta gravar. Falta ver num lançamento. Depois, a visão oblíqua do planeta na órbita.
- [ ] Testar no jogo ([roteiro](subida.md#testar-no-jogo)): primeiro 80 km e 0°, depois a inclinação, o plano de um alvo e a Mun.
- [x] A configuração pelo encoder AJUSTE, no Uno, com a página SUBIDA aberta ([docs/encoder.md](encoder.md#na-ponte-da-tela)).
- [ ] Depois: a guiagem do vácuo (PEG), mais eficiente que seguir o pró-grado.
- [ ] Depois: lançar na hora certa para o rendezvous. Além de esperar o plano do alvo, o script esperaria a **fase**: decolar quando o alvo estiver no ângulo certo à frente, para a subida terminar logo atrás dele, e o rendezvous virar só a aproximação final. Na Estação um (quase equatorial, ~37 min de volta), o alvo passa por cima do KSC a cada ~41 min, então a espera é curta. No primeiro voo completo (21/10/2026), a subida sem essa espera terminou a 576 km da estação, e o rendezvous previu 89,6 m/s e 5 h até o encontro.

## Pouso de precisão (volta à base)

O pouso da SpaceX completo. O `pouso.py` desce na vertical onde a nave estiver; aqui o booster volta para um lugar escolhido, como a plataforma do KSC.

- **Queima de retorno** logo depois da separação: vira a nave e queima até a trajetória cair no alvo.
- **Queima de reentrada**, para chegar mais devagar nas camadas grossas da atmosfera.
- Na descida, as aletas corrigem a trajetória para o alvo.
- Termina com a queima de suicídio do `pouso.py`, com a mira puxando para o alvo em vez de só anular a deriva.
- É o mais difícil da lista: precisa prever onde a trajetória cai, com arrasto, como o `pouso.py` já faz na vertical.

## Rendezvous

**Status: voou no jogo em 21/10/2026, de 100 km até 111 m da Estação um, com 98,3 m/s gastos (89,6 previstos); a aproximação com RCS de translação também foi testada no jogo.** [`scripts/rendezvous.py`](../scripts/rendezvous.py) leva a nave até 100 m de outra em órbita do mesmo planeta, parada em relação a ela. Como funciona, as contas e o roteiro de teste no jogo estão em [docs/rendezvous.md](rendezvous.md).

**O script queima sozinho**, porque o EXEC da fase 5 ainda não existe. O nó que ele cria no jogo é só para mostrar: no mapa, o KSP desenha a aproximação, e o piloto confere o plano. Com `--so-planejar`, o script só cria o nó, imprime o plano e sai.

- **As etapas:**
  1. **Igualar o plano:** só se a inclinação relativa passa de 0,05°. Queima na direção normal, no nodo relativo, de Δv = 2·v·sen(Δi/2).
  2. **Transferência:** a conta pesada. Uma busca com tiro (shooting): para cada momento de queima e tempo de voo, um palpite tangencial e um Newton em 3D acertam a queima para a nave passar 300 m acima do alvo. O momento da queima varre o período sinódico, e o custo é o Δv da queima mais a velocidade relativa no encontro. Serve também quando a nave já está na altitude do alvo, onde uma Hohmann dá 0 m/s. Sem motor, as órbitas seguem Kepler: a previsão é exata.
  3. **Correções** no meio do caminho: o mesmo tiro, a partir do estado de agora, em frações de volta antes do encontro.
  4. **Igualar a velocidade:** no momento da menor distância, com a queima igual à diferença entre a velocidade do alvo e a da nave.
  5. **Aproximação final**, sem nó: aponta para o alvo e vai pelo RCS de translação, sem virar a nave, a até 2 m/s, freando só no fim, e para a uns 100 m. Sem RCS, vai pelo motor. Dali segue o acoplamento assistido.
- **Automático ou diretor de voo:** o script encadeia as etapas e acelera o tempo entre elas (`warp_to`). O modo diretor de voo, em que ele só propõe cada nó e o piloto queima, fica para depois.
- **Na página do editor de manobras, na tela multifunção:** a menor distância prevista até o alvo, quando ela acontece e a velocidade relativa nesse ponto, atualizadas enquanto o encoder e o TEMPO mexem no nó.
- **Ordem para fazer**, do mais simples ao mais difícil:
  1. [ ] Só mostrar a menor distância prevista enquanto o piloto edita os nós na mão. Sem automação, e já é como se faz rendezvous "de olho" no KSP.
  2. [x] Os nós de igualar o plano e igualar a velocidade e a busca da transferência, numa etapa só, para o script já fechar o voo. Testado em voos simulados.
  3. [x] A aproximação final, que já entrou junto. Falta a passagem para o acoplamento.
  4. [x] O plano conferido no jogo (`--so-planejar`, 21/10/2026): 99,5 m/s previstos de 100 km até a Estação um.
  5. [x] O voo completo no jogo ([roteiro](rendezvous.md#testar-no-jogo)), 21/10/2026: 111 m e 0,20 m/s no fim, 98,3 m/s e 117 de monopropelente gastos.
  6. [x] A aproximação com o RCS de translação, sem virar a nave, e com a curva de frenagem até 2 m/s. Testada no jogo em 21/10/2026: de 1,3 km a 59 m, parada a 0,19 m/s. O RCS só fica ligado nela; no resto do voo, quem vira a nave é a roda de reação.
  7. [ ] De longe (mais de ~1 km), trocar a reta por um tiro de Kepler: seguir a reta contra a órbita gasta ~2 m/s de RCS a cada 100 m.
- **Decidido:**
  - Quem prevê as órbitas: uma previsão própria, com a equação de Kepler (as funções f e g), rápida e testável sem o KSP. Com o kRPC, cada pergunta vai pela rede, e a busca faz milhares. O `--so-planejar` confere a menor distância da previsão própria contra a do kRPC.
  - Queimas longas: começam metade da duração antes do nó, senão o encontro erra por quilômetros, e seguem o Δv que ainda falta, como o KSP. Como o script queima sozinho, a regra está nele; o EXEC, quando existir, usa a mesma.
- **Precisa de:** só do kRPC e de uma nave com motor aceso; roda pela linha de comando, sem o painel. A etapa 1 da ordem precisa da tela. O EXEC e o editor de manobras só entram no modo diretor de voo.

## Acoplamento assistido

- Página nova na tela multifunção: a mira de alinhamento com a porta de acoplamento do alvo, a distância e a velocidade de aproximação.
- O sidestick no modo TRANSLAÇÃO, escolhido pelo botão do manche: o manche move a nave com o RCS, sem girar ([os três modos](../hardware/construcao.md#um-joystick-três-modos)).
- Primeiro manual, com a tela ajudando. Depois automático: a nave se alinha e se aproxima devagar sozinha.
- **Precisa de:** joystick (fase 2) e a tela multifunção.
