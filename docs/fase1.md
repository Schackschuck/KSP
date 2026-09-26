# Fase 1: primeiro circuito fechado

**Pronto quando:** apertar o botão faz o *stage*, o LED acompanha o SAS do jogo e o LCD mostra a altitude.

Durante o desenvolvimento, **o Mega fica ligado na USB do PC** e a ponte também roda no PC. Assim você grava o firmware e testa no mesmo lugar. No último passo, tudo vai para o Pi.

Cada passo termina com algo funcionando. Não pule o critério de "pronto" de cada um.

## Material

- Arduino Mega 2560 e cabo USB-B
- Protoboard e jumpers
- 1 botão
- 1 LED e 1 resistor de 220 Ω (serve de 220 a 330 Ω)
- LCD 20x4 com módulo I2C soldado atrás

## Montagem

```
Botão STAGE:  pino 2 ──[botão]── GND               sem resistor: usa o pull-up interno
LED SAS:      pino 8 ──[220 Ω]──(+)LED(−)── GND     perna longa (+) do lado do resistor
LCD I2C:      SDA → pino 20   SCL → pino 21   VCC → 5V   GND → GND
```

> No Mega, o I2C fica nos pinos **20 (SDA) e 21 (SCL)**. Tutoriais de Arduino Uno usam A4 e A5, e isso não funciona no Mega.

## Onde está o código

| Arquivo | O que é |
|---|---|
| [`firmware/passos/passo1_pisca`](../firmware/passos/passo1_pisca/passo1_pisca.ino) | Passo 1: piscar sem `delay()` |
| [`firmware/passos/passo2_botao`](../firmware/passos/passo2_botao/passo2_botao.ino) | Passo 2: botão com debounce |
| [`firmware/passos/passo3_comandos`](../firmware/passos/passo3_comandos/passo3_comandos.ino) | Passo 3: receber comandos pela serial |
| [`firmware/passos/passo4_i2c_scanner`](../firmware/passos/passo4_i2c_scanner/passo4_i2c_scanner.ino) | Passo 4a: achar o endereço do LCD |
| [`firmware/painel`](../firmware/painel/painel.ino) | Passo 4b: **o firmware do painel** (tudo junto + LCD) |
| [`bridge/ponte.py`](../bridge/ponte.py) | Passo 5: a ponte kRPC ⇄ painel |
| [`docs/protocolo.md`](protocolo.md) | O protocolo v0, mensagem por mensagem |

Os passos são cumulativos: cada sketch acrescenta uma ideia ao anterior, e os comentários explicam o porquê de cada escolha. Leia o código antes de gravar.

## Passo 0: preparar a Arduino IDE

1. **Ferramentas → Placa → Arduino AVR Boards → Arduino Mega or Mega 2560.**
2. **Ferramentas → Porta:** a porta COM do Mega. Se não souber qual é, desconecte o Mega e veja qual porta some da lista.
3. **Ferramentas → Gerenciar bibliotecas:** instale **LiquidCrystal I2C**, de Frank de Brabander.
4. Para abrir um sketch: **Arquivo → Abrir** e escolha o `.ino` dentro da pasta dele. A IDE exige que o arquivo tenha o mesmo nome da pasta.

No Serial Monitor (lupa no canto superior direito), use **115200 baud** e o final de linha em **Nova linha**.

## Passo 1: piscar sem `delay()`

Monte só o LED, abra o `passo1_pisca` e grave (seta → no alto da IDE).

**Pronto quando:** o LED pisca uma vez por segundo e o Serial Monitor mostra quantas voltas o `loop()` dá por segundo. Experimente colocar um `delay(500)` no fim do `loop()` e veja o número despencar.

## Passo 2: botão com debounce

Monte o botão e grave o `passo2_botao`.

**Pronto quando:** cada aperto imprime exatamente um `BTN STAGE 1` e um `BTN STAGE 0`, mesmo apertando rápido. Mude `DEBOUNCE_MS` para `0` e veja a trepidação aparecer.

## Passo 3: receber comandos

Com o LED e o botão montados, grave o `passo3_comandos`.

**Pronto quando:**
- ao abrir o Serial Monitor aparece `READY`;
- `SAS 1` acende o LED e `SAS 0` apaga;
- qualquer outra coisa responde `ERR ...`;
- o botão continua respondendo na hora.

## Passo 4: LCD e o firmware do painel

1. Ligue o LCD e grave o `passo4_i2c_scanner`. Anote o endereço que aparecer (normalmente `0x27` ou `0x3F`).
2. Abra o `painel`. Se o endereço for diferente de `0x27`, troque em `LCD_ENDERECO`. Grave.
3. Se a luz acender mas não aparecer texto, gire o trimpot azul atrás do LCD (contraste).

**Pronto quando**, pelo Serial Monitor:
- a primeira linha do LCD mostra `KSP Cockpit`;
- `SAS 1` acende o LED e mostra `SAS: ligado`;
- `ALT 1234567` mostra `Alt:     1.234.567 m`;
- sem digitar nada por 1 segundo, aparece `Ponte: sem sinal`, o LED apaga e os valores viram `--`.

Com isso, **o painel está completo e testado sem o KSP.**

## Passo 5: a ponte, no PC

1. **Feche o Serial Monitor.** A porta COM só pode ser aberta por um programa de cada vez.
2. No PC, se ainda não tiver instalado: `pip install krpc pyserial`.
3. Abra o KSP, com o servidor kRPC ligado, e rode:
   ```
   python bridge/ponte.py
   ```
   Sem IP, a ponte conecta no kRPC do próprio PC. A porta do Mega é detectada sozinha. Se não for, use `--porta COM5`, trocando pelo nome da sua porta.

Saída esperada:

```
Abrindo o painel em COM5...
Painel pronto.
Conectando ao kRPC em 127.0.0.1... (se demorar, aceite a conexão no jogo)
Nenhuma nave ativa. Aguardando a cena de voo...
Nave: Kerbal X
```

**Pronto quando** (este é o critério da fase):
- o botão faz o *stage* (aparece `STAGE!`);
- o LED acompanha o SAS, inclusive quando você liga e desliga pela tecla **T** do jogo;
- o LCD mostra a altitude subindo durante o voo;
- fechando a ponte (`Ctrl+C`), o LCD mostra `Ponte: sem sinal` em 1 segundo.

> Para gravar o Mega de novo, **pare a ponte antes**: ela está usando a porta.

## Passo 6: levar para o Pi

1. Ligue o Mega numa USB do Pi.
2. No Pi, pelo SSH:
   ```bash
   cd ~/cockpit && git pull
   source ~/ksp/bin/activate
   python ~/cockpit/bridge/ponte.py 192.168.1.10
   ```
   No Pi, a porta é `/dev/ttyACM0` (Mega original) ou `/dev/ttyUSB0` (clone com CH340), e também é detectada sozinha.

**Pronto quando:** tudo funciona igual ao passo 5, com o Mega no Pi e o Pi pelo Wi-Fi.

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| Serial Monitor mostra caracteres estranhos | Baud errado | 115200 no Serial Monitor |
| `SAS 1` digitado não faz nada | Final de linha em "Nenhum" | Mudar para "Nova linha" |
| LED não acende nunca | LED invertido | Perna longa (+) do lado do resistor |
| Scanner não acha nada | SDA/SCL trocados ou nos pinos errados | SDA → 20, SCL → 21 |
| LCD com luz, mas sem texto | Contraste | Girar o trimpot atrás do LCD |
| LCD mostra uma fileira de quadrados pretos | O LCD não foi inicializado: endereço errado em `LCD_ENDERECO` | Usar o endereço que o scanner mostrou |
| Falha ao gravar (avrdude: `can't open device`, `Acesso negado` ou timeout) | A ponte ou outro programa está com a porta aberta | Parar a ponte e gravar de novo |
| Ponte: `Acesso negado` ao abrir a porta | Serial Monitor aberto | Fechar o Serial Monitor |
| `module 'serial' has no attribute 'Serial'` | Foi instalado o pacote `serial` em vez de `pyserial` | `pip uninstall serial` e `pip install pyserial` |
| Ponte: "O painel não mandou READY" | Firmware errado gravado, ou baud diferente | Gravar o `painel.ino` |
| No Pi: `Permission denied` em `/dev/ttyACM0` | Usuário fora do grupo `dialout` | `sudo usermod -aG dialout $USER`, sair e entrar de novo no SSH |
