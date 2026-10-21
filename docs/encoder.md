# Encoder AJUSTE no Uno

O AJUSTE é o encoder único do cockpit, no [VOO](../hardware/construcao.md#painel-de-sistemas-de-controle), logo embaixo da tela: ele mexe na página aberta (o piloto automático, o Δv do editor, o alvo e a subida). Até o módulo do VOO ficar pronto, ele é um EC11 com botão, ligado num Arduino Uno que fica na USB do Pi do cockpit. O firmware é o [`firmware/encoder/encoder.ino`](../firmware/encoder/encoder.ino): ele só manda os cliques e o botão, e quem decide o que eles fazem na tela é a ponte.

## Ligação

Tudo direto nos pinos do Uno, sem resistor: o firmware usa o pull-up interno.

**EC11 solto:** 5 pinos, 3 de um lado e 2 do outro.

| Pino do encoder | Uno |
|---|---|
| A: ponta do lado de 3 | 2 |
| C: **o do meio** do lado de 3 (o comum) | GND |
| B: a outra ponta do lado de 3 | 3 |
| Botão: um dos 2 do outro lado | 4 |
| Botão: o outro | GND |

**Módulo KY-040, ou uma plaquinha própria com pull-ups de 4,7 kΩ:** 5 pinos numa fileira. Os resistores vão do A, do B e do botão para o +, e o comum do encoder vai no GND. Ao contrário, com o comum no +, a lógica inverte.

| Pino do módulo | Uno |
|---|---|
| CLK | 2 |
| DT | 3 |
| SW | 4 |
| + | 5V |
| GND | GND |

- **A e B ficam nos pinos 2 e 3**, que são os de interrupção do Uno. O Nano e o Mega também têm interrupção no 2 e no 3. O botão pode ir em qualquer outro pino; basta trocar o `PINO_BOTAO`.
- **Se o sentido horário der número negativo,** troque os fios dos pinos 2 e 3.
- **Se contar um clique a cada dois "tec",** o encoder é de meio passo (30 posições e 15 pulsos por volta). O firmware espera o EC11 de 20 posições e 20 pulsos, que é o do [cockpit](../hardware/construcao.md).

## Mensagens

Protocolo v0, como o do painel ([protocolo](protocolo.md)): 115200 baud, uma mensagem por linha.

| Mensagem | Quando |
|---|---|
| `READY` | Ao ligar. Abrir a porta reinicia o Uno, que leva uns 2 s para voltar |
| `ENC AJUSTE <cliques>` | O encoder girou: horário positivo. Girando rápido, vários cliques vão numa linha só (`ENC AJUSTE 3`) |
| `BTN AJUSTE 1`, `BTN AJUSTE 0` | O botão foi apertado e solto, já sem trepidação (debounce de 20 ms) |

- **A página é da ponte:** ela repassa o giro e o aperto para a página aberta, como `ENC SUB` na SUBIDA e `ENC AP` nas outras ([Na ponte da tela](#na-ponte-da-tela), [protocolo](protocolo.md#encoder-ajuste)). O nome vem do `NOME`, na primeira linha do sketch.
- **O tempo do aperto longo é da ponte:** o Uno só manda o aperto e a soltura.
- **O Uno não lê nada da ponte** e não tem LED.

## Gravar

**Pelo Pi**, sem tirar o Uno de lá. O Pi tem o `avrdude` (`sudo apt install avrdude`). Com o `--encoder`, a ponte da tela ocupa a porta do Uno: pare o serviço antes de gravar (`sudo systemctl stop ksp-tela@USUARIO`) e ligue de novo depois (`start`).

1. No PC, no Git Bash, a partir da pasta do repositório, compile o `.hex` com o `arduino-cli` que vem com a Arduino IDE:
   ```bash
   "$LOCALAPPDATA/Programs/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe" compile --fqbn arduino:avr:uno --output-dir "$TEMP/encoder" firmware/encoder
   ```
2. Copie o `.hex` para o Pi:
   ```bash
   scp "$TEMP/encoder/encoder.ino.hex" admin@192.168.50.2:/tmp/
   ```
3. Grave:
   ```bash
   ssh admin@192.168.50.2 "avrdude -p atmega328p -c arduino -P /dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_854383639383512060A1-if00 -b 115200 -U flash:w:/tmp/encoder.ino.hex:i"
   ```
   No fim, o `avrdude` lê de volta e confere: `bytes of flash verified`.

**Pelo PC**, com o Uno na USB dele: na Arduino IDE, escolha a placa **Arduino Uno** e a porta, e grave o `firmware/encoder/encoder.ino`. O Serial Monitor, em 115200 baud, mostra o `READY` e as linhas da tabela.

## Testar no Pi

No Pi, o Uno é a porta `/dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_854383639383512060A1-if00`. Para ver as linhas chegando:

```bash
~/ksp/bin/python -m serial.tools.miniterm /dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_854383639383512060A1-if00 115200
```

Para sair, aperte `Ctrl+]`. Com a ponte da tela aberta, a porta está ocupada: pare o serviço antes (`sudo systemctl stop ksp-tela@USUARIO`).

## Na ponte da tela

A ponte da tela (`bridge/mfd.py`) lê o Uno com o `--encoder`, no Pi pelo serviço ([setup-pi.md](setup-pi.md)):

```
ARGS=192.168.50.1 --celular --encoder /dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_854383639383512060A1-if00
```

No PC, com o Uno na USB dele: `python bridge/mfd.py --demo --encoder COM8` (a porta que a Arduino IDE mostra).

**Para onde vai o giro e o aperto** ([`bridge/ajuste.py`](../bridge/ajuste.py)):

| Página aberta na tela | O AJUSTE faz o papel de | O que ele mexe |
|---|---|---|
| SUBIDA | `ENC SUB` e `BTN SUB` | O menu da subida: altitude, inclinação e o plano do alvo. Para abrir a SUBIDA, um toque curto no LANCAR (segurar 5 s lança). Com a subida voando, só mantém a página aberta |
| Qualquer outra | `ENC AP` e `BTN AP` | O menu do piloto automático: o primeiro giro abre a página do piloto, e segurar 1 s liga o modo da linha |

- **O aperto e a soltura vão para o mesmo lugar**, mesmo se a página mudar no meio. Assim o aperto longo do piloto não se perde.
- **A página fecha sozinha:** uns 10 s depois do último giro ou aperto, a tela volta para a navball (ou para a página do script voando). Depois disso, o AJUSTE volta a mexer no piloto: para mexer na subida de novo, outro toque curto no LANCAR.
- **O Uno pode sair e voltar:** se a porta cair ou não abrir, a ponte segue sem ele e tenta de novo a cada 5 s.
- **A página de botões continua valendo:** o encoder do piloto e o da subida dela mandam `ENC AP` e `ENC SUB` direto, junto com o Uno.
- O Δv do editor e o alvo entram aqui quando a ponte da tela tiver as páginas deles.
