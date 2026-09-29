# Fly by wire de avião

**Pronto quando:** um avião decola na lei direta e, com o FBW, responde ao manche na hora, sem balançar: puxar dá carga, rolar dá rolagem, e soltar segura o que estava.

Como nos caças (F-16, Gripen), o manche não mexe nas superfícies: ele pede uma **carga** (em g) e uma **velocidade de rolagem**, e o FBW decide o profundor, os ailerons e o leme para o avião fazer isso. [`scripts/fbw.py`](../scripts/fbw.py) lê o joystick pela USB e manda tudo ao jogo pelo kRPC. A arquitetura e as decisões estão no [README](../README.md#fly-by-wire-de-avião).

**Onde estamos:** o script passa nos testes com um avião simulado ([`scripts/tests/test_fbw.py`](../scripts/tests/test_fbw.py)), em 100, 150, 200 e 280 m/s, e com um avião "nervoso" (superfícies fortes, pouco amortecimento e a leitura do kRPC atrasada em até 160 ms), como o do primeiro voo gravado.

**Por que mudou:** a primeira versão movia um ponto na navball, e o avião ia até ele devagar. O voo gravado mostrou que ela era lenta demais (o ponto andava a 8°/s e o avião levava 2,5 s para chegar), que soltar o manche não parava a curva (o avião continuava indo atrás do ponto), que empurrar o manche mal descia (a carga mínima era 0 g) e que o nariz oscilava sozinho a 1,5 vez por segundo, entre −2 g e +5 g (ganho alto demais para o atraso do kRPC). A lei de caça resolve os três primeiros; ganhos menores e o integral certo resolvem o último. Depois, a recuperação automática do estol e o limite de ângulo de ataque no manche também saíram: sobrou só o aviso ([Aviso de estol](#aviso-de-estol)).

## O manche

| Você faz | O avião |
|---|---|
| Manche para trás | Puxa carga: até **4 g** com o manche todo, na hora |
| Manche para a frente | Até **−1 g** com o manche todo |
| Solta em pitch | Volta a **1 g** (corrigido pelo ângulo de subida): com as asas niveladas, o caminho não curva nem para cima nem para baixo |
| Manche para os lados | Rola, até **90°/s** com o manche todo |
| Solta de lado | A rolagem para e a **inclinação fica onde parou**, em qualquer ângulo, até de costas |
| Torce o manche | Soma ao leme que o FBW usa para coordenar a curva |

- **Numa curva inclinada, puxe o manche** para o avião não descer: soltando, ele faz 1 g, e a asa inclinada não segura o peso todo. É assim num caça. A 60° de inclinação, são 2 g para manter a altitude.
- **O FBW não trava a altitude sozinho.** Para segurar a altitude, use o korry **TRAVA ALT** ou o piloto automático.
- Perto da vertical (nariz a mais de 75° do horizonte), a inclinação não é segurada: só a rolagem para.

**Sem proteção de estol no manche:** puxando tudo devagar, o avião estola, como no jogo sem o script. O único limite é a carga pedida, até 4 g. O piloto automático e a TRAVA ALT continuam com o ângulo de ataque entre −8° e 15°, para não estolarem o avião sozinhos.

### Aviso de estol

- Com o ângulo de ataque acima de **14,5°**, o painel acende a luz **ESTOL**, vermelha e piscando, com dois bipes por segundo na tela. O terminal mostra `ESTOL`. Abaixo de **13°**, apaga.
- **É só um aviso: o FBW não mexe em nada.** O acelerador, o piloto automático, a trava e o manche continuam como estavam. Quem recupera é o piloto: empurra o manche e põe motor.
- A primeira versão tinha um alpha floor (acelerador a 100%, piloto automático e trava desligados, nariz para baixo e a trava ligando sozinha na altitude nova). Saiu porque tirava o avião do piloto, e a trava que ligava sozinha parecia o piloto automático subindo para uma altitude.

**Lei direta:** no chão, e com o FBW desligado pelo botão, o manche mexe direto nas superfícies, como no jogo sem o script. O FBW assume sozinho 1 s depois de o avião sair do chão, e volta para a lei direta ao tocar no chão. No ar ralo, ou muito devagar, as superfícies não seguram o avião, e também fica a lei direta.

**O acelerador fica com o piloto.** A alavanca do joystick vai para o jogo só quando é mexida, e as teclas Shift e Ctrl do jogo continuam valendo (a última que mexeu ganha). O acelerador automático (SPD) já existe por dentro (`FlyByWire.velocidade_alvo`) e é usado nos testes, mas ainda não tem como ser ligado.

## Piloto automático

Por cima do FBW, como um piloto que não cansa: cada modo pede um caminho (um rumo, um ângulo de subida), e o FBW calcula a inclinação e a carga para chegar nele, com as proteções valendo. O caminho pedido aparece na navball da tela, como o ponto verde. Os modos são ligados e os valores escolhidos no [painel de sistemas de controle](../hardware/construcao.md#painel-de-sistemas-de-controle), que ainda é uma [página de botões](mfd.md#painel-de-sistemas-de-controle) aberta pela ponte da tela. Por isso, **o piloto automático precisa da ponte da tela aberta** (`python mfd.py`).

| Modo | O que faz | Luz |
|---|---|---|
| **HDG** | Vira até o rumo escolhido, com as asas até 60° (menos, devagar, se a asa não aguenta), e segura | Verde |
| **V/S** | O ângulo de subida que dá a velocidade vertical escolhida | Verde |
| **ALT** | Sobe ou desce até a altitude escolhida: com a velocidade do V/S, se ele estiver ligado, ou a 10 m/s. Perto dela (20 m, ou 4 s na velocidade vertical de agora), nivela e segura, e o V/S desliga | Azul enquanto vai (armado), verde segurando |

- **Só liga voando na lei do FBW.** Na lei direta (no chão, ou com o FBW desligado), os modos desligam, como no avião.
- **Mexer no manche devolve o eixo ao piloto:** para os lados desliga o HDG; para trás ou para a frente, o ALT, o V/S e a trava. Cada eixo é separado: com o ALT ligado, o piloto pode rolar e fazer a curva na mão, e a altitude continua segura.
- **Trava de altitude:** o korry **TRAVA ALT** trava a altitude do momento (e desliga o ALT e o V/S) ou solta a trava. Ela não liga sozinha, e nenhum modo do piloto automático liga sem ser pedido no painel.
- **Korry FBW:** o mesmo que o botão do FBW no joystick.

**Na ponte:** o `fbw.py` manda à ponte da tela, 10 vezes por segundo, num pacote UDP, o caminho pedido (`FBW`, ou `FBW OFF` voando na mão), a lei (`LEI`), a trava (`TRAVA`) e os modos (`APL`). A ponte responde para o mesmo endereço com os toques do painel (`CMD FBW`, `CMD TRAVA`, `CMD HDG`...) e os valores do menu (`APV`). Protocolo em [docs/protocolo.md](protocolo.md#ponte-da-tela--fly-by-wire).

**Testar no jogo**, depois do roteiro do FBW abaixo, com a ponte da tela e a página de botões abertas:

| Você faz | Resultado esperado |
|---|---|
| No chão, segura o encoder no HDG | Nada liga: a página continua DESLIGADO |
| Voando no FBW, escolhe HDG 90° a mais que o rumo e segura o encoder | Terminal: `Painel: HDG ligado`. O avião vira até o rumo, com as asas até 60°, e segura. A altitude muda pouco |
| Escolhe V/S +5,0 e liga | O avião sobe a uns 5 m/s (barra V VERT da tela) |
| Escolhe ALT 300 m acima e liga, com o V/S ligado | ALT azul (armado); perto da altitude, nivela, fica verde e o V/S desliga |
| Mexe o manche para o lado | O HDG desliga (luz apagada); o ALT continua |
| Aperta TRAVA ALT | A trava liga na altitude do momento; o terminal mostra `trava` no status |
| Com a trava ligada e o HDG virando, tira o motor (Ctrl ou X) e espera | O avião perde velocidade. Perto de 14,5° de ângulo de ataque: `ESTOL`, luz ESTOL piscando e alarme. O HDG e a trava continuam ligados, o acelerador fica em zero e o ângulo de ataque não passa de 15°: o avião vai afundando. Empurre o manche e ponha motor para sair |
| Liga o FBW (korry ou botão) sem mexer em nada do painel | Nenhum modo acende e a TRAVA fica apagada |

**Pronto quando:** um avião decola na mão, e o piloto automático leva ele até a altitude e o rumo escolhidos no painel e segura lá.

### Sem joystick

Para testar o piloto automático sem o joystick:

```
python scripts/fbw.py --sem-joystick
```

- **Na lei direta** (no chão, e com o FBW desligado), o script não mexe nas superfícies: o avião é pilotado pelo **teclado do jogo** (W/S, A/D, Q/E), como sem o script. Decole assim.
- **No ar**, 1 s depois de sair do chão, o FBW assume e segura o caminho e a inclinação em que o avião está. Nivele antes, com o teclado, e ligue a TRAVA ALT ou o piloto automático. Daí em diante, o teclado não deve ser usado para pilotar: quem muda o caminho é o piloto automático, pelo painel (a página de botões da ponte da tela). O acelerador continua no Shift e no Ctrl.
- Para voltar ao teclado (para pousar, por exemplo), aperte o korry **FBW** no painel: a lei volta a ser a direta, e o script solta o manche.
- A conferir no jogo: se, na lei direta, o teclado não mexer nas superfícies, anote. O script manda o manche zerado uma vez, ao voltar para a lei direta, e depois não manda mais nada.

## Controles

Perfil `extreme3d` (padrão), o [Logitech Extreme 3D Pro](../hardware/construcao.md#joystick-logitech-extreme-3d-pro):

| Controle | FBW | Lei direta |
|---|---|---|
| Manche para trás e para a frente (Y) | Carga, de −1 g a 4 g | Profundor |
| Manche para os lados (X) | Velocidade de rolagem, até 90°/s | Ailerons |
| Torção do manche | Leme, somado ao que o FBW usa para coordenar a curva | Leme (e roda do nariz, no chão) |
| Alavanca da base | Acelerador | Acelerador |
| Botão 3 (no topo do manche) | Liga e desliga o FBW | Liga e desliga o FBW |

Com o perfil `xbox`: analógico esquerdo como manche, o direito (para os lados) como leme e o botão Y liga e desliga o FBW; o acelerador fica só nas teclas. A ordem dos eixos de um controle de Xbox muda com o sistema: confira com `--controles` e, se precisar, mude o `PERFIS` no começo do `fbw.py`.

## Instalar

No PC (ou no Pi), além do que a ponte já usa:

```
pip install krpc pygame-ce
```

**No KSP, deixe os eixos do joystick sem nada** (*Settings → Input*). Senão o jogo também lê o manche e os comandos chegam em dobro.

## Testar

### 1. O joystick, sem o KSP

```
python scripts/fbw.py --controles
```

Mexa cada controle e veja qual número muda:

- [ ] Manche para os lados: eixo **0**, −1 à esquerda, +1 à direita.
- [ ] Manche para a frente: eixo **1** vai a −1; para trás, a +1.
- [ ] Torção: eixo **2**, +1 para a direita.
- [ ] Alavanca: eixo **3**, −1 toda para a frente (o lado do "+").
- [ ] Botão 3 do manche aparece como **2** (o pygame conta a partir de 0).

Se algum número for outro, ajuste o perfil `extreme3d` no começo do `fbw.py`.

### 2. No jogo

Um avião pequeno de fábrica, como o **Aeris 3A**, serve de referência: dá para repetir o teste depois de mudar um ganho. Na pista, com o servidor kRPC ligado:

```
python scripts/fbw.py --gravar voo.csv
```

Para ver o caminho do piloto automático na tela, rode a ponte da tela em outro terminal (`cd bridge` e `python mfd.py`, ou `python mfd.py --celular`). Uma vez por segundo, o terminal do FBW mostra a lei, a velocidade, a altitude, o pró-grado, o caminho pedido (com o piloto automático ou a trava), a inclinação atual e a pedida, o ângulo de ataque, a carga atual e a pedida, e os comandos.

| Você faz | Resultado esperado |
|---|---|
| Parado na pista, mexe o manche | Terminal: `DIRETA ... (no chão)`. As superfícies mexem como no teclado: puxar levanta o profundor, torcer vira o leme. Se alguma for ao contrário, anote qual |
| Mexe a alavanca | O acelerador do jogo acompanha. Parada a alavanca, Shift e Ctrl continuam funcionando |
| Decola puxando o manche | 1 s depois de sair do chão: `--> lei FBW` e, se estava ligado, `SAS desligado`. O avião continua subindo com o manche puxado, sem tranco |
| Nivela e solta o manche | O avião segue reto, sem balançar. A altitude muda devagar (não há trava) |
| Puxa o manche até a metade por 2 s e solta | A carga sobe na hora (terminal: `carga`), o nariz sobe, e soltando o caminho para de curvar e fica no ângulo em que estava, sem balançar |
| Empurra todo por 2 s e solta | A carga vai abaixo de zero e o nariz desce rápido; soltando, para |
| Manche todo para a direita por 1 s e solta | O avião rola rápido e para uns poucos graus depois de soltar. A inclinação fica ali |
| Com 60° de inclinação, puxa o manche | O avião vira mais rápido; com uns 2 g, a altitude fica |
| Motor em zero, manche todo para trás | Perto de 14,5° de ângulo de ataque (terminal: `alfa`), a luz ESTOL pisca. O FBW não segura: o avião estola, e o acelerador continua em zero. Empurre para recuperar |
| Aperta o botão 3 | `FBW desligado (lei direta)`: o manche volta a mexer direto nas superfícies. Apertando de novo, o FBW volta |
| Pousa | Aproxime na mão, uns 3° abaixo do horizonte. Para arredondar, puxe o manche devagar, ou desligue o FBW no botão e pouse na lei direta. Ao tocar: `--> lei DIRETA (no chão)` |

**Pronto quando:**

- [ ] O manche mexe as superfícies para o lado certo na lei direta.
- [ ] O FBW assume depois da decolagem sem tranco.
- [ ] Puxar e empurrar respondem na hora, e soltar não faz o nariz balançar.
- [ ] Rolar e soltar: a inclinação fica onde parou.
- [ ] Com o manche todo para trás e devagar, a luz ESTOL pisca antes de o avião estolar, e o FBW não mexe em nada.
- [ ] Ligar o FBW não liga nenhum modo nem a trava.
- [ ] O botão 3 troca entre FBW e lei direta.
- [ ] Com a TRAVA ALT ou o piloto automático, o ponto verde da tela bate com o que o terminal mostra.

## Ajustar

Os ganhos estão no começo do `fbw.py`, com a unidade de cada um. Voe gravando (`--gravar voo.csv`) e abra a planilha: cada linha é uma volta do laço, com o que cada camada pediu (`inclinacao_c`, `carga_c`, `giro_pitch_c`...) ao lado do que o avião fez.

| Sintoma | Onde mexer |
|---|---|
| O nariz balança para cima e para baixo, rápido | Diminuir `KP_PITCH`, `KI_PITCH` e `K_CARGA` |
| A carga demora para chegar na pedida | Aumentar `K_CARGA` ou `KI_PITCH` |
| O avião puxa pouco (ou demais) com o manche todo | `CARGA_MANCHE_MAX` e `CARGA_MANCHE_MIN` |
| O avião rola devagar demais (ou rápido demais) | `GIRO_ROLL_MANCHE` |
| As asas balançam depois de rolar | Diminuir `KP_ROLL` e `KI_ROLL` |
| A rolagem passa muito do ponto em que o manche foi solto | Aumentar `KP_ROLL` |
| O avião escorrega de lado nas curvas (a bola do escorregamento, `beta`, longe de zero) | Aumentar `K_BETA` |
| A altitude travada fica oscilando devagar | Diminuir `K_ALTITUDE` |
| No piloto automático, o pró-grado passa do caminho pedido e volta | Diminuir `K_TRAJETORIA` |

Os ganhos das superfícies são divididos pela **autoridade** do avião: a aceleração angular que ele faz com o comando todo, do torque disponível e da inércia que o kRPC informa (colunas `autoridade_*` da planilha). Por isso o mesmo ajuste serve devagar e rápido. Se o kRPC informar uma autoridade muito diferente da real, o avião fica mole (autoridade alta demais) ou balança (baixa demais). Nos testes, o FBW segura o avião com a autoridade errada pela metade ou pelo dobro.

## Como funciona por dentro

A guiagem (`FlyByWire`) não conhece o kRPC nem o joystick, como a do pouso: recebe uma `Leitura` do avião e um `Manche` e devolve `Comandos`. Assim os testes usam a mesma classe com um avião simulado.

```
 manche em pitch ──▶ carga (−1 a 4 g; solto, 1 g · cos γ)
 ALT, V/S, TRAVA ──▶ caminho ──▶ carga para curvar até ele
                    │
 1. giros           ▼
            carga → giro do nariz em pitch   (no piloto automático, limitado pelo ângulo de ataque)

 manche de lado ──▶ velocidade de rolagem (até 90°/s)
 solto ──▶ segura a inclinação em que parou
 HDG ──▶ rumo ──▶ inclinação (até 60°) ──▶ velocidade de rolagem
            escorregamento → leme (+ torção do manche)
                    │
 2. superfícies     ▼
            diferença de giro → proporcional + integral, ÷ autoridade → control.pitch, roll, yaw
```

- **Velocidades de giro** saem da diferença entre os eixos da nave numa leitura e na anterior, com o tempo do jogo. Pelos ângulos daria errado: o rumo pula de 359° para 0°.
- **Ângulo de ataque e escorregamento** saem da velocidade escrita nos eixos da nave. A **carga** é a força do ar (`aerodynamic_force` do kRPC) na direção do "cima" da nave, dividida pelo peso.
- **Carga → giro do nariz:** o giro que a carga pedida dá ao caminho, mais `K_CARGA` vezes a diferença entre a carga pedida e a de agora, para o ângulo de ataque chegar lá.
- **Integrais:** o do pitch guarda o profundor que segura o ângulo de ataque; o do roll, o aileron que segura a rolagem pedida. Os dois acham sozinhos o comando que o avião precisa, que muda de avião para avião.
- **Inclinação segura:** soltando o manche de lado, a rolagem para primeiro (o giro cai abaixo de 3°/s) e só então a inclinação daquele momento fica segura, para não voltar para trás.
- **Leme:** zera o escorregamento e, rolando com ângulo de ataque, gira o nariz junto para a rolagem ser em volta do caminho, e não do nariz.
- **Troca de lei sem tranco:** ao assumir, os integrais começam com o comando que já estava no jogo.
- **Na tela:** com o piloto automático ou a trava, o script manda o caminho pedido, `FBW <pitch> <rumo>`, por UDP para a ponte da tela, que repassa para a navball ([protocolo](protocolo.md#scripts--ponte-da-tela)), junto com a lei, a trava e os modos do piloto, e recebe os toques do painel de volta. Voando na mão, manda `FBW OFF`.
- **Piloto automático:** `_gama_automatico()` dá o ângulo de subida do ALT, do V/S ou da trava, e `_rumo_automatico()` o rumo do HDG. Cada um vale só no seu eixo; sem eles, o eixo fica com o manche.

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `Nenhum joystick encontrado` | Joystick desligado, ou o pygame não o vê | Religar na USB e rodar `--controles`. Com mais de um, escolher com `--joystick 1` |
| O manche só funciona com a janela do terminal na frente | O SDL ignora o joystick em segundo plano | O script já pede para não ignorar (`SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS`). Se acontecer, anote o sistema e a versão do pygame |
| O avião responde em dobro ou sozinho | O KSP também lê o joystick | Tirar os eixos do joystick das configurações de controle do KSP |
| Na lei direta, alguma superfície mexe ao contrário | Eixo invertido no perfil, ou convenção de sinal do jogo | Anotar qual e mudar o sinal no `Joystick.ler()`. Se for o pitch, o FBW também vai errar: não ligue antes de corrigir |
| O avião balança no FBW | Ganho alto para esse avião | Ver [Ajustar](#ajustar) |
| `--> lei DIRETA (ar ralo...)` voando | Pressão dinâmica abaixo de 500 Pa: muito alto ou muito devagar | Normal: as superfícies não seguram o avião ali |
| O SAS liga sozinho e o terminal diz `SAS desligado` de novo | Alguém apertou T | O FBW desliga o SAS, que brigaria com ele pelo manche |
| O ponto verde não aparece na tela | Voando na mão, ele não aparece: só com o piloto automático ou a trava. Com eles, a ponte da tela não está aberta, ou está em outro computador | Abrir o `mfd.py`; em outro computador, `--tela <IP>` e liberar a porta UDP 50100 no firewall |
| O painel mostra `FBW FECHADO` e os modos não ligam | A ponte não recebe o `fbw.py` | Abrir o `fbw.py`, com `--tela <IP>` se a ponte está noutro computador. As respostas voltam para a porta de onde o `fbw.py` manda: no firewall, liberar o Python |
| Segurar o encoder não liga o modo | O avião está na lei direta (no chão, ou FBW desligado) | Normal: o piloto automático só liga voando no FBW |
| O avião afunda com o manche puxado, e a luz ESTOL pisca | Devagar demais para a asa | Empurre o manche e ponha motor; sem motor, desça para ganhar velocidade ([Aviso de estol](#aviso-de-estol)) |
| Um modo do piloto automático ou a TRAVA acende sem você pedir | Com o `fbw.py` antigo, a trava ligava sozinha com o manche solto perto do horizonte e depois do alpha floor | Atualizar (`git pull`): agora nada liga sozinho. Se ainda acontecer, anote o que estava aceso e grave o voo |
| `Nenhum joystick encontrado`, e não há joystick | O script espera um joystick | `--sem-joystick`: decola pelo teclado, e o piloto automático voa ([Sem joystick](#sem-joystick)) |

## Próximos passos

1. **Testar no jogo** com o roteiro acima, gravando (`--gravar voo.csv`), e ajustar os ganhos.
2. **SPD:** uma interface para a velocidade escolhida (botões + e − no celular, depois um encoder).
3. **Testar o piloto automático no jogo** com o roteiro de [Piloto automático](#piloto-automático).
4. **Arredondamento no pouso:** perto do chão, passar para uma lei que facilite o toque, como o Airbus faz a 50 pés.
5. **Joystick na ponte:** quando a ponte ler o joystick ([hardware/construcao.md](../hardware/construcao.md#joystick-logitech-extreme-3d-pro)), a classe `Joystick` passa para lá, e o script recebe o manche dela.
