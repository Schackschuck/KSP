# Tela multifunção: navball, simulador e celular

**Pronto quando:** a navball da tela acompanha a do jogo, os números batem com os do KSP e os botões de toque ligam e desligam o SAS e o RCS.

A tela multifunção mostra uma navball no estilo do KSP2, velocidade, altitude, acelerador, velocidade vertical e os dados da órbita ou do alvo, com botões de toque. Ela mora na mikromedia for ARM, a fase 6 do [roteiro](../README.md#fase-6--tela-multifunção-mikromedia-for-arm), com o firmware de `firmware/mfd/`: gravar e ligar em [mikromedia.md](mikromedia.md). A mesma tela roda também no PC e no celular, e os três falam o mesmo [protocolo](protocolo.md#tela-multifunção-mikromedia):

```
 KSP + kRPC (PC)
      │ streams do kRPC
      ▼
 bridge/mfd.py: a ponte. Lê o jogo, escolhe o modo da navball,
      │         manda as mensagens e executa os toques
      │ protocolo em texto, uma mensagem por linha
      ├─────────────────────┬──────────────────────────┐
      ▼                     ▼                          ▼
 simulador             celular, pelo Wi-Fi         mikromedia, pela serial
 mfd_simulador.py      mfd_celular.py e            firmware/mfd/
 janela no PC          celular/index.html          (mikromedia.md)
 (padrão)              (--celular)                 (--porta COMx)
```

A ponte não sabe qual tela está do outro lado: para usar a placa, basta trocar a janela pela porta serial. O **simulador** desenha ponto a ponto na resolução da placa (320x240, 16 bits por ponto) e é a referência do que o firmware tem que desenhar. A **página do celular** segue as mesmas posições, só que na resolução do celular.

**Onde estamos:**

- Testado com o jogo: navball (pitch, yaw e roll), pró-grado, SAS e RCS pelo toque, e a volta automática ao trocar de nave. Estão marcados na lista de [Testar com o KSP](#testar-com-o-ksp).
- Ainda sem teste com o jogo: radar, troca automática de modo, modo ALVO, normal e radial, nó de manobra, acelerador, tempos até AP e PE, e os números na bola.
- Ainda sem teste num celular de verdade: a página foi testada num navegador simulando um celular.
- O firmware da placa está pronto e conferido no PC contra o simulador, mas ainda não rodou na placa: [mikromedia.md](mikromedia.md).

![O simulador em órbita: navball no centro com os números do rumo e do pitch e os marcadores, velocidade e altitude nas laterais, acelerador e velocidade vertical nas bordas, AP e PE embaixo](img/mfd_simulador.png)

## O que já se sabe da placa

- Ela tem **duas mini-USB**:
  - **USB** vai direto no LPC2148. Alimenta a placa e rodava o demo de fábrica.
  - **PROG** tem um **FT232RL**, um conversor USB-serial. É por ela que o PC conversa com a placa, como uma porta COM comum, igual ao Mega, e é por ela que o Flash Magic grava o firmware. O firmware não precisa implementar USB.
- No primeiro teste, a PROG alimentou a placa, mas o Windows mostrou "Dispositivo USB desconhecido (falha na solicitação do descritor)". O cabo mini-USB era antigo e falhava nos fios de dados.
- O manual e o esquemático deram os pinos da tela e do touch, a gravação pela PROG e o módulo da tela (MI0283QT2). Estão resumidos em [mikromedia.md](mikromedia.md#como-o-firmware-funciona).

## Onde está o código

| Arquivo | O que é |
|---|---|
| [`bridge/mfd.py`](../bridge/mfd.py) | A ponte kRPC ⇄ tela: lê o jogo, manda as mensagens e executa os toques; repassa o ponto do [fly by wire](fbw.md) |
| [`bridge/mfd_simulador.py`](../bridge/mfd_simulador.py) | O simulador: faz o papel do firmware da mikromedia |
| [`bridge/mfd_celular.py`](../bridge/mfd_celular.py) | O servidor da tela no celular: serve a página e troca as mensagens pelo Wi-Fi |
| [`bridge/celular/index.html`](../bridge/celular/index.html) | A página do celular: o "firmware" do navegador, com a mesma navball e o mesmo layout |
| [`bridge/navball.py`](../bridge/navball.py) | A conta da navball, escrita para ser passada para C |
| [`bridge/sistemas.py`](../bridge/sistemas.py) | O painel de sistemas de controle: modos do SAS, SAS, RCS, FBW, o menu do piloto automático e a troca de página |
| [`bridge/painel_scripts.py`](../bridge/painel_scripts.py) | O painel de scripts: o korry POUSO segurado 5 s abre e aborta o `scripts/pouso.py` num processo |
| [`bridge/celular/painel.html`](../bridge/celular/painel.html) | A página de botões dos painéis de sistemas e de scripts, no lugar do painel de verdade |
| [`firmware/mfd/`](../firmware/mfd/) | O firmware da mikromedia, em C: a cópia do simulador na placa ([mikromedia.md](mikromedia.md)) |
| [`docs/protocolo.md`](protocolo.md#tela-multifunção-mikromedia) | O protocolo da tela, mensagem por mensagem |

## Instalar

No PC, além do que a ponte do painel já usa:

```
pip install krpc pyserial pygame-ce numpy
```

O **pygame-ce** é a versão do pygame mantida pela comunidade, e o código usa do mesmo jeito (`import pygame`). O pygame original não tem pacote para o Python 3.14. Não instale os dois juntos: se o pygame original já estiver instalado, rode `pip uninstall pygame` antes.

## O que a tela mostra

O layout se inspira na navball do KSP2: a bola no centro, cercada por um aro escuro.

- **Números na navball:** o rumo a cada 30°, logo acima do horizonte (N, 30, 60, L, 120...), e o pitch a cada 30° (60, 30, -30, -60), ao lado dos meridianos de N, L, S e O. Eles ficam sempre de pé, sem girar com a bola, e somem perto da borda.
- **Navball:** o "W" laranja no centro é para onde o nariz aponta. Os marcadores têm as cores do KSP, e cada um tem o seu oposto do outro lado da bola:

  | Cor | Marcador | Oposto |
  |---|---|---|
  | Amarelo | Pró-grado: para onde a nave vai | Retrógrado |
  | Roxo | Normal: perpendicular à órbita (numa órbita para leste, aponta para o norte) | Antinormal |
  | Ciano | Radial para fora: perpendicular ao movimento, do lado de fora do planeta | Radial para dentro |
  | Rosa | Alvo, quando há um alvo escolhido no jogo | Anti-alvo |
  | Azul | Nó de manobra: a direção da queima que falta | — |
  | Verde (quatro cantos) | Ponto do [fly by wire](fbw.md): para onde o avião está sendo levado. Com o avião no ponto, o pró-grado fica dentro do quadrado | — |

- **Caixa amarela, à esquerda:** a velocidade, com o modo no título (`VEL SUP`, `VEL ORB` ou `VEL ALVO`). **Tocar nela troca o modo**, como no KSP2.
- **Caixa magenta, à direita:** `ALT`, acima do nível do mar. Abaixo de 5 km do chão vira `RADAR`, a altura acima do chão ou do mar; volta para `ALT` acima de 5,5 km.
- **Barra da esquerda:** o acelerador, de 0 a 100%.
- **Barra da direita:** a velocidade vertical, com o zero no meio e escala logarítmica (±10, ±100 e ±1000 m/s nas marcas e nas pontas). Verde subindo, amarela descendo devagar e vermelha descendo a mais de 10 m/s.
- **Botões redondos RCS e SAS**, embaixo da bola: verde quando o sistema está ligado **no jogo**. Tocar liga ou desliga.
- **Painel de baixo:** muda com o modo, e no `SUP` não aparece, porque a velocidade vertical já está na barra.

  | Modo | Velocidade, pró-grado, normal e radial em relação a | Painel de baixo |
  |---|---|---|
  | `SUP` | Superfície | — |
  | `ORB` | Órbita | `AP` e `PE`, com o tempo até cada um |
  | `ALVO` | Alvo (normal e radial não aparecem) | `DIST`, a distância até o alvo |

- **O modo troca sozinho, como no KSP:** vai para `ORB` acima de 36 km e volta para `SUP` abaixo de 33 km, em Kerbin. Em outros planetas, 6% e 5,5% do raio. Escolher ou trocar o alvo no jogo leva para `ALVO`, e tirar o alvo volta para `SUP` ou `ORB`. O toque na caixa da velocidade passa para o próximo modo; a escolha vale até a próxima troca automática.

## Testar sem o KSP

```
cd bridge
python mfd.py --demo
```

A nave de mentira desce até perto do chão e sobe até 55 km a cada 2 minutos. A cada minuto, ela ganha um alvo por 30 segundos, e a cada minuto e meio, um nó de manobra por 30 segundos. A cada 2 minutos, o ponto verde do fly by wire aparece por 40 segundos, andando em volta do pró-grado.

| Você faz | Resultado esperado |
|---|---|
| Roda o comando | A janela abre. A navball gira devagar, sobe, desce e rola, com os números do rumo e do pitch andando junto, e os números das caixas e as barras mudam. |
| Espera | `ALT` vira `RADAR` perto do chão. O modo passa sozinho para `ORB` acima de 36 km e volta para `SUP` abaixo de 33 km, e o painel de baixo muda junto. Quando o alvo aparece, vai para `ALVO`, com `DIST` e os marcadores rosa; quando o alvo some, volta. O marcador azul da manobra aparece e some, e o ponto verde do fly by wire também. O terminal mostra cada troca. |
| Clica em **SAS** | O terminal mostra `SAS: ligar` e o botão fica verde. Outro clique apaga. |
| Clica em **RCS** | Igual ao SAS |
| Clica na **caixa da velocidade** | Passa para o próximo modo. `ALVO` só entra na roda enquanto há alvo. |
| Clica fora dos botões | Nada acontece |
| Fecha a janela | O programa termina |

Janela pequena? `python mfd.py --demo --zoom 3`.

## No celular

O celular pode ser a tela, pelo Wi-Fi, sem instalar nada nele. A página desenha o mesmo layout da placa na resolução do celular, então tudo fica nítido.

![A tela no celular, em órbita: o mesmo layout, desenhado na resolução do celular](img/mfd_celular.png)

1. No notebook, rode a ponte com `--celular`; com `--demo` também funciona:

   ```
   cd bridge
   python mfd.py --celular
   ```

   O terminal mostra o endereço, por exemplo `Abra no navegador do celular: http://192.168.0.15:8000`.

2. Na primeira vez, o Windows pergunta se o Python pode usar a rede. Marque **Redes privadas** e permita.
3. No celular, conectado **ao mesmo Wi-Fi**, abra esse endereço no navegador (Chrome no Android, Safari no iPhone) e deite o celular.
   - **Android:** o primeiro toque põe a página em tela cheia.
   - **iPhone:** Compartilhar → **Adicionar à Tela de Início**, e abra pelo ícone, que já fica sem a barra do navegador.
4. Aumente o tempo de bloqueio da tela do celular. Uma página comum, sem HTTPS, não consegue manter a tela acesa sozinha.

Outros detalhes:

- Pode abrir em mais de um aparelho ao mesmo tempo, inclusive no navegador do próprio notebook: todos mostram a mesma coisa e todos respondem ao toque.
- Qualquer pessoa no mesmo Wi-Fi pode abrir a página e tocar nos botões. Em casa não tem problema; em rede pública, não use.
- Se a conexão cair, a página reconecta sozinha e pede tudo de novo à ponte.
- A janela do simulador continua sendo a referência do que a placa vai mostrar, ponto por ponto. A página segue as mesmas posições, só que com mais detalhe.

**Pronto quando:**

- [ ] Com `python mfd.py --demo --celular`, a página abre no celular e a navball se mexe.
- [ ] Tocar em SAS deixa o botão verde e mostra `SAS: ligar` no terminal.
- [ ] O primeiro toque põe a página em tela cheia (Android), ou ela abre sem a barra pelo ícone da Tela de Início (iPhone).
- [ ] Desligar o Wi-Fi do celular por alguns segundos mostra `SEM SINAL`; ao religar, a tela volta sozinha.
- [ ] Com o KSP, os mesmos itens de [Testar com o KSP](#testar-com-o-ksp) valem no celular.

## Painel de sistemas de controle

O [painel de sistemas de controle](../hardware/construcao.md#painel-de-sistemas-de-controle) (modos do SAS, SAS, RCS, FBW, trava de altitude e o piloto automático) é tratado por esta mesma ponte, porque ela já tem o jogo, a tela e a conversa com o [fly by wire](fbw.md). Enquanto o painel não existe, uma **página de botões** faz o papel dele, no navegador do celular ou do PC, e manda as mesmas linhas que o painel vai mandar ([protocolo](protocolo.md#painel-de-sistemas-de-controle)).

![A página de botões: os dez modos do SAS com o NORMAL aceso, SAS, RCS e FBW ligados, e o encoder do piloto automático com o HDG ligado](img/painel_sistemas.png)

A ponte abre a página sozinha, na porta **8001**, junto com a tela (no simulador, no celular ou na placa). O terminal mostra o endereço:

```
cd bridge
python mfd.py --demo --celular
```

```
Para a tela, abra no navegador do celular: http://192.168.0.15:8000
Para a página de botões do painel de sistemas, abra no navegador do celular: http://192.168.0.15:8001
```

Dá para abrir a tela num celular e os botões noutro, ou os dois no mesmo, em abas. Os botões ficam melhores com o celular em pé. `--painel 8002` troca a porta, e `--sem-painel` não abre a página.

**Os controles:**

| Controle | Faz |
|---|---|
| Korry de modo (ESTAB, PRO, NORMAL...) | Escolhe o modo do SAS no jogo. Com o SAS desligado, liga junto. Um modo que o jogo não aceita (sem alvo, sem nó, SAS fraco) não muda nada |
| SAS, RCS | Liga e desliga no jogo |
| FBW, TRAVA ALT | Vão para o `fbw.py`: ligam e desligam o FBW e a trava da altitude do momento. Sem o `fbw.py` aberto, não fazem nada |
| Encoder | Arraste o dedo em volta do anel para girar (20 cliques por volta), ou use `+` e `-`. O centro é o botão: apertar escolhe, segurar 1 s liga o modo |

**As luzes**, que mostram o estado do jogo e do `fbw.py`, nunca o toque:

- **Modo do SAS:** azul enquanto a nave vira para o marcador, verde quando ela chega a menos de 2° dele (e volta a azul acima de 4°). ESTAB fica verde logo, porque segura a atitude de agora.
- **SAS, RCS:** verdes ligados. A metade de baixo acende em âmbar com o SAS ligado sem carga elétrica (`SEM EC`) ou o RCS ligado sem monopropelente (`SEM MP`).
- **FBW:** verde voando no FBW; `DIRETA` em âmbar no ar na lei direta. **TRAVA ALT:** verde com a altitude travada.
- **HDG, ALT, V/S:** verdes com o modo ligado (o ALT também armado).
- **ESTOL:** vermelha, piscando, com o [alpha floor](fbw.md#alpha-floor) do FBW ligado (o avião devagar demais para a asa). Junto, a tela toca dois bipes por segundo: no celular, o som só é liberado depois do primeiro toque na tela (o mesmo que põe em tela cheia); no simulador, pela placa de som do PC.

### As páginas do painel na tela

Mexer no painel troca a tela, e uns **10 s depois do último toque** ela volta sozinha para a navball. As páginas são só para ver: o toque nelas não faz nada.

| Página | Abre quando | Mostra |
|---|---|---|
| Roda do SAS | Um korry de modo, SAS ou RCS | Os seis modos em volta da nave e, embaixo, ESTAB, MANOBRA, ALVO e ANTIALVO (`--` sem nó ou sem alvo). O modo escolhido ganha um anel azul ou verde, e a seta do meio aponta para ele, torta enquanto a nave ainda vira. Em cima, o SAS e o erro em graus até o marcador |
| Piloto automático | O encoder | HDG, ALT e V/S, cada um com o estado (DESLIGADO, LIGADO em verde, ARMADO em azul) e o valor. O cursor é a seta; a linha escolhida tem o valor na caixa âmbar. Embaixo, a lei do FBW e a trava |

![A roda do SAS no simulador: o PRO escolhido, azul, com a nave ainda virando](img/mfd_sas.png) ![A página do piloto automático no simulador: HDG e V/S ligados, ALT armado e escolhido](img/mfd_ap.png)

**O menu do piloto**, com o encoder:

1. Com a tela noutra página, girar ou apertar só abre a página do piloto.
2. Girar move o cursor entre HDG, ALT e V/S (horário desce).
3. Apertar escolhe a linha, e girar muda o valor: horário soma. Devagar, de 1 em 1 (1°, 10 m, 0,1 m/s); rápido, de 10 em 10.
4. Apertar de novo sai da linha.
5. Segurar 1 s liga ou desliga o modo da linha do cursor.

Os valores começam onde o avião está na primeira vez que a página abre (o rumo e a altitude arredondada), e vão para o `fbw.py` quando mudam e 1 vez por segundo. O que cada modo faz no avião está em [docs/fbw.md](fbw.md#piloto-automático).

### Testar o painel sem o KSP

Com `python mfd.py --demo --celular`, a página de botões e as páginas novas da tela funcionam com a nave de mentira. Um avião de mentira faz o papel do `fbw.py`: os modos ligam e desligam, e o ALT fica armado por 6 s antes de "chegar".

| Você faz | Resultado esperado |
|---|---|
| Aperta PRO | A tela mostra a roda do SAS. PRO fica azul, com o `ERRO` caindo, e verde em uns 4 s, na tela e no korry. 10 s depois, a tela volta para a navball |
| Aperta ALVO sem alvo (na primeira metade de cada minuto) | Nada muda. O terminal diz que o jogo não aceitaria |
| Aperta RCS | O RCS acende. A cada 2 minutos, por 20 s, o `SEM MP` fica âmbar |
| Gira o encoder | A tela mostra a página do piloto. O próximo giro move o cursor |
| Aperta o centro e gira | O valor da linha fica na caixa âmbar e muda. Girando rápido, anda de 10 em 10 |
| Segura o centro 1 s | O modo da linha liga: a luz ao lado do encoder acende, e a página mostra LIGADO (ou ARMADO no ALT, e LIGADO 6 s depois) |
| Aperta FBW | `LEI DIRETA` na página, `DIRETA` âmbar no korry, e os modos desligam |
| Espera, com o FBW ligado | A cada 2 minutos, por 8 s, o avião de mentira "estola": a luz ESTOL pisca, os modos desligam e a tela toca o alarme (no celular, depois de tocar na tela uma vez) |

**Pronto quando:**

- [ ] Com o KSP: cada korry de modo muda o modo do SAS no jogo, e a luz fica azul e depois verde quando a nave chega no marcador.
- [ ] Com o KSP: apertar ALVO sem alvo não muda nada no jogo nem na luz.
- [ ] Com o KSP: `SEM EC` acende quando a bateria acaba com o SAS ligado.
- [ ] Com o `fbw.py` voando: os korry FBW e TRAVA ALT, e o encoder segurado, mudam o FBW, e as luzes acompanham.
- [ ] No celular de verdade: arrastar em volta do anel gira o encoder sem rolar a página.

## Painel de scripts e a página do pouso

O [painel de scripts](../hardware/construcao.md#painel-de-scripts) tem um korry por script de voo; por enquanto, só o POUSO, que dispara o [`scripts/pouso.py`](../scripts/pouso.py). Ele fica na mesma página de botões do painel de sistemas (porta **8001**), embaixo, com os lugares vagos dos próximos scripts.

- **Segurar o POUSO 5 s** abre o pouso. O korry pisca âmbar enquanto conta, e a tela abre a página POUSO com `SEGURE 3 S / PARA POUSAR`. Soltar antes não faz nada.
- Com o pouso voando, o korry fica **verde** e a página acompanha a descida. **Segurar de novo 5 s aborta:** o script corta o motor e devolve a nave; o korry fica **vermelho** por 10 s.
- Quando a nave pousa, a página mostra `POUSADA` por 10 s e volta para a navball. Se o script para sem pousar (sem nave ativa, sem chão, nave perdida), o korry fica vermelho e a página mostra `FALHOU`; o motivo aparece no terminal da ponte, nas linhas `[pouso]`.

O script roda num processo próprio, o mesmo da linha de comando, e manda o estado dele para a ponte por UDP ([protocolo](protocolo.md#painel-de-scripts)). A ponte passa para ele o IP do KSP que ela mesma usa.

![A página do pouso no simulador: a nave freando a 250 m do chão, com o motor a 72%, a fase QUEIMA e a barra da freada](img/mfd_pouso.png)

**A página POUSO**, inspirada na tela do booster da SpaceX:

| Onde | O quê |
|---|---|
| No meio | A nave descendo pela linha tracejada até o alvo, na altura do pé numa escala logarítmica (1, 10, 100 e 1000 m ocupam o mesmo espaço). A chama cresce com o acelerador, e o trem aparece baixado na freada |
| Em cima, à esquerda | `ALT` (altura do pé até o chão), `VEL` (descida) e `TWR` (empuxo/peso no chão) |
| Em cima, à direita | `SAS` (RETRO ou ESTAB, o que a guiagem pediu), `MOTOR` e `INCL` (graus do nariz até a vertical) |
| Embaixo, à esquerda | A fase: `QUEDA` em azul (esperando a hora de acender), `QUEIMA` e `TOQUE` em verde, e o fim: `POUSADA`, `ABORTADO` ou `FALHOU` |
| Embaixo, à direita | `FREADA`: quanto do empuxo a freada precisa agora. O motor acende quando a barra chega na marca âmbar (85%); acima de 100%, vermelho: não dá mais para parar |
| No alto do meio | Os avisos do script, piscando: `EMPUXO INSUFICIENTE`, `SEM MOTOR ATIVO`, `NARIZ LONGE DA VERTICAL` |

### Testar o pouso sem o KSP

Com `python mfd.py --demo --celular` (ou sem `--celular`, no simulador), segurar o POUSO abre o `pouso.py --demo`, que pousa uma nave de mentira em Kerbin: começa a 4 km, descendo a 200 m/s, e pousa em uns 30 s. É o script de verdade, com a mesma guiagem, o mesmo UDP e o mesmo aborto.

| Você faz | Resultado esperado |
|---|---|
| Segura o POUSO 2 s e solta | O korry pisca âmbar e a tela abre a página POUSO com `SEGURE 3 S`. Soltando, nada abre; 10 s depois, a tela volta para a navball |
| Segura o POUSO 5 s | O terminal mostra `[pouso] aberto` e as linhas do script. O korry fica verde, a página mostra `QUEDA` em azul, e a barra da freada sobe até a marca |
| Espera | `QUEIMA` em verde, a chama acende e o trem baixa; perto do chão, `TOQUE`; depois `POUSADA`, e o korry apaga. 10 s depois, a navball |
| Segura de novo 5 s no meio da descida | `SEGURE ... PARA ABORTAR`; depois `[pouso] Interrompido`, o korry vermelho e `ABORTADO` na página |
| Aperta um modo do SAS no meio do pouso | A roda do SAS abre e, 10 s depois, volta para a página do pouso |

Os testes automáticos ficam em `bridge/tests/test_scripts.py`, e um deles abre o `pouso.py --demo` de verdade e aborta.

**Pronto quando:**

- [ ] Com o KSP: segurar o POUSO 5 s com a nave caindo abre o pouso, e a página acompanha até `POUSADA`.
- [ ] Com o KSP: segurar de novo 5 s aborta, com o motor cortado e o SAS segurando a atitude.
- [ ] Com o KSP e a nave no chão: o korry fica vermelho e o terminal diz que a nave já está pousada.
- [ ] No celular de verdade: o toque longo no korry não abre o menu do navegador nem seleciona texto.

## Testar com o KSP

Com o jogo na cena de voo e o servidor kRPC iniciado:

```
cd bridge
python mfd.py
```

A ponte do painel (`ponte.py`) pode rodar ao mesmo tempo, em outro terminal: o kRPC aceita as duas conexões.

**Pronto quando:**

- [x] Na plataforma, a navball da janela fica igual à do jogo: o centro no azul, olhando para cima.
- [x] **Pitch** (W/S), **yaw** (A/D) e **roll** (Q/E): a navball da janela gira igual à do jogo.
- [x] O pró-grado da janela fica no mesmo lugar que o do jogo.
- [x] **SAS** e **RCS:** tocar o botão liga e desliga no jogo, e as teclas **T** e **R** mudam a cor do botão.
- [x] Voltar ao KSC mostra `SEM SINAL`. Lançar outra nave faz a tela voltar sozinha.
- [ ] Na plataforma e no pouso, a tela mostra `RADAR`, igual ao altímetro do jogo no modo radar. Acima de 5,5 km volta para `ALT`.
- [ ] Na subida, o modo passa sozinho para `ORB` perto dos 36 km, junto com a navball do jogo. Na descida, volta para `SUP` perto dos 33 km. `AP` e `PE` só aparecem em `ORB` e batem com o mapa (tecla **M**).
- [ ] Em `SUP`, `V VERT` fica negativa descendo e positiva subindo.
- [ ] **Alvo:** escolher uma nave ou um planeta como alvo leva a tela para `ALVO`. Os marcadores rosa ficam no mesmo lugar que os do jogo, e `VEL` e `DIST` batem com os do jogo no modo *Target*. Tirar o alvo volta para `SUP` ou `ORB`.
- [ ] **MODO:** tocar na caixa da velocidade passa por `SUP`, `ORB` e `ALVO` (só com alvo).
- [ ] Em órbita, os marcadores **normal** e **radial** ficam no mesmo lugar que os do jogo: aponte a nave para o normal (SAS em *Normal*) e o triângulo roxo deve ficar no centro.
- [ ] Com um **nó de manobra**, o marcador azul fica no mesmo lugar que o do jogo e some quando a queima termina.
- [ ] A barra do **acelerador** acompanha as teclas **Shift** e **Ctrl** (e **Z** e **X**).
- [ ] A barra da **velocidade vertical** fica verde na subida e amarela ou vermelha na descida.
- [ ] O tempo até o `AP` e o `PE` bate com o do mapa.
- [ ] Os **números na navball** (rumo e pitch) ficam nos mesmos lugares que os da navball do jogo.

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `No module named 'pygame'` (ou `numpy`) | Faltou instalar | `pip install pygame-ce numpy` |
| O `pip install pygame` falha dizendo que não há versão para o Python 3.14 | O pygame original parou no Python 3.13 | Instalar o `pygame-ce` no lugar |
| Fica parado em `Conectando ao kRPC...` | O jogo está esperando você aceitar a conexão | Aceitar na janela do kRPC, dentro do jogo |
| Tocar em SAS não deixa o botão verde | A nave não tem SAS (sem piloto nem núcleo de sonda com SAS) | É o comportamento certo: o botão mostra o jogo |
| `SEM SINAL` com o foguete voando | A ponte parou, ou o terminal mostra `Nenhuma nave ativa` | Ver a mensagem no terminal |
| O celular não abre a página | Celular noutra rede (dados móveis, Wi-Fi de visitantes), firewall do Windows, ou rede do Windows como Pública | Mesmo Wi-Fi; permitir o Python em *Redes privadas*; rede do Windows como Privada, como na fase 0 |
| O endereço mostrado não funciona, e o notebook tem mais de uma rede (cabo e Wi-Fi, VPN) | O IP mostrado é o da outra rede | Ver o IP do Wi-Fi com `ipconfig` e usar esse, com `:8000` no fim |
| `Não foi possível abrir a porta 8000 para o celular` | Outro programa já usa a porta | `python mfd.py --celular 8080` e abrir com `:8080` no fim |
| `DIST`, `AP` ou `PE` mostram `---` longe de casa | A distância passou de 2,1 milhões de km, o limite de um inteiro de 32 bits | Normal com planetas distantes |

## Como o código funciona por dentro

A cada volta do laço principal (`voar()` no `mfd.py`, a cada ~10 ms):

1. **A fonte lê o jogo** e devolve uma `Telemetria`: atitude, velocidades nos três modos, altitude e radar, posição, órbita, acelerador, alvo, nó de manobra e o estado do SAS e do RCS. A fonte é a `NaveKrpc` (streams do kRPC) ou a `Demo` (a nave de mentira).
2. **O ponto do fly by wire** chega dos scripts por UDP (`Scripts`), se o `fbw.py` estiver voando. Na demonstração, a `Demo` inventa um.
3. **As linhas da tela e do painel são tratadas:** `READY` faz a ponte reenviar tudo; `TOQUE SAS` e `TOQUE RCS` invertem o sistema no jogo; `TOQUE MODO` passa para o próximo modo. As linhas do painel de sistemas (`BTN`, `ENC`) vão para `Sistemas.tratar()`.
4. **O `ModoNavball` escolhe o modo** (`SUP`, `ORB` ou `ALVO`), com as trocas automáticas pela altitude e pelo alvo.
5. **O `Transmissor` decide o que mandar e quando:**

   | O quê | Frequência |
   |---|---|
   | `MODO`, `SAS` e `RCS` | Quando mudam, e todos 1 vez por segundo. O `MODO` vai antes dos números |
   | `ATT` | 20 por segundo |
   | Marcadores: `PRO`, `NRM`, `RDL`, `TGT`, `MNV` e `FBW` | 10 por segundo |
   | Números: `ALT` ou `RAD`, `VEL`, `VV`, `ACEL` e `DIST` | 10 por segundo |
   | Órbita: `AP`, `PE`, `TAP` e `TPE`, só no modo `ORB` | 2 por segundo |

6. **O painel de sistemas:** a cada 50 ms, a ponte mede o erro até o marcador do SAS (`erro_do_sas()`), junta o estado do `fbw.py` e manda as luzes ao painel e as páginas à tela. Um `Remetente` para cada um manda cada linha quando muda e todas 1 vez por segundo.

As peças:

| Peça | Arquivo | Papel |
|---|---|---|
| `NaveKrpc` e `Demo` | `mfd.py` | Fontes de dados: o jogo, pelo kRPC, ou uma nave de mentira |
| `Telemetria` | `mfd.py` | Tudo o que a ponte precisa saber da nave numa volta do laço |
| `ModoNavball` | `mfd.py` | O modo da navball e as trocas automáticas |
| `Transmissor` | `mfd.py` | Transforma a telemetria em mensagens, cada uma na sua frequência |
| `Scripts` | `mfd.py` | Conversa com os scripts de voo por UDP: recebe o ponto, a lei, a trava e os modos do FBW, e manda os comandos do painel |
| `Sistemas`, `MenuPiloto`, `CorDoModo` | `sistemas.py` | O painel de sistemas: os botões, o menu do piloto, o azul e o verde, e a página da tela |
| `Demo`, `FbwDemo` | `mfd.py` | A nave de mentira e um fly by wire de mentira, para testar o painel sem o jogo |
| `Simulador` | `mfd_simulador.py` | Tela: janela no PC, na resolução da placa |
| `TelaCelular` | `mfd_celular.py` | Tela: servidor HTTP que liga a ponte à página do celular |
| página | `celular/index.html` | O "firmware" do navegador: interpreta o protocolo e desenha |
| página de botões | `celular/painel.html` | O painel de sistemas no navegador: manda os botões e acende as luzes, servida por outra `TelaCelular` |
| `TelaMikromedia` | `mfd.py` | Tela: a serial da mikromedia, pela PROG. Abre a porta sem prender a placa no reset |
| funções da navball | `navball.py` | A conta da bola, usada pelo simulador e copiada no JavaScript |

Toda tela tem a mesma interface: `enviar(linha)` manda uma linha para a tela, `linhas()` devolve as linhas que a tela mandou, e ainda `esperar_ready()` e `fechar()`.

**Referenciais.** As velocidades e direções saem do kRPC já nos eixos do horizonte local da nave (cima, norte, leste), por referenciais "híbridos": posição e velocidade medidas em relação ao planeta, mas com os eixos da superfície. Em relação ao chão, que gira, no modo `SUP`; em relação ao centro do planeta, sem girar, no `ORB`. A velocidade relativa ao alvo é a diferença entre a velocidade orbital da nave e a do alvo, as duas no mesmo referencial.

### Acrescentar um número ou um marcador

1. **`Telemetria`:** um campo novo, preenchido pela `NaveKrpc.ler()` (um stream novo no `__init__`) e pela `Demo.ler()`.
2. **`Transmissor.enviar()`:** a mensagem nova, na frequência certa. Para um marcador, use `mensagem_direcao()` com um vetor (cima, norte, leste).
3. **`docs/protocolo.md`:** uma linha na tabela.
4. **`mfd_simulador.py`:** aceitar a mensagem em `_interpretar()` e desenhar. Um marcador também entra em `_marcadores` e em `pares`, com a função que o desenha.
5. **`celular/index.html`:** o mesmo, em `interpretar()` e no desenho, nas mesmas posições.
6. **`firmware/mfd/mfd.c`:** o mesmo, em `interpretar()` e no desenho; depois, `python compilar.py` e gravar.

Depois, confira com `python mfd.py --demo`, na janela e com `--celular`.

### Armadilhas

- **O layout está em três lugares:** `mfd_simulador.py`, `celular/index.html` e `firmware/mfd/mfd.c`, e as cores e larguras da navball também estão em `navball.py` e `firmware/mfd/navball.c`. Mudou um, mude os outros. O simulador é a referência da placa.
- **Linhas de no máximo 31 caracteres.** Um texto livre, como o nome de um alvo, teria que ser cortado antes de ir para a tela.
- **Os referenciais do kRPC são "canhotos"** (eixos da mão esquerda). O produto vetorial só dá o sentido certo em eixos da mão direita, então `normal_e_radial()` troca a ordem para (leste, norte, cima) antes da conta.
- **No navegador, os pedidos HTTP podem chegar fora de ordem.** A página manda uma linha de cada vez, esperando a anterior terminar, para funcionar como uma serial.
- **Página sem HTTPS:** o navegador não deixa manter a tela do celular acesa, e o iPhone não deixa pôr uma página em tela cheia (só pelo ícone da Tela de Início).
- **pygame no Python 3.14:** só o `pygame-ce` tem pacote; os dois não podem ser instalados juntos.

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
3. **Marcadores e números:** cada um é um vetor projetado na bola por 3 produtos escalares, e só aparece se estiver na metade visível. As direções dos marcadores chegam prontas da ponte: normal e radial saem de produtos vetoriais da posição e da velocidade, feitos no PC. Os números do rumo e do pitch são escritos de pé no ponto projetado, com a fonte normal e uma sombra escura, então a placa não precisa girar texto.

Com raio de 72 pontos, são cerca de 16 mil pontos por quadro, cada um com umas 30 operações de inteiros. Na placa ([`navball.c`](../firmware/mfd/navball.c)), a conta é a mesma, em inteiros com 14 bits de fração, e a tela é desenhada em faixas de 16 linhas ([mikromedia.md](mikromedia.md#como-o-firmware-funciona)). A velocidade de verdade só dá para saber medindo na placa.

## Próximos passos

1. **Gravar e ligar a placa** ([mikromedia.md](mikromedia.md)): confirmar o controlador da tela, a orientação, o touch e a velocidade.
2. **Alarme de estol na placa**, pelo chip de áudio (VS1053), como o simulador já toca.
3. **Manobras pela tela** (ideia para depois): informações do próximo nó (Δv, tempo de queima, T− até o nó) e um editor de manobras pelo toque, junto com o editor de encoders da fase 4.
4. **Painéis de sistemas e de scripts de verdade:** quando os módulos existirem, as mesmas linhas chegam pela serial do Mega, pela ponte do painel (`ponte.py`), e as duas pontes precisam virar uma, ou a do painel repassar as linhas para esta.

## Histórico

A tela foi feita aos poucos, testando no jogo entre uma etapa e outra:

| PR | O que entrou |
|---|---|
| [#10](https://github.com/Schackschuck/KSP/pull/10) | Descoberta das duas USB da placa (a PROG tem um FT232RL); o simulador de 320x240, a ponte com o kRPC, o modo `--demo` e a navball 3D feita só com multiplicações e somas |
| [#11](https://github.com/Schackschuck/KSP/pull/11) | Instalação com o `pygame-ce`, porque o pygame não tem pacote para o Python 3.14 |
| [#12](https://github.com/Schackschuck/KSP/pull/12) | Altitude pelo radar perto do chão, troca automática SUP ⇄ ORB como no KSP, e o modo ALVO |
| [#13](https://github.com/Schackschuck/KSP/pull/13) | Marcadores normal, radial e de manobra; visual inspirado no KSP2, com barras do acelerador e da velocidade vertical e botões redondos |
| [#14](https://github.com/Schackschuck/KSP/pull/14) | A tela no celular, pelo Wi-Fi |
| [#15](https://github.com/Schackschuck/KSP/pull/15) | Números do rumo e do pitch na própria navball; sai a fita de rumo, e o modo SUP fica sem o painel de baixo |
| [#32](https://github.com/Schackschuck/KSP/pull/32) | Painel de sistemas de controle: a página de botões, a roda do SAS e a página do piloto automático, com a volta à navball; a conversa com o `fbw.py` nos dois sentidos |
| [#40](https://github.com/Schackschuck/KSP/pull/40) | O firmware da mikromedia, cópia do simulador na placa, com o ajuste da tela e do touch na flash; a ponte abre a PROG sem prender a placa no reset |
