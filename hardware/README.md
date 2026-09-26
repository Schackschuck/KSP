# Hardware

Esquemáticos do painel, feitos no KiCad. Cada pasta tem também um PDF do esquema, que dá para ver sem instalar nada.

| Pasta | Placa | CIs |
|---|---|---|
| [`modulo_pequeno/`](modulo_pequeno/) | Módulo pequeno: 8 entradas e 8 LEDs ([PDF](modulo_pequeno/modulo_pequeno.pdf)) | 1 × 74HC165, 1 × 74HC595 |
| [`modulo_medio/`](modulo_medio/) | Módulo médio: 16 entradas e 16 LEDs ([PDF](modulo_medio/modulo_medio.pdf)) | 2 × 74HC165, 2 × 74HC595 |
| [`modulo_grande/`](modulo_grande/) | Módulo grande: 24 entradas e 16 LEDs ([PDF](modulo_grande/modulo_grande.pdf)) | 3 × 74HC165, 2 × 74HC595 |
| [`backplane/`](backplane/) | Backplane: liga até 12 módulos ao Mega ([PDF](backplane/backplane.pdf)) | — |

As três placas de módulo usam o mesmo cabo flat e encaixam em qualquer slot.

## Qual placa em cada seção

| Seção do painel | Entradas | LEDs | Placa |
|---|---|---|---|
| Ação executiva (STAGE, ABORT) + scripts (ARM, SUICIDE BURN, EXEC) | 5 | 8 | pequena |
| Tempo | 8 | 1 | pequena |
| Analógicos: rotação | 8 | 3 | pequena, slots 1 a 5 |
| Analógicos: translação | 5 | 1 | pequena, slots 1 a 5 |
| Acelerador | 4 | 2 | pequena, slots 1 a 5 |
| Telemetria | 4 | 0 | pequena |
| Sistemas de controle | 12 | 12 | média |
| Action groups 1 a 10 | 10 | 10 | média |
| EVA | 11 | 12 | média |
| Navegação | 10 | 0 | média |
| Câmera | 10 | 0 | média |
| Editor de manobras | 17 | 0 | grande (a única seção com mais de 16 entradas) |

São 6 pequenas, 5 médias e 1 grande, que ocupam os 12 slots. As seções da primeira linha ficam longe uma da outra no painel, mas podem dividir uma placa: os fios dos botões até a placa podem ter uns 30 cm.

## Como abrir

1. Instale o KiCad 7 ou mais novo e abra o `.kicad_pro` de cada pasta.
2. Os arquivos estão no formato do KiCad 7. Uma versão mais nova avisa que vai converter o arquivo ao salvar: pode aceitar.
3. Os símbolos estão embutidos no esquema. As footprints já estão escolhidas (DIP-16 com soquete, IDC 2x8, barras de pinos), mas o layout da PCB ainda não existe: fica para a fase 7.
4. Ao abrir, rode o verificador de regras elétricas: menu **Inspecionar → Verificador de Regras Elétricas (ERC)**.

## Como tudo se liga

```
Mega ──(fios)── Backplane ── slot 1 ──(cabo flat)── módulo
                          ├─ slot 2 ──(cabo flat)── módulo
                          └─ ... até o slot 12
```

As entradas de todos os módulos formam uma única cadeia de 74HC165 e as saídas, uma única cadeia de 74HC595, as duas no SPI do Mega. Monte sempre todos os CIs da placa escolhida: a posição de cada byte na cadeia depende disso.

### Cabo flat (IDC 2x8, igual no módulo e no slot)

| Pino | Sinal | Pino | Sinal |
|---|---|---|---|
| 1 | +5V | 2 | GND |
| 3 | SCK | 4 | GND |
| 5 | PL (carrega as entradas) | 6 | RCLK (atualiza os LEDs) |
| 7 | SIN165 (vem do slot seguinte) | 8 | SOUT165 (vai para o Mega) |
| 9 | SIN595 (vem do Mega) | 10 | SOUT595 (vai para o slot seguinte) |
| 11 | AN_A | 12 | GND |
| 13 | AN_B | 14 | AN_C |
| 15 | +5V | 16 | GND |

### Ligação ao Mega

| Sinal | Pino do Mega | Observação |
|---|---|---|
| SCK | D52 | SPI |
| MOSI | D51 | Entra na cadeia de 74HC595 |
| MISO | D50 | Sai da cadeia de 74HC165 |
| PL | D49 | |
| RCLK | D48 | |
| Analógicos dos slots 1 a 5 | A0 a A14 | Slot k: A(3k−3), A(3k−2), A(3k−1) |
| 5V | 5V | Só com JP1 em 1-2 |
| GND | GND | Sempre ligado, mesmo com fonte externa |

Não use o D53 (SS) como entrada: se ele for a 0, o SPI do Mega sai do modo mestre. O `SPI.begin()` já o deixa como saída.

### Regras do backplane

1. **Módulos em slots seguidos,** a partir do slot 1, sem buracos. A cadeia para no primeiro slot vazio.
2. **Módulos com joystick ou acelerador vão nos slots 1 a 5,** os únicos com linhas analógicas.
3. **JP1 escolhe de onde vem o +5V dos módulos:**
   - **1-2:** 5 V do Mega. Serve para poucos módulos, com o Mega alimentado pela USB.
   - **2-3:** fonte externa de 5 V no borne J3. É para o painel completo.
   - Use um jumper só: ele liga 1-2 ou 2-3, nunca as duas fontes juntas.

## No módulo

| O que liga | Pequeno | Médio | Grande | Como |
|---|---|---|---|---|
| Botões e chaves | J2 (IN0–IN7) | J2, J3 (IN0–IN15) | J2, J3, J4 (IN0–IN23) | Entre o INn e o GND do próprio conector. Apertado ou ligado lê **0** (pull-up de 10 kΩ). |
| LEDs | J3 (LED0–LED7) | J4, J5 (LED0–LED15) | J5, J6 (LED0–LED15) | Anodo no LEDn, catodo no GND. O resistor de 1 kΩ já está na placa: uns 3 mA por LED, para os 8 LEDs de um 74HC595 ficarem abaixo de 70 mA. |
| Joystick ou acelerador | J4 | J6 | J7 | Pontas do potenciômetro em +5V e GND, cursor em AN_A, AN_B ou AN_C. |

**Os LEDs mostram o estado do jogo.** Nenhum LED é ligado a um botão: o Mega acende cada LED com o que a ponte manda do kRPC. Até o LED de um botão iluminado vai numa saída LEDn, separado do contato do botão.

**Botão com LED de 5 V** (como os botões arcade) já tem resistor interno. Com o 1 kΩ da placa em série, ele fica mais fraco. Se ficar fraco demais, troque o resistor daquela saída por um de menor valor, ou por um fio.

## Ordem dos bits (para o firmware)

O firmware precisa de uma tabela dizendo qual placa está em cada slot, porque cada uma ocupa um número diferente de bytes na cadeia:

| Placa | Bytes de entrada | Bytes de saída |
|---|---|---|
| Pequena | 1: U1 (IN0–IN7) | 1: U2 (LED0–LED7) |
| Média | 2: U1 (IN0–IN7), U2 (IN8–IN15) | 2: U3 (LED0–LED7), U4 (LED8–LED15) |
| Grande | 3: U1 (IN0–IN7), U2 (IN8–IN15), U3 (IN16–IN23) | 2: U4 (LED0–LED7), U5 (LED8–LED15) |

**Entradas:**
1. Um pulso baixo em PL copia todas as entradas para os 74HC165.
2. Em seguida, o SPI lê os bytes de entrada a começar pelo slot 1, na ordem da tabela acima.
3. Em cada byte, o bit n é o INn do respectivo CI.

**Saídas:**
1. O SPI envia os bytes de saída **do último slot para o primeiro**, e em cada slot do último CI para o primeiro. O último byte enviado fica no primeiro 74HC595 do slot 1.
2. Um pulso em RCLK acende o que foi enviado.

**Uma varredura em uma transferência só:**
- Como as duas cadeias compartilham o SCK, dá para ler e escrever junto.
- Cada placa tem pelo menos tantos bytes de entrada quanto de saída. Então basta transferir o total de bytes de entrada, com os bytes de saída no fim da transferência.
- Com as 12 placas da tabela, são 19 bytes: uns 80 µs a 2 MHz.
- Feito mil vezes por segundo numa interrupção de timer, dá tempo de ler até os encoders.

## Lista de peças por placa

**Módulo pequeno:**
- U1: 74HC165.
- U2: 74HC595.
- RN1: rede resistiva 10 kΩ SIP 9 pinos.
- R1–R8: 1 kΩ.
- C1–C2: 100 nF.
- C3: 10 µF.
- J1: conector IDC 2x8 macho com trava.
- J2–J3: barra de pinos 1x10.
- J4: barra de pinos 1x5.
- 2 soquetes DIP-16.

**Módulo médio:**
- U1–U2: 74HC165.
- U3–U4: 74HC595.
- RN1–RN2: rede resistiva 10 kΩ SIP 9 pinos.
- R1–R16: 1 kΩ.
- C1–C4: 100 nF.
- C5: 10 µF.
- J1: conector IDC 2x8 macho com trava.
- J2–J5: barra de pinos 1x10.
- J6: barra de pinos 1x5.
- 4 soquetes DIP-16.

**Módulo grande:**
- U1–U3: 74HC165.
- U4–U5: 74HC595.
- RN1–RN3: rede resistiva 10 kΩ SIP 9 pinos.
- R1–R16: 1 kΩ.
- C1–C5: 100 nF.
- C6: 10 µF.
- J1: conector IDC 2x8 macho com trava.
- J2–J6: barra de pinos 1x10.
- J7: barra de pinos 1x5.
- 5 soquetes DIP-16.

**Backplane:**
- J1: barra de pinos 1x7.
- J2: barra de pinos 1x16.
- J3: borne de 2 vias.
- JP1: barra de pinos 1x3 com jumper.
- J10–J21: conector IDC 2x8 macho.
- R1–R5: 47 Ω.
- R10–R21: 10 kΩ.
- C1: 470 µF.
- C2: 100 nF.

## Próximos passos

1. Revisar os esquemas no KiCad e rodar o ERC.
2. Firmware do Mega lendo a cadeia de CIs.
3. Montar o backplane e o primeiro módulo em placa perfurada. A PCB fica para a fase 7: são três placas de módulo diferentes, e cada uma é fabricada em quantidade.
