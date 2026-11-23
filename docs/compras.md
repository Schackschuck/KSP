# Lista de compras

Itens marcados já estão na bancada. Compre por fase do [roteiro](roteiro.md) — não precisa tudo de uma vez. AliExpress costuma ser mais barato (e lento); Mercado Livre e lojas nacionais chegam mais rápido.

> **Atenção à tensão:** o Mega trabalha em 5V; o Pi, em 3,3V. Nunca ligue um pino do Pi direto em 5V — a comunicação entre os dois é pela USB.

## Ferramentas (uma vez só)

- [ ] Ferro de solda com controle de temperatura + estanho + malha dessoldadora
- [ ] Multímetro
- [ ] Alicate de corte e decapador de fios
- [x] Impressora 3D (em casa)
- Corte a laser: no colégio
- [ ] Paquímetro (para medir as peças antes de desenhar os furos dos painéis)

## Fases 0–1 — Kit inicial

- [x] Arduino Mega 2560 (também tem Uno e Nano)
- [x] Raspberry Pi 4
- [x] Botões
- [ ] Fonte para o Pi 4: 5,1V 3A USB-C de boa qualidade (fonte fraca causa travamentos)
- [ ] Dissipador ou case com ventoinha (o Pi 4 esquenta, principalmente dentro de uma caixa fechada)
- [x] Cartão microSD de 16 GB ou mais (classe A1)
- [x] Cabo USB-B para ligar o Mega no Pi
- [x] Cabo de rede, para ligar o Pi direto no PC (qualquer um: o Pi 4 inverte os pares sozinho)
- [x] 2× protoboard de 830 pontos
- [x] Jumpers macho-macho e macho-fêmea
- [x] Kit de LEDs 5 mm + kit de resistores (220 Ω–10 kΩ)
- [x] LCD 16x2 ou 20x4 com módulo I2C (só para a fase 1; opcional se já tiver)

## Fase 2 — Painel de controle

- [x] 10–15× chaves alavanca (toggle) ON-OFF
- [x] 2–3× capas de proteção para chave ("missile switch cover")
- [x] 4–6× botões arcade (24 ou 30 mm), de preferência com LED
- [ ] Por módulo pequeno (5 no painel): 2× 74HC165, 1× 74HC595, 2× rede resistiva 10 kΩ SIP 9 pinos, 1× chave DIP de 8 vias, 8× resistor 1 kΩ, 3× capacitor 100 nF, 1× capacitor 10 µF, 3 soquetes DIP-16, conector IDC 2x8 e cabo flat de 16 vias
- [ ] Por módulo médio (5 no painel): 3× 74HC165, 3× 74HC595, 3× rede resistiva 10 kΩ SIP 9 pinos, 1× chave DIP de 8 vias, 24× resistor 220 Ω, 6× capacitor 100 nF, 1× capacitor 470 µF, 12× conector JST-XH de 4 vias, 6 soquetes DIP-16, conector IDC 2x8 e cabo flat de 16 vias
- [ ] Por módulo grande (1 no painel, o VOO): 4× 74HC165, 4× 74HC595, 4× rede resistiva 10 kΩ SIP 9 pinos, 1× chave DIP de 8 vias, 32× resistor 1 kΩ, 8× capacitor 100 nF, 1× capacitor 10 µF, 8 soquetes DIP-16, conector IDC 2x8 e cabo flat de 16 vias
- [ ] Backplane: 12× conector IDC 2x8, 5× resistor 47 Ω, 13× resistor 10 kΩ, capacitores de 470 µF e 100 nF, borne de 2 vias e jumper de 3 pinos
- [x] Joystick: Logitech Extreme 3D Pro (para desenvolver no PC)
- [ ] Sidestick: 1× joystick JH-D400X-R4, 10 kΩ, 3 eixos com botão
- [ ] Acelerador: 1× potenciômetro deslizante Bourns PTA6043, 10 kΩ linear, curso de 60 mm
- [ ] 35 korry switches ([lista completa](../hardware/korry/README.md#lista-de-peças-um-korry)), cada um com 1 chave PSW 8,5 × 8,5 mm sem trava, até 2 LEDs difusos de alto brilho de 3 mm, 4 fios finos e 1 conector JST-XH fêmea de 4 vias com os terminais; filamento PLA preto e transparente
- [ ] 10× LED azul e verde de 3 mm, difuso, catodo comum (korry dos modos do SAS)
- [ ] 17× parafuso M3 autoatarraxante de 8 mm, para as 9 grades dos korry ([fixação no painel](../hardware/korry/README.md#fixação-no-painel))
- [ ] 31× botão de 16 mm sem trava, com anel de 20 mm (R16-503 ou R13-507), e 2 capas impressas para o CARREGAR e o REVERTER
- [ ] 2× botão de metal de 22 mm com anel de LED (vermelho e branco), de 5 V ou 3 V, e 2× capa transparente para botão de 22 mm
- [ ] 2× tecla KCD1 (ON)-OFF-(ON) de 21 × 15 mm
- [ ] 7× LED de 5 mm difuso (3 verdes e 1 vermelho do piloto, 3 brancos do sidestick)
- [x] 7× suporte de plástico com porca para LED de 5 mm
- [ ] Placas perfuradas de dupla face + barras de pinos (headers) e fio fino encapado (wire-wrap)

## Fase 4 — Instrumentos físicos

- [ ] 3–4× módulos MAX7219 com 8 dígitos de 7 segmentos (o piloto automático não usa mais: os valores vão para a tela)
- [ ] 2× encoders rotativos (KY-040), para escolher o que os displays mostram
- [ ] Editor de manobras ([peças e medidas](../hardware/construcao.md#painel-do-editor-de-manobras)): 1× chave rotativa de 1 polo e 12 posições, com anel de batente, e knob de ponteiro de 22 mm (a tecla, os botões e os korry estão na fase 2)
- [ ] Navegação: 1× chave rotativa de 1 polo e 12 posições, com anel de batente, e knob de ponteiro de 22 mm
- [ ] VOO, de sistemas de controle ([peças e medidas](../hardware/construcao.md#painel-de-sistemas-de-controle)): 1× encoder EC11 com botão e knob de alumínio de 30 mm, o AJUSTE (os korry e os LEDs estão na fase 2); 1 módulo grande
- [ ] 2–4× motores de passo X27.168 (ponteiros)
- [ ] 1× fonte 5V 3A + conector/borne

## Fase 6 — Tela multifunção

- [x] mikromedia for ARM (LPC2148)
- [x] Cabo mini-USB **com fios de dados**, para a PROG (o antigo alimenta a placa, mas o Windows não reconhece o FT232)
- [ ] Cartão microSD (para os sons de alarme)
- [ ] Fone ou caixinha de som com plugue P2
- [ ] Alto-falante USB para o Pi (a voz dos [avisos de voo](avisos.md))
- [ ] Gravador JTAG compatível com ARM7 (opcional, só para depurar passo a passo)

## Fase 7 — Hardware definitivo

- [ ] PCBs fabricadas
- [ ] Conectores JST/dupont, parafusos e espaçadores M3
- [ ] Material da caixa: MDF 3 mm e acrílico 3 mm (preto ou branco leitoso) para a laser, filamento PLA, primer e tinta spray fosca
- [ ] Insertos roscados M3 (colocados a quente nas peças impressas) e pés de borracha
- [ ] Extensão USB de painel (para o joystick) e ventoinha 5 V de 40 mm (para o Pi dentro da caixa)
