# Fly by wire de avião

**Pronto quando:** um avião decola na lei direta e, com o FBW, voa reto, faz curvas, sobe e desce só pelo ponto, sem balançar. A navball da tela mostra o ponto no mesmo lugar para onde o avião vai.

Como nos aviões da Airbus, o manche não mexe nas superfícies: ele diz para onde o piloto quer ir. [`scripts/fbw.py`](../scripts/fbw.py) lê o joystick pela USB, decide o profundor, os ailerons e o leme e manda tudo ao jogo pelo kRPC. A arquitetura e as decisões estão no [README](../README.md#fly-by-wire-de-avião).

**Onde estamos:** o script está escrito e passa nos testes com um avião simulado ([`scripts/tests/test_fbw.py`](../scripts/tests/test_fbw.py)), em 100, 150 e 280 m/s. Ainda não foi testado no jogo nem com o joystick de verdade.

## O ponto

O manche move um **ponto na navball**, que diz para onde o avião deve ir: um rumo e um ângulo de subida. O FBW inclina as asas, puxa ou cede o nariz e usa o leme até o **pró-grado** (o círculo amarelo, para onde o avião vai de verdade) ficar em cima do ponto.

| Você faz | O ponto | O avião |
|---|---|---|
| Manche para trás | Sobe, até 8°/s com o manche todo | Sobe junto, até +30° |
| Manche para a frente | Desce | Desce junto, até −30° |
| Manche para os lados | Anda para os lados, até 15°/s | Inclina as asas e faz a curva |
| Solta o manche | Fica onde está | Vai até o ponto e segue nele |
| Solta com o ponto a menos de 1° do horizonte | Vai para o horizonte e trava a altitude daquele momento | Segura a altitude; o ponto sobe e desce um pouco sozinho para corrigir |

- O ponto fica no máximo 60° para o lado do pró-grado, para não sair da navball. Segurando o manche de lado, ele fica na beirada e vai sendo levado enquanto o avião vira: é uma curva contínua.
- Mexer o manche para trás ou para a frente destrava a altitude.

**Proteções**, que valem mesmo com o manche todo para um lado:

- **Inclinação das asas até 60°.** Devagar, menos: a 60°, a asa precisa fazer 2 g para o avião não descer. Se ela não consegue sem passar do ângulo de ataque máximo, a curva fica mais aberta em vez de o avião perder altura.
- **Ângulo de subida entre −30° e +30°.**
- **Ângulo de ataque até 15°:** puxar o manche não estola o avião. Sem motor, o avião vai perdendo velocidade e desce devagar, com a asa no limite.

### Alpha floor

Devagar demais, a asa no limite do ângulo de ataque não sustenta o peso, e o avião vai afundando, mesmo com o ponto no horizonte: a proteção não deixa estolar, mas também não faz milagre. Como no Airbus, o FBW então corrige:

- Com o ângulo de ataque acima de **14,5°** (0,5° antes do limite), o **acelerador vai a 100%**, o **piloto automático desliga** e o painel acende a luz **ESTOL**, vermelha e piscando, com dois bipes por segundo na tela. O terminal mostra `ESTOL`.
- O nariz continua na proteção dos 15°, e o avião ganha velocidade. Com o ângulo de ataque abaixo de **10°** por **2 s**, o alarme para.
- **O acelerador fica no máximo** até o piloto mexer nele (a alavanca do joystick, ou Shift e Ctrl), como o TOGA LOCK do Airbus: ninguém tira a potência sem querer.
- Durante o alpha floor, o piloto automático não liga.
- Sem motor, ou com pouco, o alarme continua: o avião desce devagar, com a asa no limite.
- Na curva devagar, a asa usa até uns 13,5° (90% do que aguenta), abaixo do alpha floor: curva não liga o alarme.

**Lei direta:** no chão, e com o FBW desligado pelo botão, o manche mexe direto nas superfícies, como no jogo sem o script. O FBW assume sozinho 1 s depois de o avião sair do chão, e volta para a lei direta ao tocar no chão. No ar ralo, ou muito devagar, as superfícies não seguram o avião, e também fica a lei direta.

**O acelerador fica com o piloto.** A alavanca do joystick vai para o jogo só quando é mexida, e as teclas Shift e Ctrl do jogo continuam valendo (a última que mexeu ganha). O acelerador automático (SPD) já existe por dentro (`FlyByWire.velocidade_alvo`) e é usado nos testes, mas ainda não tem como ser ligado.

## Piloto automático

Por cima do FBW, como um piloto que não cansa: cada modo só mexe no ponto, e as proteções continuam valendo. Os modos são ligados e os valores escolhidos no [painel de sistemas de controle](../hardware/construcao.md#painel-de-sistemas-de-controle), que ainda é uma [página de botões](mfd.md#painel-de-sistemas-de-controle) aberta pela ponte da tela. Por isso, **o piloto automático precisa da ponte da tela aberta** (`python mfd.py`).

| Modo | O ponto | Luz |
|---|---|---|
| **HDG** | O rumo do ponto vai para o rumo escolhido. Longe, o ponto fica na beirada (60° do pró-grado) e o avião faz uma curva contínua até lá | Verde |
| **V/S** | O ângulo de subida que dá a velocidade vertical escolhida | Verde |
| **ALT** | Sobe ou desce até a altitude escolhida: com a velocidade do V/S, se ele estiver ligado, ou a 10 m/s. Perto dela (20 m, ou 4 s na velocidade vertical de agora), nivela e segura, e o V/S desliga | Azul enquanto vai (armado), verde segurando |

- **Só liga voando na lei do FBW.** Na lei direta (no chão, ou com o FBW desligado), os modos desligam, como no avião.
- **Mexer no manche devolve o ponto ao piloto:** para os lados desliga o HDG; para trás ou para a frente, o ALT e o V/S. O ponto começa de onde o piloto automático deixou, sem tranco.
- **Trava de altitude:** continua sozinha, com o manche solto e o ponto perto do horizonte. O korry **TRAVA ALT** trava a altitude do momento (e desliga o ALT e o V/S) ou solta a trava; solta pelo korry, ela só volta sozinha depois de o manche se mexer.
- **Korry FBW:** o mesmo que o botão do FBW no joystick.

**Na ponte:** o `fbw.py` manda à ponte da tela, 10 vezes por segundo, num pacote UDP, o ponto (`FBW`), a lei (`LEI`), a trava (`TRAVA`) e os modos (`APL`). A ponte responde para o mesmo endereço com os toques do painel (`CMD FBW`, `CMD TRAVA`, `CMD HDG`...) e os valores do menu (`APV`). Protocolo em [docs/protocolo.md](protocolo.md#ponte-da-tela--fly-by-wire).

**Testar no jogo**, depois do roteiro do FBW abaixo, com a ponte da tela e a página de botões abertas:

| Você faz | Resultado esperado |
|---|---|
| No chão, segura o encoder no HDG | Nada liga: a página continua DESLIGADO |
| Voando no FBW, escolhe HDG 90° a mais que o rumo e segura o encoder | Terminal: `Painel: HDG ligado`. O avião vira até o rumo, com as asas até 60°, e segura. A altitude muda pouco |
| Escolhe V/S +5,0 e liga | O avião sobe a uns 5 m/s (barra V VERT da tela) |
| Escolhe ALT 300 m acima e liga, com o V/S ligado | ALT azul (armado); perto da altitude, nivela, fica verde e o V/S desliga |
| Mexe o manche para o lado | O HDG desliga (luz apagada); o ALT continua |
| Aperta TRAVA ALT | A trava liga na altitude do momento; o terminal mostra `trava` no status |
| Com a trava ligada, tira o motor (Ctrl ou X) e espera | O avião perde velocidade. Perto de 14,5° de ângulo de ataque: `ESTOL`, acelerador em 100%, piloto automático desligado, luz ESTOL piscando e alarme. Depois de recuperar, o alarme para, e o acelerador fica no máximo até você mexer |

**Pronto quando:** um avião decola na mão, e o piloto automático leva ele até a altitude e o rumo escolhidos no painel e segura lá.

### Sem joystick

Para testar o piloto automático sem o joystick:

```
python scripts/fbw.py --sem-joystick
```

- **Na lei direta** (no chão, e com o FBW desligado), o script não mexe nas superfícies: o avião é pilotado pelo **teclado do jogo** (W/S, A/D, Q/E), como sem o script. Decole assim.
- **No ar**, 1 s depois de sair do chão, o FBW assume e segura o ponto onde o avião está indo. Daí em diante, o teclado não deve ser usado para pilotar: quem mexe no ponto é o piloto automático, pelo painel (a página de botões da ponte da tela). O acelerador continua no Shift e no Ctrl.
- Para voltar ao teclado (para pousar, por exemplo), aperte o korry **FBW** no painel: a lei volta a ser a direta, e o script solta o manche.
- A conferir no jogo: se, na lei direta, o teclado não mexer nas superfícies, anote. O script manda o manche zerado uma vez, ao voltar para a lei direta, e depois não manda mais nada.

## Controles

Perfil `extreme3d` (padrão), o [Logitech Extreme 3D Pro](../hardware/construcao.md#joystick-logitech-extreme-3d-pro):

| Controle | FBW | Lei direta |
|---|---|---|
| Manche para trás e para a frente (Y) | Sobe e desce o ponto | Profundor |
| Manche para os lados (X) | Leva o ponto para os lados | Ailerons |
| Torção do manche | Nada: o FBW coordena a curva sozinho | Leme (e roda do nariz, no chão) |
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

Para ver o ponto na tela, rode a ponte da tela em outro terminal (`cd bridge` e `python mfd.py`, ou `python mfd.py --celular`). Uma vez por segundo, o terminal do FBW mostra a lei, a velocidade, a altitude, o pró-grado e o ponto, a inclinação atual e a pedida, o ângulo de ataque, a carga atual e a pedida, e os comandos.

| Você faz | Resultado esperado |
|---|---|
| Parado na pista, mexe o manche | Terminal: `DIRETA ... (no chão)`. As superfícies mexem como no teclado: puxar levanta o profundor, torcer vira o leme. Se alguma for ao contrário, anote qual |
| Mexe a alavanca | O acelerador do jogo acompanha. Parada a alavanca, Shift e Ctrl continuam funcionando |
| Decola puxando o manche | 1 s depois de sair do chão: `--> lei FBW` e, se estava ligado, `SAS desligado`. O avião continua subindo com o manche puxado, e o ponto verde aparece na navball da tela |
| Solta o manche | O avião segue o ponto, sem balançar |
| Traz o ponto para perto do horizonte e solta | Terminal: `trava <altitude>`. A altitude fica a poucos metros dela |
| Manche para a direita por 3 s e solta | O ponto anda ~45°. As asas inclinam até no máximo 60°, o avião vira e nivela as asas com o pró-grado em cima do ponto, sem passar dele. A altitude muda pouco |
| Manche para trás por 1 s e solta | O ponto sobe ~8°, e o avião sobe e segura esse ângulo |
| Motor em zero, manche todo para trás | O ângulo de ataque para em ~15° (terminal: `alfa`), o avião não estola e vai perdendo velocidade |
| Aperta o botão 3 | `FBW desligado (lei direta)`: o manche volta a mexer direto nas superfícies. Apertando de novo, o FBW volta, com o ponto onde o avião está indo |
| Pousa | Aproxime com o ponto uns 3° abaixo do horizonte, na pista. Para arredondar, puxe o manche devagar, ou desligue o FBW no botão e pouse na lei direta. Ao tocar: `--> lei DIRETA (no chão)` |
| Na tela, durante o voo | O ponto verde fica onde o terminal diz e, com o avião estabilizado, o pró-grado amarelo fica dentro dele |

**Pronto quando:**

- [ ] O manche mexe as superfícies para o lado certo na lei direta.
- [ ] O FBW assume depois da decolagem sem tranco.
- [ ] Reto e nivelado, com o manche solto, a altitude fica a menos de 10 m da travada.
- [ ] Curva de 90°: a inclinação não passa de ~62° e o avião termina no ponto, sem ficar balançando.
- [ ] Subida e descida seguem o ponto.
- [ ] Com o manche todo para trás, o ângulo de ataque não passa de ~16°.
- [ ] O botão 3 troca entre FBW e lei direta.
- [ ] O ponto verde da tela bate com o que o terminal mostra.

## Ajustar

Os ganhos estão no começo do `fbw.py`, com a unidade de cada um. Voe gravando (`--gravar voo.csv`) e abra a planilha: cada linha é uma volta do laço, com o que cada camada pediu (`inclinacao_c`, `carga_c`, `giro_pitch_c`...) ao lado do que o avião fez.

| Sintoma | Onde mexer |
|---|---|
| O nariz balança para cima e para baixo, rápido | Diminuir `KP_PITCH` e `KI_PITCH` |
| O nariz demora para responder, ou o avião afunda no começo das curvas | Aumentar `KP_PITCH`, ou `K_CARGA` |
| As asas balançam ao chegar na inclinação | Diminuir `KP_ROLL` ou `K_INCLINACAO` |
| As asas passam da inclinação pedida | Diminuir `K_INCLINACAO` |
| O avião rola devagar | Aumentar `GIRO_ROLL_MAX` ou `KP_ROLL` |
| O avião escorrega de lado nas curvas (a bola do escorregamento, `beta`, longe de zero) | Aumentar `K_BETA` |
| A altitude travada fica oscilando devagar | Diminuir `K_ALTITUDE` |
| O pró-grado passa do ponto e volta | Diminuir `K_TRAJETORIA` |

Os ganhos das superfícies são divididos pela **autoridade** do avião: a aceleração angular que ele faz com o comando todo, do torque disponível e da inércia que o kRPC informa (colunas `autoridade_*` da planilha). Por isso o mesmo ajuste serve devagar e rápido. Se o kRPC informar uma autoridade muito diferente da real, o avião fica mole (autoridade alta demais) ou balança (baixa demais). Nos testes, o FBW segura o avião com a autoridade errada pela metade ou pelo dobro.

## Como funciona por dentro

A guiagem (`FlyByWire`) não conhece o kRPC nem o joystick, como a do pouso: recebe uma `Leitura` do avião e um `Manche` e devolve `Comandos`. Assim os testes usam a mesma classe com um avião simulado.

```
 manche ──▶ ponto (rumo, ângulo de subida) ◀── trava de altitude
                    │
 1. trajetória      │ diferença entre o ponto e o pró-grado
                    ▼
            aceleração que falta para curvar o caminho
            → inclinação das asas (até 60°, menos se a asa não aguenta)
            → carga, em g (na curva, 1 / cos(inclinação) para não descer)
                    │
 2. giros           ▼
            carga → giro do nariz em pitch   (limitado pelo ângulo de ataque)
            inclinação → giro em roll
            escorregamento → leme
                    │
 3. superfícies     ▼
            diferença de giro × ganho ÷ autoridade → control.pitch, roll, yaw
```

- **Velocidades de giro** saem da diferença entre os eixos da nave numa leitura e na anterior, com o tempo do jogo. Pelos ângulos daria errado: o rumo pula de 359° para 0°.
- **Ângulo de ataque e escorregamento** saem da velocidade escrita nos eixos da nave. A **carga** é a força do ar (`aerodynamic_force` do kRPC) na direção do "cima" da nave, dividida pelo peso.
- **Integrais:** o do pitch guarda o profundor que segura o ângulo de ataque; o do roll só age perto da inclinação pedida, senão o aileron guardado na rolagem levaria a asa além dela.
- **Troca de lei sem tranco:** ao assumir, o ponto começa no pró-grado e os integrais com o comando que já estava no jogo.
- **Na tela:** o script manda `FBW <pitch> <rumo>` por UDP para a ponte da tela, que repassa para a navball ([protocolo](protocolo.md#scripts--ponte-da-tela)), junto com a lei, a trava e os modos do piloto, e recebe os toques do painel de volta.
- **Piloto automático:** depois do manche, `_mover_ponto()` põe o rumo do HDG no ponto, e `_subida_do_piloto()` dá a velocidade vertical do ALT e do V/S, que vira o ângulo de subida do ponto. O resto do FBW não muda.

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
| O ponto não aparece na tela | A ponte da tela não está aberta, ou está em outro computador | Abrir o `mfd.py`; em outro computador, `--tela <IP>` e liberar a porta UDP 50100 no firewall |
| O painel mostra `FBW FECHADO` e os modos não ligam | A ponte não recebe o `fbw.py` | Abrir o `fbw.py`, com `--tela <IP>` se a ponte está noutro computador. As respostas voltam para a porta de onde o `fbw.py` manda: no firewall, liberar o Python |
| Segurar o encoder não liga o modo | O avião está na lei direta (no chão, ou FBW desligado), ou no alpha floor | Normal: o piloto automático só liga voando no FBW, fora do alpha floor |
| O avião afunda com o ponto no horizonte, e a luz ESTOL pisca | Devagar demais para a asa | O alpha floor já pôs o acelerador no máximo; se não houver motor, desça para ganhar velocidade ([Alpha floor](#alpha-floor)) |
| `Nenhum joystick encontrado`, e não há joystick | O script espera um joystick | `--sem-joystick`: decola pelo teclado, e o piloto automático voa ([Sem joystick](#sem-joystick)) |

## Próximos passos

1. **Testar no jogo** com o roteiro acima e ajustar os ganhos.
2. **SPD:** uma interface para a velocidade escolhida (botões + e − no celular, depois um encoder).
3. **Testar o piloto automático no jogo** com o roteiro de [Piloto automático](#piloto-automático).
4. **Arredondamento no pouso:** perto do chão, passar para uma lei que facilite o toque, como o Airbus faz a 50 pés.
5. **Joystick na ponte:** quando a ponte ler o joystick ([hardware/construcao.md](../hardware/construcao.md#joystick-logitech-extreme-3d-pro)), a classe `Joystick` passa para lá, e o script recebe o manche dela.
