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
   • tela de telemetria (pygame)
          ▲                              ▲
          │ USB/serial                   │ USB/serial
          │ (protocolo próprio)          │ (mesmo protocolo)
          ▼                              ▼
 Arduino Mega = I/O do painel     mikromedia (LPC2148) = tela multifunção
 firmware/painel/                 firmware/mfd/
          ▲
          │  pinos, I2C, SPI
          ▼
 Painel: chaves, LEDs, joystick,
 displays de 7 segmentos, ponteiros
```

Cada parte tem um papel bem definido:

| Parte | Responsabilidade | Não faz |
|---|---|---|
| **KSP + kRPC** (PC) | Expõe o estado da nave e aceita comandos. | — |
| **Computador de bordo** (Raspberry Pi 4, Python) | Conecta no kRPC pela rede, abre *streams* de telemetria, traduz eventos do painel em comandos do jogo e telemetria em mensagens para o painel. Desenha a tela de telemetria. Dispara scripts (ex.: pouso autônomo). | Não lê pino nenhum. |
| **Painel** (Arduino Mega, C++) | Lê entradas (com debounce), envia eventos; recebe valores e atualiza LEDs, displays e ponteiros. | **Não sabe que o KSP existe.** É um painel de I/O genérico. |
| **Tela multifunção** (mikromedia for ARM, LPC2148, C sem framework) | Recebe telemetria pelo mesmo protocolo serial, desenha páginas (atitude, órbita, pouso), troca de página pelo touch e toca alarmes sonoros. | Não fala com o kRPC; só mostra o que o computador de bordo manda. |

Durante o desenvolvimento, o mesmo código Python roda no PC — só muda o endereço do servidor kRPC e a porta serial.

### Princípios

- **O LED mostra o estado do jogo, não a posição da chave.** A chave só avisa para onde foi ("SAS para cima"); o computador de bordo decide o que fazer e o jogo confirma. Assim o painel nunca fica dessincronizado (ex.: SAS desligado pelo jogo).
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
| **mikromedia for ARM (LPC2148)** como tela multifunção | Já está na bancada. ARM programado sem framework, com tela touch, microSD e áudio. Entra depois do protocolo v1, que ela também usa. |
| **ESP32** fica para depois | Candidato a painel sem fio ou módulo extra (fase 8). |

### Estrutura planejada do repositório

```
bridge/           computador de bordo em Python: ponte kRPC ⇄ serial, tela de telemetria, scripts de voo
firmware/painel/  Arduino Mega (Arduino IDE ou PlatformIO)
firmware/passos/  sketches de aprendizado, um por passo da fase 1
firmware/mfd/     mikromedia for ARM / LPC2148 (C, GCC e make)
hardware/         esquemáticos e PCBs (KiCad), desenhos da caixa
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

**Status: em andamento.** Chaves, botões e LEDs estão prontos para montar: pinagem, código e testes em [docs/fase2.md](docs/fase2.md). Joystick e acelerador aguardam o hardware.

- Chaves para SAS, RCS, trem de pouso, luzes e freios; STAGE e ABORT com capa de proteção. Depois, action groups.
- A posição da chave é o estado desejado (para cima = ligado); o LED de cada sistema mostra o estado no jogo.
- Tudo direto nos pinos do Mega, que sobram para esta fase. Shift registers (74HC165 para entradas, 74HC595 para LEDs) **ou** MCP23017 (I2C) ficam para quando os pinos acabarem. Opcional: matriz de botões com diodos.
- Joystick de 3 eixos + potenciômetro deslizante para o acelerador (aguardando o hardware).

**Pronto quando:** dá para lançar e colocar um foguete em órbita usando só o painel.

### Fase 3 — Tela de telemetria

- Interface em pygame no Pi: altitude, velocidades, apoapse/periapse, tempo até Ap/Pe, combustível e delta-v por estágio.
- Depois: gráfico de altitude × tempo, desenho simples da órbita, indicador de atitude.
- O Pi 4 tem folga de desempenho, mas vale o bom hábito: redesenhar só o que mudou e limitar a taxa de quadros.
- A tela definitiva do Pi foi adiada. Enquanto isso, desenvolver com qualquer monitor ou TV HDMI (ou rodando a interface no PC).

**Pronto quando:** dá para circularizar uma órbita olhando só para a tela.

### Fase 4 — Instrumentos físicos

- Displays de 7 segmentos com MAX7219 para os números mais importantes.
- Encoder rotativo para escolher o que cada display mostra.
- **Editor de nós de manobra** (pelo kRPC: `control.add_node`, `node.prograde` etc.):
  - 4 encoders: pró-grado, normal, radial e tempo (mover o nó ao longo da órbita). Apertar o encoder troca o passo: 0,1 / 1 / 10 / 100 m/s por clique.
  - Botões NOVO, APAGAR, AP e PE (levar o nó ao apoastro ou ao periastro) e CIRC (nó de circularização no apoastro, com o Δv calculado pela ponte).
  - O LCD mostra Δv, tempo de queima, T− até o nó e o Ap/Pe resultante.
  - Encoders lidos **por interrupção** (externa ou *pin change*): redesenhar o LCD trava o laço por ~20 ms, e o *polling* perderia cliques. O painel acumula os cliques e manda `ENC <nome> <cliques>`.
- Barra de combustível com LEDs WS2812.
- Ponteiro analógico com motor de passo X27.168.
- Fonte 5V externa (a USB não aguenta muitos LEDs).

**Pronto quando:** um voo inteiro (lançamento → órbita → reentrada) é feito sem olhar para o monitor do PC, inclusive planejar a circularização pelo editor de manobras.

### Fase 5 — Protocolo v1 + scripts de voo

- Migrar para o protocolo binário (COBS + CRC).
- Chave "ARM" + botão "SUICIDE BURN" que dispara o script de pouso autônomo no computador de bordo.
- Chave "ARM" + botão "EXEC" que executa o nó de manobra da fase 4: aponta a nave para o nó, acelera o tempo até perto dele, queima e corta quando o Δv restante chega a zero.
- Painel e tela mostram o estado do script (armado, queimando, pousado, abortado).

**Pronto quando:** um booster pousa sozinho a partir de um botão no painel, e um nó de manobra é executado pelo botão EXEC.

### Fase 6 — Tela multifunção (mikromedia for ARM)

Placa da MikroElektronika com **NXP LPC2148** (ARM7TDMI-S, 60 MHz, 512 KB de flash, 32 KB de RAM), tela 320x240 com touch resistivo, microSD, saída de áudio e carregador de Li-Po. Aqui o firmware é escrito **sem framework**: C, registradores, script de linker e código de inicialização próprios.

- **Antes de começar:** achar o manual e o esquemático da placa (site da MikroE) para confirmar o controlador da tela, o chip de áudio e qual mini-USB está ligada à serial do LPC2148.
- **Ferramentas:** `arm-none-eabi-gcc` + `make`. Gravação pelo bootloader serial de fábrica do LPC2148, com `lpc21isp` ou Flash Magic — provavelmente pela mini-USB com LEDs RX/TX, sem precisar de gravador.
- **Passos:**
  1. Piscar um LED: código de inicialização, script de linker, configuração do PLL.
  2. Serial: eco de caracteres; depois, receber o protocolo v1.
  3. Driver da tela: inicializar o controlador, desenhar pixels, retângulos e texto com fonte bitmap. Com 32 KB de RAM não cabe um *framebuffer* (320×240×2 = 150 KB), então o desenho vai direto para a memória do controlador da tela, atualizando só o que mudou.
  4. Touch: leitura pelo ADC e calibração.
  5. Páginas: indicador de atitude, mapa da órbita, dados de pouso; troca de página pelo touch.
  6. Áudio: alarmes e avisos gravados no microSD (combustível baixo, contagem de altitude no pouso).

**Pronto quando:** a mikromedia mostra telemetria ao vivo recebida do Pi e toca um alarme de combustível baixo.

### Fase 7 — Hardware definitivo

- Esquemático e PCB no **KiCad**; fabricação (JLCPCB, PCBWay…).
- Caixa impressa em 3D ou MDF cortado a laser, painel com legendas, Pi e mikromedia embutidos.

### Fase 8 — Embarcados avançado (opcional)

- Painéis modulares, cada um com seu micro, falando com um mestre via I2C, RS-485 ou CAN.
- Painel sem fio com **ESP32**.
- Reescrever o firmware do Mega sem o framework Arduino (registradores do AVR) ou migrar para RP2040 (Raspberry Pi Pico) com o C SDK ou Rust + Embassy.

---

## Lista de compras

Itens marcados já estão na bancada. Compre por fase — não precisa tudo de uma vez. AliExpress costuma ser mais barato (e lento); Mercado Livre e lojas nacionais chegam mais rápido.

> **Atenção à tensão:** o Mega trabalha em 5V; o Pi, em 3,3V. Nunca ligue um pino do Pi direto em 5V — a comunicação entre os dois é pela USB.

### Ferramentas (uma vez só)

- [ ] Ferro de solda com controle de temperatura + estanho + malha dessoldadora
- [ ] Multímetro
- [ ] Alicate de corte e decapador de fios

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
- [ ] 3× 74HC165 + 3× 74HC595 **ou** 2× MCP23017 (só quando os pinos do Mega acabarem)
- [ ] Capacitores cerâmicos de 100 nF (desacoplamento, um por CI; junto com os CIs acima)
- [ ] Diodos 1N4148 (se fizer matriz de botões)
- [ ] 1× joystick de 3 eixos (ou módulo de 2 eixos KY-023 para começar)
- [ ] 1× potenciômetro deslizante 10 kΩ linear, curso ≥ 60 mm
- [ ] Placas perfuradas + barras de pinos (headers)

### Fase 3 — Tela de telemetria

- **Tela do Pi: adiada** — decidir depois. Para desenvolver, qualquer monitor ou TV HDMI serve.
- [ ] Cabo ou adaptador **micro-HDMI → HDMI** (o Pi 4 só tem saída micro-HDMI)

### Fase 4 — Instrumentos físicos

- [ ] 3–4× módulos MAX7219 com 8 dígitos de 7 segmentos
- [ ] 6× encoders rotativos (KY-040): 4 para o editor de manobras, 2 para escolher o que os displays mostram
- [ ] 5× botões para o editor de manobras (NOVO, APAGAR, AP, PE, CIRC), se não sobrarem da fase 2
- [ ] 1 m de fita WS2812B (60 LEDs/m) + resistor 330 Ω + capacitor 1000 µF
- [ ] 2–4× motores de passo X27.168 (ponteiros)
- [ ] 1× fonte 5V 3A + conector/borne

### Fase 6 — Tela multifunção

- [x] mikromedia for ARM (LPC2148)
- [ ] Cabo mini-USB
- [ ] Cartão microSD (para os sons de alarme)
- [ ] Fone ou caixinha de som com plugue P2
- [ ] Gravador JTAG compatível com ARM7 (opcional, só para depurar passo a passo)

### Fase 7 — Hardware definitivo

- [ ] PCBs fabricadas
- [ ] Conectores JST/dupont, parafusos e espaçadores M3
- [ ] Material da caixa (filamento ou MDF 3 mm)

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
