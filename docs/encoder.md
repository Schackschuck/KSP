# Encoder AJUSTE no Uno

O AJUSTE é o encoder único do [painel da tela](../hardware/construcao.md#tela-multifunção): ele mexe na página aberta (o piloto automático, o Δv do editor, o alvo e a subida). Até o módulo do painel da tela ficar pronto, ele é um EC11 com botão, ligado num Arduino Uno que fica na USB do Pi do cockpit. O firmware é o [`firmware/encoder/encoder.ino`](../firmware/encoder/encoder.ino): ele só manda os cliques e o botão, e quem decide o que eles fazem na tela é a ponte.

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

**Módulo KY-040:** 5 pinos numa fileira.

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

- **A página é da ponte:** ela repassa o giro e o aperto para a página aberta, como fazem hoje o `ENC AP`, o `ENC DV` e o `ENC SUB` ([protocolo](protocolo.md#encoder-ajuste)). O nome vem do `NOME`, na primeira linha do sketch.
- **O tempo do aperto longo é da ponte:** o Uno só manda o aperto e a soltura.
- **O Uno não lê nada da ponte** e não tem LED.

## Gravar

O Pi não tem o `avrdude`, então a gravação é pelo PC:

1. Tire o Uno da USB do Pi e ligue no PC.
2. Na Arduino IDE, escolha a placa **Arduino Uno** e a porta dele, e grave o `firmware/encoder/encoder.ino`.
3. Teste pelo Serial Monitor, em 115200 baud: aparece `READY`. Girar e apertar mostram as linhas da tabela.
4. Ligue o Uno de volta no Pi.

## Testar no Pi

No Pi, o Uno é a porta `/dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_854383639383512060A1-if00`. Para ver as linhas chegando:

```bash
~/ksp/bin/python -m serial.tools.miniterm /dev/serial/by-id/usb-Arduino__www.arduino.cc__0043_854383639383512060A1-if00 115200
```

Para sair, aperte `Ctrl+]`.

**Ainda falta** a ponte da tela (`bridge/mfd.py`) abrir essa porta e mandar o `ENC AJUSTE` e o `BTN AJUSTE` para a página aberta.
