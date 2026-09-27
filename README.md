# KSP Cockpit

Controle físico (painel + joystick + telemetria) para o **Kerbal Space Program 1**, feito do zero com hardware e software próprios.

O objetivo principal é **aprender firmware/embarcados e eletrônica**, e de quebra ter um cockpit de verdade — com direito a um botão que dispara um script de pouso autônomo estilo SpaceX.

---

## Arquitetura

```
 PC com Windows: KSP 1 + servidor kRPC
          ▲
          │  rede — cabo ou Wi-Fi (kRPC, TCP/protobuf)
          ▼
 Raspberry Pi 4 = computador de bordo ............... bridge/
   • ponte kRPC ⇄ placas
   • lê o joystick (Logitech Extreme 3D Pro) pela USB
   • tela de telemetria (pygame)
   • tela multifunção no navegador do celular, pelo Wi-Fi (enquanto a placa não fica pronta)
   • dispara os scripts de voo ....................... scripts/
          ▲                              ▲
          │ USB/serial                   │ USB/serial
          │ (protocolo próprio)          │ (mesmo protocolo)
          ▼                              ▼
 Arduino Mega = I/O do painel     mikromedia (LPC2148) = tela multifunção
 firmware/painel/                 firmware/mfd/
          ▲
          │  SPI + linhas analógicas
          ▼
 Backplane: 12 slots ................................ hardware/backplane/
          ▲
          │  um cabo flat de 16 vias por módulo
          ▼
 Módulos do painel, um por seção .......... hardware/modulo_pequeno/, _medio/ e _grande/
   pequeno: 8 entradas + 8 LEDs (1 × 74HC165 + 1 × 74HC595)
   médio: 16 entradas + 16 LEDs (2 × 74HC165 + 2 × 74HC595)
   grande: 24 entradas + 16 LEDs (3 × 74HC165 + 2 × 74HC595)
   chaves, botões, LEDs, joysticks, acelerador

 Instrumentos (fase 4): displays, ponteiros e fita de LED, direto no Mega
```

Cada parte tem um papel bem definido:

| Parte | Responsabilidade | Não faz |
|---|---|---|
| **KSP + kRPC** (PC) | Expõe o estado da nave e aceita comandos. | — |
| **Computador de bordo** (Raspberry Pi 4, Python) | Conecta no kRPC pela rede, abre *streams* de telemetria, traduz eventos do painel em comandos do jogo e telemetria em mensagens para o painel. Desenha a tela de telemetria. Dispara os scripts de voo de `scripts/` (ex.: pouso autônomo). | Não lê pino nenhum. |
| **Joystick** (Logitech Extreme 3D Pro, USB no Pi) | Manda eixos e botões para o computador de bordo, que os traduz em comandos do kRPC. | O KSP não enxerga o joystick: tudo passa pela ponte. |
| **Painel** (Arduino Mega, C++) | Lê entradas (com debounce), envia eventos; recebe valores e atualiza LEDs, displays e ponteiros. | **Não sabe que o KSP existe.** É um painel de I/O genérico. |
| **Celular** (opcional, página no navegador) | Mostra a tela multifunção pelo Wi-Fi, com o mesmo protocolo e o mesmo layout, enquanto a mikromedia não tem firmware. | Não fala com o kRPC nem guarda estado: só desenha o que a ponte manda. |
| **Tela multifunção** (mikromedia for ARM, LPC2148, C sem framework) | Recebe telemetria pelo mesmo protocolo serial, desenha páginas (atitude, órbita, pouso), troca de página pelo touch e toca alarmes sonoros. | Não fala com o kRPC; só mostra o que o computador de bordo manda. |

Durante o desenvolvimento, o mesmo código Python roda no PC — só muda o endereço do servidor kRPC e a porta serial.

### Princípios

- **O LED mostra o estado do jogo, não a posição da chave.** A chave só avisa para onde foi ("SAS para cima"); o computador de bordo decide o que fazer e o jogo confirma. Assim o painel nunca fica dessincronizado (ex.: SAS desligado pelo jogo).
- **Uma tela só, no meio do painel: a tela multifunção.** Os módulos não têm tela própria. Cada módulo que precisa mostrar números (editor de manobras, piloto automático, rendezvous...) tem uma página na tela multifunção. Quando o piloto mexe num módulo, a ponte troca a tela para a página dele; uns segundos depois do último toque no módulo (uns 10 s, a ajustar), a tela volta sozinha para a página de antes, em geral a navball.
- **Protocolo serial em duas versões:**
  - **v0 — texto**, uma mensagem por linha. Fácil de depurar no Serial Monitor.
    ```
    Pi → placa:  ALT 12345      SAS 1      FUEL 73
    placa → Pi:  BTN STAGE 1    SW SAS 0   AX PITCH -312
    ```
  - **v1 — binário**, com enquadramento [COBS](https://en.wikipedia.org/wiki/Consistent_Overhead_Byte_Stuffing), ID de mensagem e CRC. Mais rápido e robusto; vem quando a v0 começar a apertar. É o mesmo protocolo para o Mega e para a mikromedia.
- **Entradas analógicas** (joystick, acelerador) são enviadas a uma taxa fixa, com zona morta e filtro; **entradas digitais** são enviadas só quando mudam.

### Decisões

| Decisão | Por quê |
|---|---|
| **kRPC** em vez de mods de serial (Kerbal Simpit etc.) | Acesso a praticamente tudo do jogo (órbita, estágios, delta-v, autopilot) e permite scripts de voo. A ferramenta não deve ser o limite. |
| **Ponte fora do microcontrolador** em vez do cliente kRPC C-nano | kRPC completo com *streams*; o firmware fica simples e ganha um protocolo próprio — que é onde está o aprendizado de embarcados. |
| **Python** na ponte | Já usado com kRPC antes; o mesmo código roda no PC e no Pi. |
| **Raspberry Pi 4** como computador de bordo | Deixa o cockpit independente do PC (só um cabo de rede) e pode ligar uma tela colorida grande. A compra dessa tela foi adiada — decidir depois. |
| **Arduino Mega** para o I/O | O Pi não tem entradas analógicas e o Linux não é tempo real; o Mega tem muitos pinos, trabalha em 5V e é compatível com praticamente todo módulo. |
| **Painel em módulos** com 74HC165 e 74HC595, ligados ao Mega por um backplane | Cada seção do painel é uma placa, montada e testada uma de cada vez. Há três tamanhos (8 entradas e 8 LEDs, 16 e 16, ou 24 e 16), para não montar CI à toa. Cada módulo tem uma etiqueta (chave DIP lida por um 74HC165 a mais), e o Mega reconhece sozinho qual módulo está em cada slot. Os CIs custam poucos reais por módulo, o firmware continua um só e o protocolo com a ponte não muda. Um micro em cada módulo fica para a fase 8. |
| Pinos do Raspberry Pi **não** substituem o Mega | O Pi não tem entradas analógicas, o Linux não é tempo real para encoders e ponteiros, e os pinos de 3,3 V vão direto ao processador: um fio errado nos 5 V queima o Pi. |
| **mikromedia for ARM (LPC2148)** como tela multifunção | Já está na bancada. ARM programado sem framework, com tela touch, microSD e áudio. Entra depois do protocolo v1, que ela também usa. |
| **Simulador da tela multifunção** no PC antes do firmware | A ponte, o protocolo e o desenho (navball, números, botões) ficam prontos e testados com o jogo antes da placa; o firmware só precisa copiar o simulador. A placa desenha a partir dos ângulos, porque a imagem pronta não cabe na serial (150 KB por quadro). |
| **Celular como tela**, por uma página web | Funciona já, sem firmware e sem o cabo, em qualquer celular e sem instalar nada. A ponte serve a página e fala com ela por HTTP (Server-Sent Events e POST), só com a biblioteca padrão do Python. O protocolo é o mesmo da placa, então a ponte não muda. |
| **pygame-ce** no lugar do pygame | O pygame original não tem pacote para o Python 3.14; o pygame-ce, mantido pela comunidade, tem e é usado do mesmo jeito (`import pygame`). |
| **Pouso por previsão**: simula a freada até o chão e acha o acelerador por bisseção | Com arrasto, a freada não tem conta fechada. Simular funciona igual em qualquer planeta, com ou sem atmosfera, e refazer a conta 20 vezes por segundo corrige os erros da previsão. O arrasto é medido em voo, e a previsão só usa parte dele, porque ele cai quando a nave fica mais lenta que o som. A guiagem não conhece o kRPC, então é testada numa nave simulada. |
| **Pé da nave medido pelas pernas do trem**, não pela caixa da nave inteira | Nas versões lançadas do kRPC (até a 0.6.0), a caixa de uma peça junta tudo o que está pendurado nela, como a chama do motor ligado. A caixa da nave inteira descia metros abaixo do pé, e a freada terminava alta. |
| **SAS do KSP aponta a nave no pouso**, não o piloto automático do kRPC | O piloto automático do kRPC vem ajustado para levar 3 s até o ângulo pedido e não conta a força do ar. No segundo teste, a nave caindo de ré balançou até 31° na freada. O SAS o jogo ajusta para cada nave. Retrógrado enquanto a nave desce rápido; devagar, perto do chão, o retrógrado pula de um lado para o outro, então no fim o SAS só segura a atitude. |
| **Scripts de voo numa pasta própria** (`scripts/`), fora da ponte | Cada script roda sozinho pela linha de comando, no PC ou no Pi, com ou sem o cockpit. A ponte só dispara o script quando o botão do painel é apertado; o script não depende dela nem do painel. |
| **Um joystick só** (Logitech Extreme 3D Pro) na USB do Pi, lido pela ponte, com uma chave de 3 posições para o modo | Já está em casa e tem 3 eixos, acelerador, 12 botões e um chapéu. Passando pela ponte, dá para ter zona morta, os modos VOO, CÂMERA e TRANSLAÇÃO, e saber quando o piloto mexe no manche para tirar o controle de um script. Não precisa abrir o joystick. |
| **Uma tela no meio para todos os módulos**, a tela multifunção, no lugar de um LCD por módulo | Os olhos vão sempre ao mesmo lugar, os painéis ficam menores e só com botões, e sai um LCD por módulo da lista de compras. A página troca sozinha para o módulo em uso e volta depois, então não é preciso escolher a página na mão. Quem decide a troca é a ponte, que já recebe todos os eventos do painel: a tela continua só desenhando. |
| **Korry switches** (botões iluminados com legenda, de avião) nos sistemas que o jogo também muda | O botão não tem posição, então nunca discorda do jogo: cada toque pede a troca, e a legenda acesa é o estado do jogo. Feitos em casa: corpo impresso em 3D e tampa de acrílico cortada a laser. Quais chaves viram korry: a decidir. |
| **Caixa em MDF cortado a laser, com peças impressas em 3D** | A laser do colégio faz as peças planas e grandes (paredes, painéis com legendas); a impressora de casa, as pequenas e complicadas (korry, knobs, suportes). Cada seção é um painel removível com o seu módulo atrás. |
| **Fly by wire pelo ponto na navball**: o manche move para onde o avião vai, e não as superfícies | É o jeito do Airbus e dos caças: soltar o manche segura o caminho, e as proteções ficam simples, porque o ponto tem limites. O piloto automático do avião vira um piloto que só mexe no ponto. |
| **Ganhos do FBW divididos pela autoridade do avião** (torque disponível ÷ inércia, informados pelo kRPC) | A força das superfícies cresce com o quadrado da velocidade: um ganho fixo, bom na decolagem, faz o avião balançar rápido, e cada avião precisaria do seu. Nos testes, o FBW segura o avião com a autoridade informada errada pela metade ou pelo dobro. |
| **Scripts mandam marcadores à ponte da tela por UDP**, com a própria linha do protocolo da tela | O script continua rodando sozinho: sem a ponte aberta, a linha se perde e nada acontece. A ponte só confere e repassa. |
| **O `fbw.py` lê o joystick sozinho**, por enquanto | A ponte ainda não lê o joystick. Quando ler, a leitura passa para ela, e o script recebe o manche da ponte. |
| **ESP32** fica para depois | Candidato a painel sem fio ou módulo extra (fase 8). |

### Estrutura planejada do repositório

```
bridge/           computador de bordo em Python: ponte kRPC ⇄ serial, tela de telemetria;
                  tela multifunção: ponte (mfd.py), simulador, navball e a página do celular (celular/);
                  editor de nós de manobra com botões na página (manobras.py); testes em bridge/tests/
scripts/          scripts de voo (pouso, fly by wire...), que rodam com ou sem o cockpit; testes em scripts/tests/
firmware/painel/  Arduino Mega (Arduino IDE ou PlatformIO)
firmware/passos/  sketches de aprendizado, um por passo da fase 1
firmware/mfd/     mikromedia for ARM / LPC2148 (C, GCC e make)
hardware/         esquemáticos e PCBs (KiCad), desenhos da caixa; ver hardware/README.md
                  e hardware/construcao.md (carcaça, aparência, painéis, joystick);
                  cada peça própria numa pasta, com ficha e desenhos (hardware/korry/)
docs/             protocolo serial, pinagem, anotações
```

---

## Roteiro

Cada fase termina com algo funcionando de ponta a ponta. Não pule o critério de "pronto".

### Fase 0 — Ambiente

**Status: concluída.** Passo a passo detalhado e problemas encontrados em [docs/setup-pi.md](docs/setup-pi.md).

**No PC:**

- Instalar KSP 1.12.x e o **kRPC** (via CKAN ou manualmente).
- No jogo, abrir a janela do kRPC e iniciar o servidor (dica: ativar *auto-start* e *auto-accept* nas configurações).
- Nas configurações do servidor, trocar o endereço de `localhost` para **Any** (aceitar conexões da rede), e liberar no firewall do Windows as portas do kRPC (padrão: 50000 e 50001).
- Marcar a rede do Windows como **Privada**; em rede Pública o Windows bloqueia a conexão do Pi.
- Instalar Python 3, `pip install krpc pyserial` e a Arduino IDE 2 (ou PlatformIO no VS Code).
- Se a placa for clone com chip CH340, instalar o driver CH340 no Windows.

**No Raspberry Pi 4:**

- Gravar o Raspberry Pi OS com o Raspberry Pi Imager, já configurando Wi-Fi e SSH.
- `pip install krpc pyserial pygame` (de preferência dentro de um *venv*).

```python
import time
import krpc

# No PC: krpc.connect(name="KSP Cockpit")
# No Pi: informar o IP do PC onde o KSP está rodando
conn = krpc.connect(name="KSP Cockpit", address="192.168.0.10")
vessel = conn.space_center.active_vessel
altitude = conn.add_stream(getattr, vessel.flight(), "mean_altitude")

while True:
    print(f"{altitude():,.0f} m")
    time.sleep(0.1)
```

Versão completa, que recebe o IP como argumento, espera a cena de voo e explica os erros de conexão: [`bridge/fase0_altitude.py`](bridge/fase0_altitude.py).

**Pronto quando:** o script roda **no Pi** e imprime a altitude ao vivo enquanto o foguete sobe no PC.

### Fase 1 — Primeiro circuito fechado

**Status: concluída**, no PC e no Pi. Roteiro passo a passo, montagem e testes: [docs/fase1.md](docs/fase1.md). Protocolo: [docs/protocolo.md](docs/protocolo.md).

- Mega ligado no PC pela USB durante o desenvolvimento; no fim, no Pi.
- 1 botão (STAGE), 1 LED (SAS) e a altitude num LCD 20x4 com módulo I2C.
- Protocolo **v0 (texto)**.
- Aprende: pull-up, debounce, leitura/escrita serial, laço principal sem `delay()`.

**Pronto quando:** apertar o botão faz *stage*, o LED acompanha o SAS do jogo e o LCD mostra a altitude.

### Fase 2 — Painel de controle

**Status: em andamento.** Chaves, botões e LEDs estão prontos para montar: pinagem, código e testes em [docs/fase2.md](docs/fase2.md). O joystick e o acelerador serão o Logitech Extreme 3D Pro, que já está em casa; falta o código na ponte.

- Chaves para SAS, RCS, trem de pouso, luzes e freios; STAGE e ABORT com capa de proteção. Depois, action groups.
- A posição da chave é o estado desejado (para cima = ligado); o LED de cada sistema mostra o estado no jogo.
- **Painel em módulos:** cada seção vira uma placa, ligada por cabo flat a um backplane de 12 slots no Mega. A placa pequena tem 8 entradas e 8 LEDs (1 × 74HC165 + 1 × 74HC595); a média, 16 e 16 (2 + 2); a grande, 24 e 16 (3 + 2). Os LEDs só mostram o que vem do jogo: nenhum é ligado a um botão. Cada módulo tem uma etiqueta numa chave DIP, e o Mega descobre sozinho o que está encaixado. Esquemáticos, etiquetas e qual placa vai em cada seção em [hardware/](hardware/README.md).
- Enquanto o primeiro módulo não fica pronto, os controles básicos continuam direto nos pinos do Mega, como em [docs/fase2.md](docs/fase2.md).
- Próximo passo: o firmware do Mega lendo a fila de módulos pelas etiquetas, e testar o primeiro módulo direto no Mega.
- **Joystick:** o Logitech Extreme 3D Pro, na USB do Pi, lido pela ponte e mandado ao jogo pelo kRPC. O acelerador é a alavanca da base dele. Mapeamento proposto em [hardware/construcao.md](hardware/construcao.md#joystick-logitech-extreme-3d-pro).
- **Korry switches** (ideia): botões iluminados com legenda, como nos aviões, para SAS, RCS, luzes e outros sistemas. Um primeiro korry pode ser testado direto no Mega. Todos do mesmo tamanho, 22,5 × 22,5 mm; medidas, peças e circuito em [hardware/korry/](hardware/korry/README.md).

**Pronto quando:** dá para lançar e colocar um foguete em órbita usando só o painel.

### Fase 3 — Tela de telemetria

- Interface em pygame no Pi: altitude, velocidades, apoapse/periapse, tempo até Ap/Pe, combustível e delta-v por estágio.
- Depois: gráfico de altitude × tempo, desenho simples da órbita, indicador de atitude.
- O Pi 4 tem folga de desempenho, mas vale o bom hábito: redesenhar só o que mudou e limitar a taxa de quadros.
- A tela definitiva do Pi foi adiada. Enquanto isso, desenvolver com qualquer monitor ou TV HDMI (ou rodando a interface no PC).
- A tela multifunção ([docs/mfd.md](docs/mfd.md)) já mostra navball, velocidades, altitude e Ap/Pe numa página web. Uma tela HDMI com touch no Pi pode abri-la em tela cheia, no navegador, sem programar nada novo.

**Pronto quando:** dá para circularizar uma órbita olhando só para a tela.

### Fase 4 — Instrumentos físicos

**Status: editor de manobras escrito, com botões numa página no lugar das chaves; falta testar no jogo.** [`bridge/manobras.py`](bridge/manobras.py) cria e edita os nós pelo kRPC e mostra os números do nó e da órbita (antes e depois) no navegador do PC ou do celular: [docs/manobras.md](docs/manobras.md). A página manda linhas do protocolo pela rede; o painel vai mandar as suas pela serial, com o encoder no lugar dos pares `+`/`-` do Δv. Por enquanto a página também gira a câmera do mapa, **o que tem que sair dela:** no cockpit, a câmera do mapa vai ser mexida pelo joystick, no modo CÂMERA.

**A fazer no editor, para ficar igual ao painel desenhado** ([desenho](hardware/construcao.md#painel-do-editor-de-manobras), [mensagens](docs/protocolo.md#no-painel)):

- [ ] Ponte (`bridge/manobras.py`): guardar o eixo escolhido (PRO, NRM ou RAD), começando pelo PRO em cada nó novo, e trocar de eixo com `BTN PRO`, `BTN NRM` e `BTN RAD`.
- [ ] Ponte: aceitar `ENC DV <cliques>` (horário positivo) e aplicar os cliques × passo no eixo escolhido.
- [ ] Ponte: aceitar `SW PASSO <0 a 3>`, o passo pela posição da chave rotativa, no lugar do `BTN PASSO`.
- [ ] Ponte: mandar ao painel qual eixo está escolhido, para acender o korry certo.
- [ ] Página do celular (`bridge/celular/manobras.html`): trocar os pares `PRO -`/`PRO +`, `NRM -`/`NRM +` e `RAD -`/`RAD +` por três botões de eixo e um par `-`/`+` que faz o papel do encoder, com o eixo escolhido destacado.
- [ ] Testes (`bridge/tests/test_manobras.py`) para o eixo escolhido, o `ENC DV` e o `SW PASSO`.
- [ ] Atualizar [docs/manobras.md](docs/manobras.md) e tirar o "planejado" da seção [No painel](docs/protocolo.md#no-painel) do protocolo.

- Displays de 7 segmentos com MAX7219 para os números mais importantes.
- Encoder rotativo para escolher o que cada display mostra. Lido pela mesma cadeia de 74HC165 dos módulos: o Mega lê a cadeia inteira mil vezes por segundo numa **interrupção de timer**, e assim o redesenho do LCD (~20 ms) não faz perder cliques. O painel acumula os cliques e manda `ENC <nome> <cliques>`.
- **Editor de nós de manobra** (pelo kRPC: `control.add_node`, `node.prograde` etc.):
  - Painel de 150 × 150 mm, desenho e peças em [hardware/construcao.md](hardware/construcao.md#painel-do-editor-de-manobras).
  - **Δv por um encoder só**, porque os três eixos nunca são mexidos ao mesmo tempo. Três korry (PRO, NRM e RAD) escolhem o eixo, e a legenda do escolhido acende na cor da alça do nó no KSP. Girar no sentido horário soma o passo; no anti-horário, tira. Um nó novo já vem com o PRO escolhido. O painel manda `ENC DV <cliques>`, e quem sabe o eixo escolhido é a ponte.
  - **PERCURSO:** uma tecla basculante com mola para o centro, como a do TIME WARP, montada deitada, move o nó ao longo da órbita (para a esquerda, antes; para a direita, depois). Segurando, repete; o painel manda `INC TEMPO <passos>`. Embaixo dela, ANT e PROX trocam de nó.
  - **PASSO:** chave rotativa de 4 posições, com a legenda gravada em volta: 0,1 / 1 / 10 / 100 m/s no Δv e 1 s / 10 s / 1 min / 10 min no tempo.
  - Korry NOVO (nó novo no apoastro), APAGAR e CIRC (circulariza no ponto do nó, com o Δv calculado pela ponte). Sem AP e PE: o tempo já leva o nó a qualquer ponto.
  - São 16 entradas e 3 LEDs (os korry de eixo): cabe numa placa média.
  - **Sem tela no módulo:** Δv, tempo de queima, T− até o nó e o Ap/Pe resultante aparecem numa página do editor na tela multifunção, que abre sozinha quando uma tecla ou botão do editor é usado (ver os [princípios](#princípios)).
  - O botão MAPA (liga e desliga o mapa do jogo) fica na seção da câmera. A câmera do mapa (girar, aproximar, trocar o foco entre nave, nó e planeta) fica no joystick, no modo CÂMERA, não no editor.
- Barra de combustível com LEDs WS2812.
- Ponteiro analógico com motor de passo X27.168.
- Fonte 5V externa (a USB não aguenta muitos LEDs).

**Pronto quando:** um voo inteiro (lançamento → órbita → reentrada) é feito sem olhar para o monitor do PC, inclusive planejar a circularização pelo editor de manobras.

### Fase 5 — Protocolo v1 + scripts de voo

**Status: script de pouso escrito, em teste no jogo.** No primeiro teste, em Kerbin, a freada terminou alta e a nave tocou o chão inclinada e tombou. Corrigido: o pé agora é medido pelas pernas do trem. No segundo teste o pé ficou certo (0,4 m de erro no toque), mas a nave balançou até 31° na freada: o piloto automático do kRPC não segurava a nave. Agora quem aponta a nave é o SAS do KSP (falta testar de novo). [`scripts/pouso.py`](scripts/pouso.py) faz a queima de suicídio numa descida vertical, em qualquer planeta, contando o arrasto do ar; roda pela linha de comando enquanto o botão não existe. [`scripts/tests/test_pouso.py`](scripts/tests/test_pouso.py) testa a mesma guiagem numa nave simulada, sem o KSP, em planetas com e sem atmosfera.

- Migrar para o protocolo binário (COBS + CRC).
- Chave "ARM" + botão "SUICIDE BURN" que dispara o script de pouso autônomo no computador de bordo.
- Chave "ARM" + botão "EXEC" que executa o nó de manobra da fase 4: aponta a nave para o nó, acelera o tempo até perto dele, queima e corta quando o Δv restante chega a zero.
- Painel e tela mostram o estado do script (armado, queimando, pousado, abortado). O pouso e o EXEC já seguem a [base comum dos scripts](#base-comum).
- Os outros scripts (piloto automático de avião, subida até a órbita, pouso de precisão...) estão em [Scripts de voo](#scripts-de-voo) e não entram no critério desta fase.

**Pronto quando:** um booster pousa sozinho a partir de um botão no painel, e um nó de manobra é executado pelo botão EXEC.

### Fase 6 — Tela multifunção (mikromedia for ARM)

Placa da MikroElektronika com **NXP LPC2148** (ARM7TDMI-S, 60 MHz, 512 KB de flash, 32 KB de RAM), tela 320x240 com touch resistivo, microSD, saída de áudio e carregador de Li-Po. Aqui o firmware é escrito **sem framework**: C, registradores, script de linker e código de inicialização próprios.

**Status: simulador pronto, firmware não começado.** A tela já roda num simulador no PC e no navegador do celular, pelo Wi-Fi, com navball, números e botões de toque, falando o protocolo que a placa vai usar: [docs/mfd.md](docs/mfd.md). A placa ainda não conversa com o PC: o cabo mini-USB antigo falha nos dados.

- **Antes de começar:** achar o manual e o esquemático da placa (site da MikroE) para confirmar o controlador da tela, os pinos da tela e do touch e o chip de áudio. Já se sabe que a placa tem duas mini-USB: a **USB** vai direto no LPC2148, e a **PROG** tem um conversor USB-serial **FT232RL**. É pela PROG que o PC conversa com a placa.
- **Ferramentas:** `arm-none-eabi-gcc` + `make`. Gravação pelo bootloader serial de fábrica do LPC2148, com `lpc21isp` ou Flash Magic — provavelmente pela PROG (FT232RL), sem precisar de gravador. Antes de gravar, guardar o `.hex` do demo de fábrica, se a MikroE oferecer: gravar um programa novo apaga o demo.
- **Passos:**
  1. Piscar um LED: código de inicialização, script de linker, configuração do PLL.
  2. Serial: eco de caracteres; depois, receber o protocolo da tela ([docs/protocolo.md](docs/protocolo.md#tela-multifunção-mikromedia)), em texto como o simulador, e mais tarde o v1.
  3. Driver da tela: inicializar o controlador, desenhar pixels, retângulos e texto com fonte bitmap. Com 32 KB de RAM não cabe um *framebuffer* (320×240×2 = 150 KB), então o desenho vai direto para a memória do controlador da tela, atualizando só o que mudou.
  4. Touch: leitura pelo ADC e calibração.
  5. Páginas: a navball do simulador primeiro (a conta está em `bridge/navball.py`, pronta para virar C); depois mapa da órbita, dados de pouso, informações, uma página para cada módulo do painel que precisa de números (a começar pelo editor de nós de manobra) e uma roda de modos do SAS. Troca de página pelo touch e pela ponte, que abre a página do módulo em uso e volta depois.
  6. Áudio: alarmes e avisos gravados no microSD (combustível baixo, contagem de altitude no pouso).

**Pronto quando:** a mikromedia mostra telemetria ao vivo recebida do Pi e toca um alarme de combustível baixo.

### Fase 7 — Hardware definitivo

- PCB no **KiCad** a partir dos esquemáticos de [hardware/](hardware/README.md): uma placa de módulo, fabricada em quantidade, e o backplane. Fabricação na JLCPCB, PCBWay…
- Caixa em MDF cortado a laser (no colégio), com peças impressas em 3D (em casa): um painel removível por seção, legendas gravadas, korry switches, Pi e mikromedia embutidos. Formato, aparência e ordem para construir em [hardware/construcao.md](hardware/construcao.md).

### Fase 8 — Embarcados avançado (opcional)

- Painéis modulares, cada um com seu micro, falando com um mestre via I2C, RS-485 ou CAN.
- Painel sem fio com **ESP32**.
- Reescrever o firmware do Mega sem o framework Arduino (registradores do AVR) ou migrar para RP2040 (Raspberry Pi Pico) com o C SDK ou Rust + Embassy.

---

## Scripts de voo

Scripts que pilotam a nave, ou ajudam o piloto a pilotar, disparados pelo painel e acompanhados na tela. O primeiro é o pouso autônomo da [fase 5](#fase-5--protocolo-v1--scripts-de-voo) ([`scripts/pouso.py`](scripts/pouso.py)); o segundo, o [fly by wire de avião](#fly-by-wire-de-avião) ([`scripts/fbw.py`](scripts/fbw.py)). Os outros desta seção são ideias ainda sem código e sem ordem: cada um entra no roteiro quando o hardware de que precisa existir.

Os scripts ficam em [`scripts/`](scripts/), fora da ponte: cada um roda sozinho pela linha de comando, no PC ou no Pi, mesmo sem o painel. No cockpit, a ponte só dispara o script pelo botão e mostra o estado dele no painel e na tela. Os testes, com naves simuladas e sem o KSP, ficam em `scripts/tests/`.

### Base comum

- **Um script ativo por vez.** No cockpit, liga com a chave ARM + o botão do script. ABORT, ou mexer no joystick, devolve o controle ao piloto na hora.
- O painel e a tela mostram o estado do script (armado, ativo, terminado, abortado). Como nos outros LEDs, o LED mostra o que o script está fazendo, não o botão que foi apertado.
- **Guiagem separada do kRPC**, como em `pouso.py`: recebe uma leitura da nave e devolve comandos. Assim ela é testada numa nave simulada, sem o KSP, antes de ir para o jogo.
- **Diretor de voo:** todo script pode rodar no automático ou só como guia. No modo guia, a tela mostra para onde apontar e quanto acelerar, e o piloto voa pelo joystick. Serve para testar a guiagem sem entregar a nave e para aprender a pilotar junto.

### Fly by wire de avião

**Status: script escrito e testado num avião simulado; falta testar no jogo.** Roteiro de testes, ajuste dos ganhos e problemas comuns em [docs/fbw.md](docs/fbw.md).

Como nos aviões da Airbus, o manche não mexe nas superfícies: ele diz para onde o piloto quer ir. [`scripts/fbw.py`](scripts/fbw.py) lê o joystick (o Extreme 3D Pro, ou um controle de Xbox) e pilota o avião pelo kRPC.

- **O ponto do FBW:** o manche move um ponto na navball, um rumo e um ângulo de subida, e o avião voa até o pró-grado ficar em cima dele. Soltando o manche, o ponto fica onde está. Com o manche solto e o ponto perto do horizonte, o avião trava a altitude.
- **Proteções:** asas até 60° (menos se a asa não aguenta: a curva abre em vez de o avião descer), subida entre −30° e +30° e ângulo de ataque até 15°.
- **Lei direta** no chão e com o botão do FBW desligado: o manche vai direto para as superfícies. O FBW assume 1 s depois da decolagem.
- **O acelerador fica com o piloto.** O acelerador automático (SPD) já existe por dentro, ainda sem interface.
- **Na tela:** o ponto aparece na navball da [tela multifunção](docs/mfd.md), como os quatro cantos verdes de um quadrado. Com o avião no ponto, o pró-grado fica dentro dele.
- **Por dentro, três camadas:** a diferença entre o ponto e o pró-grado vira inclinação das asas e carga (g); a carga e a inclinação viram velocidades de giro; os giros viram superfícies, com o ganho dividido pela autoridade do avião.

**Pronto quando:** um avião decola na lei direta e, com o FBW, voa reto, faz curvas, sobe e desce só pelo ponto, sem balançar.

### Piloto automático de avião

Inspirado no painel de piloto automático dos aviões de linha (o MCP do Boeing, o FCU do Airbus).

- **Modos**, cada um ligado e desligado pelo seu botão:
  - **HDG:** vira para o rumo escolhido e segura.
  - **ALT:** segura a altitude escolhida.
  - **V/S:** sobe ou desce com a velocidade vertical escolhida. Com o ALT ligado junto, nivela ao chegar na altitude escolhida.
  - **SPD:** acelerador automático, segura a velocidade escolhida.
  - Sem HDG ligado, mantém as asas niveladas.
- **No painel:**
  - Um encoder por valor: rumo, altitude, velocidade vertical e velocidade. Lidos como os encoders da [fase 4](#fase-4--instrumentos-físicos); apertar o encoder troca o passo.
  - Os valores escolhidos em displays de 7 segmentos (MAX7219).
  - Um botão com LED por modo. O LED acende quando o modo assumiu no jogo, não quando o botão é apertado.
- **Na tela:** os modos ligados e os valores escolhidos. Para onde o avião vai já aparece na navball: é o ponto do FBW.
- **Antes dos encoders existirem:** botões de + e − na tela do celular, que já manda toques para a ponte (`TOQUE <nome>`).
- **Por dentro:** o piloto automático fica por cima do [fly by wire](#fly-by-wire-de-avião) e só mexe no ponto, como um piloto que não cansa:
  - HDG põe o rumo do ponto no rumo escolhido; sem HDG, o ponto fica no rumo em que o avião está;
  - ALT e V/S mexem no ângulo de subida do ponto (o FBW já trava a altitude com o ponto no horizonte);
  - SPD liga o acelerador automático que já existe no `fbw.py`;
  - as proteções do FBW continuam valendo, e mexer no manche devolve o ponto ao piloto.
- **Precisa de:** 4 encoders e displays como os da fase 4. Para começar, só o celular.

**Pronto quando:** um avião decola na mão, e o piloto automático leva ele até a altitude e o rumo escolhidos no painel e segura lá.

### Rover com controle de cruzeiro

- Os mesmos botões e encoders HDG e SPD do avião, e o mesmo PID: segura a velocidade e o rumo no chão, pelo acelerador e pela direção das rodas (`control.wheel_throttle` e `control.wheel_steering`).
- Freia nas descidas, para não passar da velocidade escolhida.
- Sai quase de graça depois do piloto automático de avião.

### Subida até a órbita

- O piloto escolhe a altitude da órbita e a inclinação nos encoders e aperta ARM + LAUNCH.
- O script decola, faz a curva de gravidade, solta os estágios quando o combustível acaba e corta o motor quando o apoastro chega na altitude escolhida.
- No apoastro, circulariza com um nó de manobra executado pelo EXEC da fase 5.
- Junto com o pouso, fecha o ciclo: do chão até a órbita e de volta.

### Pouso de precisão (volta à base)

O pouso da SpaceX completo. O `pouso.py` desce na vertical onde a nave estiver; aqui o booster volta para um lugar escolhido, como a plataforma do KSC.

- **Queima de retorno** logo depois da separação: vira a nave e queima até a trajetória cair no alvo.
- **Queima de reentrada**, para chegar mais devagar nas camadas grossas da atmosfera.
- Na descida, as aletas corrigem a trajetória para o alvo.
- Termina com a queima de suicídio do `pouso.py`, com a mira puxando para o alvo em vez de só anular a deriva.
- É o mais difícil da lista: precisa prever onde a trajetória cai, com arrasto, como o `pouso.py` já faz na vertical.

### Rendezvous

Levar a nave até perto de outra em órbita. O script **não pilota até a última etapa**: ele cria nós de manobra, que o piloto confere e ajusta no editor da [fase 4](#fase-4--instrumentos-físicos) e o EXEC da fase 5 executa. Assim a parte de planejar e a parte de queimar ficam separadas, e cada uma é testada sozinha.

- **As etapas**, cada uma um nó novo:
  1. **Igualar o plano:** nó no nodo ascendente ou descendente em relação ao alvo, queima na direção normal de Δv = 2·v·sen(Δi/2). Conta fechada; o kRPC dá a inclinação relativa e onde fica o nodo (`relative_inclination`, `true_anomaly_at_an`).
  2. **Transferência:** a conta pesada, feita como no pouso, prevendo e ajustando. Para cada momento de queima ao longo de uma volta, calcula a queima pró-grado que leva o apoastro até a órbita do alvo, prevê as duas órbitas e mede a menor distância entre as naves. Fica com o melhor momento e refina por bisseção. Sem motor, as órbitas seguem as leis de Kepler: a previsão é exata, sem o arrasto que complica o pouso.
  3. **Igualar a velocidade:** nó no momento da menor distância, com a queima igual à diferença entre a velocidade do alvo e a da nave nesse instante.
  4. **Aproximação final**, sem nó: aponta para o alvo, se aproxima com uma velocidade que cai com a distância, anula a deriva para os lados e para a uns 50–100 m. Dali segue o acoplamento assistido.
- **Automático ou diretor de voo:** no automático, o script encadeia as etapas e acelera o tempo entre elas (`warp_to`). Como diretor de voo, ele só propõe cada nó e o piloto ajusta e executa.
- **Na página do editor de manobras, na tela multifunção:** a menor distância prevista até o alvo, quando ela acontece e a velocidade relativa nesse ponto, atualizadas enquanto o encoder e o TEMPO mexem no nó.
- **Ordem para fazer**, do mais simples ao mais difícil:
  1. Só mostrar a menor distância prevista enquanto o piloto edita os nós na mão. Sem automação, e já é como se faz rendezvous "de olho" no KSP.
  2. Os nós de igualar o plano e igualar a velocidade, que são contas fechadas.
  3. A busca da transferência.
  4. A aproximação final e a passagem para o acoplamento.
- **A decidir:**
  - Quem prevê as órbitas: o kRPC calcula a aproximação com um nó criado, mas cada pergunta vai pela rede, e a busca faz dezenas delas. Uma previsão própria (resolver a equação de Kepler, umas 30 linhas) é rápida e testável sem o KSP. A ideia é a própria, conferida contra a do kRPC.
  - Queimas longas: o EXEC tem que começar metade da queima antes do nó, senão o encontro erra por quilômetros. Vale para todo nó, então fica no EXEC.
- **Precisa de:** o editor de manobras (fase 4) e o EXEC (fase 5). A etapa 1 da ordem só precisa da tela.

### Acoplamento assistido

- Página nova na tela multifunção: a mira de alinhamento com a porta de acoplamento do alvo, a distância e a velocidade de aproximação.
- A chave de modo do joystick na posição TRANSLAÇÃO: o manche move a nave com o RCS, sem girar ([os três modos](hardware/construcao.md#um-joystick-três-modos)).
- Primeiro manual, com a tela ajudando. Depois automático: a nave se alinha e se aproxima devagar sozinha.
- **Precisa de:** joystick (fase 2) e a tela multifunção.

---

## Lista de compras

Itens marcados já estão na bancada. Compre por fase — não precisa tudo de uma vez. AliExpress costuma ser mais barato (e lento); Mercado Livre e lojas nacionais chegam mais rápido.

> **Atenção à tensão:** o Mega trabalha em 5V; o Pi, em 3,3V. Nunca ligue um pino do Pi direto em 5V — a comunicação entre os dois é pela USB.

### Ferramentas (uma vez só)

- [ ] Ferro de solda com controle de temperatura + estanho + malha dessoldadora
- [ ] Multímetro
- [ ] Alicate de corte e decapador de fios
- [x] Impressora 3D (em casa)
- Corte a laser: no colégio
- [ ] Paquímetro (para medir as peças antes de desenhar os furos dos painéis)

### Fases 0–1 — Kit inicial

- [x] Arduino Mega 2560 (também tem Uno e Nano)
- [x] Raspberry Pi 4
- [x] Botões
- [ ] Fonte para o Pi 4: 5,1V 3A USB-C de boa qualidade (fonte fraca causa travamentos)
- [ ] Dissipador ou case com ventoinha (o Pi 4 esquenta, principalmente dentro de uma caixa fechada)
- [x] Cartão microSD de 16 GB ou mais (classe A1)
- [x] Cabo USB-B para ligar o Mega no Pi
- [x] 2× protoboard de 830 pontos
- [x] Jumpers macho-macho e macho-fêmea
- [x] Kit de LEDs 5 mm + kit de resistores (220 Ω–10 kΩ)
- [x] LCD 16x2 ou 20x4 com módulo I2C (só para a fase 1; opcional se já tiver)

### Fase 2 — Painel de controle

- [x] 10–15× chaves alavanca (toggle) ON-OFF
- [x] 2–3× capas de proteção para chave ("missile switch cover")
- [x] 4–6× botões arcade (24 ou 30 mm), de preferência com LED
- [ ] Por módulo pequeno (6 no painel): 2× 74HC165, 1× 74HC595, 2× rede resistiva 10 kΩ SIP 9 pinos, 1× chave DIP de 8 vias, 8× resistor 1 kΩ, 3× capacitor 100 nF, 1× capacitor 10 µF, 3 soquetes DIP-16, conector IDC 2x8 e cabo flat de 16 vias
- [ ] Por módulo médio (6 no painel): 3× 74HC165, 2× 74HC595, 3× rede resistiva 10 kΩ SIP 9 pinos, 1× chave DIP de 8 vias, 16× resistor 1 kΩ, 5× capacitor 100 nF, 1× capacitor 10 µF, 5 soquetes DIP-16, conector IDC 2x8 e cabo flat de 16 vias
- [ ] Por módulo grande (nenhum no painel por enquanto): 4× 74HC165, 2× 74HC595, 4× rede resistiva 10 kΩ SIP 9 pinos, 1× chave DIP de 8 vias, 16× resistor 1 kΩ, 6× capacitor 100 nF, 1× capacitor 10 µF, 6 soquetes DIP-16, conector IDC 2x8 e cabo flat de 16 vias
- [ ] Backplane: 12× conector IDC 2x8, 5× resistor 47 Ω, 13× resistor 10 kΩ, capacitores de 470 µF e 100 nF, borne de 2 vias e jumper de 3 pinos
- [x] Joystick: Logitech Extreme 3D Pro (3 eixos + acelerador, na USB do Pi)
- [ ] 1× potenciômetro deslizante 10 kΩ linear, curso ≥ 60 mm (opcional: só para uma alavanca de acelerador própria)
- [ ] Por korry switch ([lista completa](hardware/korry/README.md#lista-de-peças-um-korry)): 1 botão tátil 6 × 6 mm, até 2 LEDs difusos de alto brilho de 3 mm, plaquinha de 22 × 22 mm, conector de 4 vias; corpo impresso, tampa de acrílico leitoso de 3 mm
- [ ] Placas perfuradas + barras de pinos (headers)

### Fase 3 — Tela de telemetria

- **Tela do Pi: adiada** — decidir depois. Para desenvolver, qualquer monitor ou TV HDMI serve.
- [ ] Cabo ou adaptador **micro-HDMI → HDMI** (o Pi 4 só tem saída micro-HDMI)

### Fase 4 — Instrumentos físicos

- [ ] 3–4× módulos MAX7219 com 8 dígitos de 7 segmentos
- [ ] 2× encoders rotativos (KY-040), para escolher o que os displays mostram
- [ ] Editor de manobras ([peças e medidas](hardware/construcao.md#painel-do-editor-de-manobras)): 1× encoder EC11 com knob de alumínio de 30 mm; 1× chave rotativa de 1 polo e 12 posições, com anel de batente, e knob de ponteiro de 22 mm; 1× tecla basculante (*rocker*) com mola para o centro, (ON)-OFF-(ON), de 21 × 15 mm; 2× botões de metal de 12 mm sem trava; 6 korry (peças na fase 2)
- [ ] 1 botão para o MAPA, na seção da câmera, se não sobrar da fase 2
- [ ] 1× chave de 3 posições (ON-OFF-ON, sem mola) para o modo do joystick: VOO, CÂMERA e TRANSLAÇÃO
- [ ] 1 m de fita WS2812B (60 LEDs/m) + resistor 330 Ω + capacitor 1000 µF
- [ ] 2–4× motores de passo X27.168 (ponteiros)
- [ ] 1× fonte 5V 3A + conector/borne

### Fase 6 — Tela multifunção

- [x] mikromedia for ARM (LPC2148)
- [ ] Cabo mini-USB **com fios de dados**, para a PROG (o antigo alimenta a placa, mas o Windows não reconhece o FT232)
- [ ] Cartão microSD (para os sons de alarme)
- [ ] Fone ou caixinha de som com plugue P2
- [ ] Gravador JTAG compatível com ARM7 (opcional, só para depurar passo a passo)

### Fase 7 — Hardware definitivo

- [ ] PCBs fabricadas
- [ ] Conectores JST/dupont, parafusos e espaçadores M3
- [ ] Material da caixa: MDF 3 mm e acrílico 3 mm (preto ou branco leitoso) para a laser, filamento PLA, primer e tinta spray fosca
- [ ] Insertos roscados M3 (colocados a quente nas peças impressas) e pés de borracha
- [ ] Extensão USB de painel (para o joystick) e ventoinha 5 V de 40 mm (para o Pi dentro da caixa)

---

## Referências

- [kRPC — repositório](https://github.com/krpc/krpc) e [documentação](https://krpc.github.io/krpc/)
- [pySerial](https://pyserial.readthedocs.io/)
- [pygame](https://www.pygame.org/docs/)
- [Raspberry Pi — documentação](https://www.raspberrypi.com/documentation/)
- [Arduino — documentação](https://docs.arduino.cc/)
- [KiCad](https://www.kicad.org/)
- [LPC214x User Manual (UM10139)](https://www.nxp.com/docs/en/user-guide/UM10139.pdf) — referência de todos os registradores do LPC2148
- [Arm GNU Toolchain](https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads) (`arm-none-eabi-gcc`)
- [lpc21isp](https://sourceforge.net/projects/lpc21isp/) — gravação pelo bootloader serial do LPC2148
- Manual e esquemático da mikromedia for ARM: site da [MikroElektronika](https://www.mikroe.com/)
- Bibliotecas úteis para o firmware: `LiquidCrystal_I2C`, `LedControl` (MAX7219), `FastLED` ou `Adafruit_NeoPixel` (WS2812), `SwitecX25` (X27.168)
