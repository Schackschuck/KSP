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
 Raspberry Pi 4 = computador de bordo ..... bridge/
   • ponte kRPC ⇄ painel
   • tela de telemetria (pygame)
          ▲
          │  USB/serial (protocolo próprio)
          ▼
 Arduino Mega = I/O do painel ............. firmware/
          ▲
          │  pinos, I2C, SPI
          ▼
 Painel: chaves, LEDs, joystick, displays de 7 segmentos, ponteiros
```

Cada parte tem um papel bem definido:

| Parte | Responsabilidade | Não faz |
|---|---|---|
| **KSP + kRPC** (PC) | Expõe o estado da nave e aceita comandos. | — |
| **Computador de bordo** (Raspberry Pi 4, Python) | Conecta no kRPC pela rede, abre *streams* de telemetria, traduz eventos do painel em comandos do jogo e telemetria em mensagens para o painel. Desenha a tela de telemetria. Dispara scripts (ex.: pouso autônomo). | Não lê pino nenhum. |
| **Firmware** (Arduino Mega, C++) | Lê entradas (com debounce), envia eventos; recebe valores e atualiza LEDs, displays e ponteiros. | **Não sabe que o KSP existe.** É um painel de I/O genérico. |

Durante o desenvolvimento, o mesmo código Python roda no PC — só muda o endereço do servidor kRPC e a porta serial.

### Princípios

- **O LED mostra o estado do jogo, não a posição da chave.** A chave só envia "mudei"; o computador de bordo decide o que fazer e o jogo confirma. Assim o painel nunca fica dessincronizado (ex.: SAS desligado pelo jogo).
- **Protocolo serial em duas versões:**
  - **v0 — texto**, uma mensagem por linha. Fácil de depurar no Serial Monitor.
    ```
    Pi → placa:  ALT 12345      SAS 1      FUEL 73
    placa → Pi:  BTN STAGE 1    SW SAS 0   AX PITCH -312
    ```
  - **v1 — binário**, com enquadramento [COBS](https://en.wikipedia.org/wiki/Consistent_Overhead_Byte_Stuffing), ID de mensagem e CRC. Mais rápido e robusto; vem quando a v0 começar a apertar.
- **Entradas analógicas** (joystick, acelerador) são enviadas a uma taxa fixa, com zona morta e filtro; **entradas digitais** são enviadas só quando mudam.

### Decisões

| Decisão | Por quê |
|---|---|
| **kRPC** em vez de mods de serial (Kerbal Simpit etc.) | Acesso a praticamente tudo do jogo (órbita, estágios, delta-v, autopilot) e permite scripts de voo. A ferramenta não deve ser o limite. |
| **Ponte fora do microcontrolador** em vez do cliente kRPC C-nano | kRPC completo com *streams*; o firmware fica simples e ganha um protocolo próprio — que é onde está o aprendizado de embarcados. |
| **Python** na ponte | Já usado com kRPC antes; o mesmo código roda no PC e no Pi. |
| **Raspberry Pi 4** como computador de bordo | Liga uma tela colorida de verdade sem esforço e deixa o cockpit independente do PC (só um cabo de rede). |
| **Arduino Mega** para o I/O | O Pi não tem entradas analógicas e o Linux não é tempo real; o Mega tem muitos pinos, trabalha em 5V e é compatível com praticamente todo módulo. |
| **ESP32** fica para depois | Candidato a painel sem fio ou módulo extra (fase 7). |

### Estrutura planejada do repositório

```
bridge/     computador de bordo em Python: ponte kRPC ⇄ serial, tela de telemetria, scripts de voo
firmware/   código da placa (Arduino IDE ou PlatformIO)
hardware/   esquemáticos e PCBs (KiCad), desenhos da caixa
docs/       protocolo serial, pinagem, anotações
```

---

## Roteiro

Cada fase termina com algo funcionando de ponta a ponta. Não pule o critério de "pronto".

### Fase 0 — Ambiente

**No PC:**

- Instalar KSP 1.12.x e o **kRPC** (via CKAN ou manualmente).
- No jogo, abrir a janela do kRPC e iniciar o servidor (dica: ativar *auto-start* e *auto-accept* nas configurações).
- Nas configurações do servidor, trocar o endereço de `localhost` para aceitar conexões da rede, e liberar no firewall do Windows as portas do kRPC (padrão: 50000 e 50001).
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

**Pronto quando:** o script roda **no Pi** e imprime a altitude ao vivo enquanto o foguete sobe no PC.

### Fase 1 — Primeiro circuito fechado

- Mega ligado no Pi (ou no PC) pela USB.
- 1 botão (STAGE), 1 LED (SAS) e a altitude num LCD 16x2/20x4 que você já tenha (é só para o teste).
- Protocolo **v0 (texto)**.
- Aprende: pull-up, debounce, leitura/escrita serial, laço principal sem `delay()`.

**Pronto quando:** apertar o botão faz *stage*, o LED acompanha o SAS do jogo e o LCD mostra a altitude.

### Fase 2 — Painel de controle

- Chaves para SAS, RCS, trem de pouso, luzes, freios, action groups; STAGE e ABORT com capa de proteção.
- LEDs de estado vindos do jogo.
- Expandir I/O com shift registers (74HC165 para entradas, 74HC595 para LEDs) **ou** MCP23017 (I2C). Opcional: matriz de botões com diodos.
- Joystick de 3 eixos + potenciômetro deslizante para o acelerador.

**Pronto quando:** dá para lançar e colocar um foguete em órbita usando só o painel.

### Fase 3 — Tela de telemetria

- Interface em pygame no Pi: altitude, velocidades, apoapse/periapse, tempo até Ap/Pe, combustível e delta-v por estágio.
- Depois: gráfico de altitude × tempo, desenho simples da órbita, indicador de atitude.
- O Pi 4 tem folga de desempenho, mas vale o bom hábito: redesenhar só o que mudou e limitar a taxa de quadros.

**Pronto quando:** dá para circularizar uma órbita olhando só para a tela.

### Fase 4 — Instrumentos físicos

- Displays de 7 segmentos com MAX7219 para os números mais importantes.
- Encoder rotativo para escolher o que cada display mostra.
- Barra de combustível com LEDs WS2812.
- Ponteiro analógico com motor de passo X27.168.
- Fonte 5V externa (a USB não aguenta muitos LEDs).

**Pronto quando:** um voo inteiro (lançamento → órbita → reentrada) é feito sem olhar para o monitor do PC.

### Fase 5 — Protocolo v1 + scripts de voo

- Migrar para o protocolo binário (COBS + CRC).
- Chave "ARM" + botão "SUICIDE BURN" que dispara o script de pouso autônomo no computador de bordo.
- Painel e tela mostram o estado do script (armado, queimando, pousado, abortado).

**Pronto quando:** um booster pousa sozinho a partir de um botão no painel.

### Fase 6 — Hardware definitivo

- Esquemático e PCB no **KiCad**; fabricação (JLCPCB, PCBWay…).
- Caixa impressa em 3D ou MDF cortado a laser, painel com legendas, Pi e tela embutidos.

### Fase 7 — Embarcados avançado (opcional)

- Painéis modulares, cada um com seu micro, falando com um mestre via I2C, RS-485 ou CAN.
- Painel sem fio com **ESP32**.
- Reescrever o firmware sem o framework Arduino (registradores do AVR) ou migrar para RP2040 (Raspberry Pi Pico) com o C SDK ou Rust + Embassy.

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
- [ ] Cartão microSD de 16 GB ou mais (classe A1)
- [ ] Cabo USB-B para ligar o Mega no Pi
- [ ] 2× protoboard de 830 pontos
- [ ] Jumpers macho-macho e macho-fêmea
- [ ] Kit de LEDs 5 mm + kit de resistores (220 Ω–10 kΩ)
- [ ] LCD 16x2 ou 20x4 com módulo I2C (só para a fase 1; opcional se já tiver)

### Fase 2 — Painel de controle

- [ ] 10–15× chaves alavanca (toggle) ON-OFF
- [ ] 2–3× capas de proteção para chave ("missile switch cover")
- [ ] 4–6× botões arcade (24 ou 30 mm), de preferência com LED
- [ ] 3× 74HC165 + 3× 74HC595 **ou** 2× MCP23017
- [ ] Capacitores cerâmicos de 100 nF (desacoplamento, um por CI)
- [ ] Diodos 1N4148 (se fizer matriz de botões)
- [ ] 1× joystick de 3 eixos (ou módulo de 2 eixos KY-023 para começar)
- [ ] 1× potenciômetro deslizante 10 kΩ linear, curso ≥ 60 mm
- [ ] Placas perfuradas + barras de pinos (headers)

### Fase 3 — Tela de telemetria

- [x] TFT (modelo a identificar — pode servir, dependendo do tipo)
- [ ] Se for comprar: tela **HDMI de 7" (1024x600)**, com ou sem touch, ou a tela oficial DSI de 7" do Raspberry Pi. Evitar telas SPI pequenas no Pi (lentas e trabalhosas de configurar).
- [ ] Cabo ou adaptador **micro-HDMI → HDMI** (o Pi 4 só tem saída micro-HDMI)

### Fase 4 — Instrumentos físicos

- [ ] 3–4× módulos MAX7219 com 8 dígitos de 7 segmentos
- [ ] 2× encoders rotativos (KY-040)
- [ ] 1 m de fita WS2812B (60 LEDs/m) + resistor 330 Ω + capacitor 1000 µF
- [ ] 2–4× motores de passo X27.168 (ponteiros)
- [ ] 1× fonte 5V 3A + conector/borne

### Fase 6 — Hardware definitivo

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
- Bibliotecas úteis para o firmware: `LiquidCrystal_I2C`, `LedControl` (MAX7219), `FastLED` ou `Adafruit_NeoPixel` (WS2812), `SwitecX25` (X27.168)
