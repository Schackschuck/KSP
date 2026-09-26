# Fase 2: painel de controle

**Esta etapa:** chaves de SAS, RCS, trem de pouso, luzes e freios, botões STAGE e ABORT, e um LED de estado por chave, tudo direto nos pinos do Mega. Joystick e acelerador entram numa próxima etapa, quando o hardware chegar.

**Pronto quando:** cada chave comanda o seu sistema no jogo, os LEDs acompanham o jogo (inclusive quando algo muda pelo teclado) e STAGE e ABORT funcionam pelo painel.

O código é o mesmo da fase 1, ampliado: [`firmware/painel/painel.ino`](../firmware/painel/painel.ino) e [`bridge/ponte.py`](../bridge/ponte.py). As mensagens novas estão em [`docs/protocolo.md`](protocolo.md).

## Material

- 5 chaves alavanca ON-OFF
- 1 botão para o ABORT, de preferência com capa de proteção (o STAGE da fase 1 continua)
- 4 LEDs e 4 resistores de 220 Ω (o LED do SAS da fase 1 continua)

O LCD, o botão STAGE e o LED do SAS ficam onde estão.

## Montagem

Todos os botões e chaves ligam **entre o pino e o GND, sem resistor**: o firmware usa o pull-up interno. Todos os LEDs ligam como na fase 1: `pino ──[220 Ω]──(+)LED(−)── GND`.

| Controle | Tipo | Pino | LED |
|---|---|---|---|
| STAGE | botão | 2 (já montado) | — |
| ABORT | botão | 3 | — |
| SAS | chave | 22 | 8 (já montado) |
| RCS | chave | 24 | 9 |
| GEAR (trem de pouso) | chave | 26 | 10 |
| LIGHTS (luzes) | chave | 28 | 11 |
| BRAKES (freios) | chave | 30 | 12 |

```
Barra dupla no fim do Mega (vista de cima):     Cada chave:

   5V   5V                                        pino ──[chave]── GND
   22   23   ← SAS                                (para cima = contato fechado)
   24   25   ← RCS
   26   27   ← GEAR                             Cada LED:
   28   29   ← LIGHTS
   30   31   ← BRAKES                             pino ──[220 Ω]──(+)LED(−)── GND
   ..   ..
   52   53
  GND  GND   ← GND para a protoboard
```

- **As chaves usam só os pinos pares** (22, 24... 30) para ficarem todas na mesma fileira da barra dupla.
- **Faça um barramento de GND** na protoboard (a linha azul, −) e ligue nele todos os contatos e LEDs.
- **Chave com 2 terminais (ON-OFF):** um terminal no pino e o outro no GND.
- **Chave com 3 terminais:** o terminal do meio (comum) no GND e um dos lados no pino.
- **Para cima = ligada.** Monte a chave de modo que, para cima, ela feche o contato e mande `SW <nome> 1`. Se ficar invertida, vire a chave ou troque o terminal da ponta.
- **Pinos que ficam livres de propósito:** 0 e 1 (serial da USB), 20 e 21 (I2C do LCD) e 50 a 53 (SPI, para os shift registers do futuro).
- **Consumo:** os 5 LEDs juntos puxam uns 70 mA, sem problema para a USB.

## Gravar

Grave o `painel.ino` como na fase 1.

**Confira o `LCD_ENDERECO`.** Se o seu LCD não é `0x27`, troque de novo para o endereço que você achou na fase 1.

Se o `git pull` reclamar de mudanças locais no `painel.ino`, rode `git stash`, depois `git pull`, e troque o endereço de novo.

## Testar sem o KSP, pelo Serial Monitor

115200 baud, final de linha em **Nova linha**.

| Você faz | Resultado esperado |
|---|---|
| Liga a placa, com as chaves em qualquer posição | Só `READY`: a posição inicial das chaves **não** é enviada |
| Sobe e desce a chave do trem | `SW GEAR 1` e depois `SW GEAR 0`, uma mensagem por movimento |
| Repete com cada chave | `SW SAS`, `SW RCS`, `SW LIGHTS`, `SW BRAKES`: confira que cada uma manda o próprio nome |
| Aperta e solta o ABORT | `BTN ABORT 1` e depois `BTN ABORT 0` |
| Digita `RCS 1`, `GEAR 1`, `LIGHTS 1`, `BRAKES 1` | Cada um acende o LED certo, e todos apagam 1 s depois (sem sinal, como na fase 1) |
| Digita `FOO 1` | `ERR FOO 1` |

## Testar com a ponte

Feche o Serial Monitor e rode a ponte, no PC (`python bridge/ponte.py`) ou no Pi (`python ~/cockpit/bridge/ponte.py IP_DO_PC`). Faça `git pull` antes, onde a ponte for rodar.

**Pronto quando:**

- [ ] Cada chave liga e desliga o seu sistema, e o terminal mostra, por exemplo, `GEAR: ligar`.
- [ ] Cada LED acompanha o jogo **também pelo teclado**: **T** (SAS), **R** (RCS), **G** (trem), **U** (luzes) e **segurar B** (freios).
- [ ] **Chave fora de posição:**
  1. Ligue o SAS pela chave.
  2. Desligue pelo **T**: o LED apaga e a chave continua para cima.
  3. Desça e suba a chave: o SAS liga de novo.
- [ ] ABORT dispara o grupo Abort da nave, e o terminal mostra `ABORT!`.
- [ ] Mexer em chaves e botões no hangar não faz nada quando o foguete chega à plataforma.

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| A chave manda `1` quando está para baixo | Chave invertida | Virar a chave ou usar o outro terminal da ponta |
| Mexer numa chave não mostra nada | Fio no pino errado, ou a chave sem GND | Conferir o pino na tabela e o barramento de GND |
| Uma chave manda o nome de outra | Fios trocados | Conferir a tabela de pinos |
| Várias mensagens num movimento só | Fio frouxo na protoboard | Firmar o fio. O debounce resolve a trepidação da chave, não mau contato |
| Ponte: `O painel não entendeu a mensagem: RCS 1` | O Mega ainda está com o firmware da fase 1 | Gravar o `painel.ino` novo |
| Ponte: `Mensagem desconhecida do painel: SW ...` | A ponte está na versão da fase 1 | `git pull` onde a ponte roda |
| ABORT mostra `ABORT!`, mas nada acontece no jogo | O grupo Abort da nave está vazio | No VAB, em *Action Groups*, pôr ações no grupo **Abort** |
| SAS não liga pela chave e o LED fica apagado | A nave não tem SAS (sem piloto nem núcleo de sonda com SAS) | É o comportamento certo: o LED mostra o jogo |

## Acrescentar um controle

O firmware e a ponte agora são guiados por tabelas:

- **Nova chave com LED** (ex.: um action group):
  - uma linha em `ENTRADAS` e outra em `LEDS`, no `painel.ino`;
  - uma linha em `SISTEMAS`, na `ponte.py`.
- **Novo botão:**
  - uma linha em `ENTRADAS`;
  - uma função em `BOTOES`, na `ponte.py`.

Ainda sobram 34 pinos digitais livres no Mega, fora os reservados, e os 16 analógicos, que também servem como digitais. Quando isso acabar, entram os shift registers ou o MCP23017.
