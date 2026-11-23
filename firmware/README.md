# firmware

O código das placas. As placas não sabem que o KSP existe: elas leem os controles, acendem as luzes e desenham a tela com o que a ponte manda pelo [protocolo](../docs/protocolo.md) em texto.

| Pasta | Placa | O que faz | Documentação |
|---|---|---|---|
| [`painel/`](painel/) | Arduino Mega 2560 | O I/O do painel: lê as chaves e os botões com debounce, acende os LEDs pelo estado do jogo e mostra a altitude no LCD | [fase2.md](../docs/fase2.md) |
| [`encoder/`](encoder/) | Arduino Uno | O encoder AJUSTE da tela, que manda `ENC AJUSTE` e `BTN AJUSTE` | [encoder.md](../docs/encoder.md) |
| [`passos/`](passos/) | Arduino Mega 2560 | Os sketches de aprendizado da fase 1: piscar sem `delay()`, botão com debounce, receber comandos e procurar o LCD no I2C | [fase1.md](../docs/fase1.md) |
| [`mfd/`](mfd/) | mikromedia for ARM (NXP LPC2148) | A tela multifunção sem framework: código de inicialização, script de linker, serial com interrupção, driver da tela desenhando em faixas, toque e navball em ponto fixo | [mikromedia.md](../docs/mikromedia.md) |

## Compilar e gravar

- **Mega e Uno:** a Arduino IDE 2, ou o `arduino-cli` (`arduino-cli compile --fqbn arduino:avr:mega:cpu=atmega2560 firmware/painel`; para o Uno, `arduino:avr:uno`). O painel usa a biblioteca `LiquidCrystal_I2C`, para o LCD.
- **mikromedia:** `python compilar.py`, dentro de `firmware/mfd/`, chama o LLVM (clang, ld.lld e llvm-objcopy) e gera o `mfd.hex`. O `mfd.hex` já vem compilado no repositório, então para só gravar basta o Flash Magic, pela PROG da placa. As fontes e as tabelas da navball saem do `gerar_tabelas.py`.

Os textos do LCD e da serial ficam em ASCII, sem acentos.

## Bibliotecas para as próximas fases

`LedControl` (MAX7219), `FastLED` ou `Adafruit_NeoPixel` (WS2812) e `SwitecX25` (ponteiros com o motor X27.168).
