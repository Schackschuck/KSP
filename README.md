# KSP Cockpit

Controle físico (painel + joystick + telemetria) para o **Kerbal Space Program 1**, feito do zero com hardware e software próprios.

O objetivo principal é **aprender firmware/embarcados e eletrônica**, e de quebra ter um cockpit de verdade — com direito a um botão que dispara um script de pouso autônomo estilo SpaceX.

---

## Arquitetura

```
 KSP 1 + servidor kRPC
          ▲
          │  TCP (protobuf)
          ▼
 Ponte em Python ................ bridge/
          ▲
          │  USB/serial (protocolo próprio)
          ▼
 Firmware (Arduino Mega) ........ firmware/
          ▲
          │  pinos, I2C, SPI
          ▼
 Painel: chaves, LEDs, displays, joystick
```

Cada parte tem um papel bem definido:

| Parte | Responsabilidade | Não faz |
|---|---|---|
| **KSP + kRPC** | Expõe o estado da nave e aceita comandos. | — |
| **Ponte (Python)** | Conecta no kRPC, abre *streams* de telemetria, traduz eventos do painel em comandos do jogo e telemetria em mensagens para o painel. Dispara scripts (ex.: pouso autônomo). | Não mexe em pino nenhum. |
| **Firmware** | Lê entradas (com debounce), envia eventos; recebe valores e atualiza LEDs, displays e ponteiros. | **Não sabe que o KSP existe.** É um painel de I/O genérico. |

### Princípios

- **O LED mostra o estado do jogo, não a posição da chave.** A chave só envia "mudei"; a ponte decide o que fazer e o jogo confirma. Assim o painel nunca fica dessincronizado (ex.: SAS desligado pelo jogo).
- **Protocolo serial em duas versões:**
  - **v0 — texto**, uma mensagem por linha. Fácil de depurar no Serial Monitor.
    ```
    PC → placa:  ALT 12345      SAS 1      FUEL 73
    placa → PC:  BTN STAGE 1    SW SAS 0   AX PITCH -312
    ```
  - **v1 — binário**, com enquadramento [COBS](https://en.wikipedia.org/wiki/Consistent_Overhead_Byte_Stuffing), ID de mensagem e CRC. Mais rápido e robusto; vem quando a v0 começar a apertar.
- **Entradas analógicas** (joystick, acelerador) são enviadas a uma taxa fixa, com zona morta e filtro; **entradas digitais** são enviadas só quando mudam.

### Estrutura planejada do repositório

```
bridge/     ponte em Python (kRPC ⇄ serial) e scripts de voo
firmware/   código da placa (Arduino IDE ou PlatformIO)
hardware/   esquemáticos e PCBs (KiCad), desenhos da caixa
docs/       protocolo serial, pinagem, anotações
```

---

## Roteiro

Cada fase termina com algo funcionando de ponta a ponta. Não pule o critério de "pronto".

### Fase 0 — Ambiente

- Instalar KSP 1.12.x e o **kRPC** (via CKAN ou manualmente).
- No jogo, abrir a janela do kRPC e iniciar o servidor (dica: ativar *auto-start* e *auto-accept* nas configurações).
- Instalar Python 3, `pip install krpc pyserial` e a Arduino IDE 2 (ou PlatformIO no VS Code).
- Se a placa for clone com chip CH340, instalar o driver CH340 no Windows.

```python
import time
import krpc

conn = krpc.connect(name="KSP Cockpit")
vessel = conn.space_center.active_vessel
altitude = conn.add_stream(getattr, vessel.flight(), "mean_altitude")

while True:
    print(f"{altitude():,.0f} m")
    time.sleep(0.1)
```

**Pronto quando:** o script imprime a altitude ao vivo enquanto o foguete sobe.

### Fase 1 — Primeiro circuito fechado

- 1 botão (STAGE), 1 LED (SAS), 1 LCD 20x4 I2C (altitude).
- Protocolo **v0 (texto)**.
- Aprende: pull-up, debounce, leitura/escrita serial, laço principal sem `delay()`.

**Pronto quando:** apertar o botão faz *stage*, o LED acompanha o SAS do jogo e o LCD mostra a altitude.

### Fase 2 — Painel de controle

- Chaves para SAS, RCS, trem de pouso, luzes, freios, action groups; STAGE e ABORT com capa de proteção.
- LEDs de estado vindos do jogo.
- Expandir I/O com shift registers (74HC165 para entradas, 74HC595 para LEDs) **ou** MCP23017 (I2C). Opcional: matriz de botões com diodos.
- Joystick de 3 eixos + potenciômetro deslizante para o acelerador.

**Pronto quando:** dá para lançar e colocar um foguete em órbita usando só o painel.

### Fase 3 — Telemetria

- Displays de 7 segmentos com MAX7219: altitude, apoapse, periapse, velocidade vertical, tempo até Ap.
- Encoder rotativo para escolher o que cada display mostra.
- Barra de combustível com LEDs WS2812.
- Ponteiro analógico com motor de passo X27.168.
- Fonte 5V externa (a USB não aguenta muitos LEDs).

**Pronto quando:** dá para circularizar uma órbita olhando só para o painel.

### Fase 4 — Protocolo v1 + scripts de voo

- Migrar para o protocolo binário (COBS + CRC).
- Chave "ARM" + botão "SUICIDE BURN" que dispara o script de pouso autônomo pela ponte.
- Painel mostra o estado do script (armado, queimando, pousado, abortado).

**Pronto quando:** um booster pousa sozinho a partir de um botão no painel.

### Fase 5 — Hardware definitivo

- Esquemático e PCB no **KiCad**; fabricação (JLCPCB, PCBWay…).
- Caixa impressa em 3D ou MDF cortado a laser, painel com legendas.

### Fase 6 — Embarcados avançado (opcional)

- Painéis modulares, cada um com seu micro, falando com um mestre via I2C, RS-485 ou CAN.
- Reescrever o firmware sem o framework Arduino (registradores do AVR) ou migrar para RP2040 (Raspberry Pi Pico) com o C SDK ou Rust + Embassy.

---

## Lista de compras

Compre por fase — não precisa tudo de uma vez. AliExpress costuma ser mais barato (e lento); Mercado Livre e lojas nacionais chegam mais rápido.

> **Atenção à tensão:** o Mega trabalha em 5V. Módulos de 3,3V precisam de conversor de nível.

### Ferramentas (uma vez só)

- [ ] Ferro de solda com controle de temperatura + estanho + malha dessoldadora
- [ ] Multímetro
- [ ] Alicate de corte e decapador de fios

### Fases 0–1 — Kit inicial

- [ ] 1× Arduino Mega 2560 (clone com CH340 serve) + cabo USB-B
- [ ] 2× protoboard de 830 pontos
- [ ] Jumpers macho-macho e macho-fêmea
- [ ] Kit de botões táteis
- [ ] Kit de LEDs 5 mm + kit de resistores (220 Ω–10 kΩ)
- [ ] 1× LCD 20x4 com módulo I2C (PCF8574)

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

### Fase 3 — Telemetria

- [ ] 3–4× módulos MAX7219 com 8 dígitos de 7 segmentos
- [ ] 2× encoders rotativos (KY-040)
- [ ] 1 m de fita WS2812B (60 LEDs/m) + resistor 330 Ω + capacitor 1000 µF
- [ ] 2–4× motores de passo X27.168 (ponteiros)
- [ ] 1× fonte 5V 3A + conector/borne

### Fase 5 — Hardware definitivo

- [ ] PCBs fabricadas
- [ ] Conectores JST/dupont, parafusos e espaçadores M3
- [ ] Material da caixa (filamento ou MDF 3 mm)

---

## Referências

- [kRPC — repositório](https://github.com/krpc/krpc) e [documentação](https://krpc.github.io/krpc/)
- [pySerial](https://pyserial.readthedocs.io/)
- [Arduino — documentação](https://docs.arduino.cc/)
- [KiCad](https://www.kicad.org/)
- Bibliotecas úteis para o firmware: `LiquidCrystal_I2C`, `LedControl` (MAX7219), `FastLED` ou `Adafruit_NeoPixel` (WS2812), `SwitecX25` (X27.168)
