# Roteiro

Cada fase termina com algo funcionando de ponta a ponta. Não pule o critério de "pronto".

## Fase 0 — Ambiente

**Status: concluída.** Passo a passo detalhado e problemas encontrados em [docs/setup-pi.md](setup-pi.md). No cockpit, o Pi liga no PC por um [cabo de rede direto](setup-pi.md#8-cabo-de-rede-direto-até-o-pc), testado com o `fase0_altitude.py`, e a ponte da tela [abre sozinha](setup-pi.md#9-a-ponte-da-tela-abrindo-sozinha) quando ele liga, espera o jogo e reconecta quando ele fecha e abre de novo.

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

Versão completa, que recebe o IP como argumento, espera a cena de voo e explica os erros de conexão: [`bridge/fase0_altitude.py`](../bridge/fase0_altitude.py).

**Pronto quando:** o script roda **no Pi** e imprime a altitude ao vivo enquanto o foguete sobe no PC.

## Fase 1 — Primeiro circuito fechado

**Status: concluída**, no PC e no Pi. Roteiro passo a passo, montagem e testes: [docs/fase1.md](fase1.md). Protocolo: [docs/protocolo.md](protocolo.md).

- Mega ligado no PC pela USB durante o desenvolvimento; no fim, no Pi.
- 1 botão (STAGE), 1 LED (SAS) e a altitude num LCD 20x4 com módulo I2C.
- Protocolo **v0 (texto)**.
- Aprende: pull-up, debounce, leitura/escrita serial, laço principal sem `delay()`.

**Pronto quando:** apertar o botão faz *stage*, o LED acompanha o SAS do jogo e o LCD mostra a altitude.

## Fase 2 — Painel de controle

**Status: em andamento.** Chaves, botões e LEDs estão prontos para montar: pinagem, código e testes em [docs/fase2.md](fase2.md). O cockpit inteiro está desenhado: a [versão B](../hardware/construcao.md#cockpit-versão-b), em U, com 11 painéis de 125 mm, o sidestick e o acelerador no painel.

- Chaves para SAS, RCS, trem de pouso, luzes e freios; STAGE e ABORT com capa de proteção. Depois, action groups.
- **Painel VOO, de sistemas de controle** ([desenho](../hardware/construcao.md#painel-de-sistemas-de-controle)): os 10 modos do SAS em korry de duas cores (azul virando, verde segurando), korry SAS, RCS, FBW e TRAVA ALT, e o encoder do [piloto automático](scripts-de-voo.md#piloto-automático-de-avião). Numa placa grande com 4 × 74HC595. Apertar um modo do SAS abre a roda dos modos na tela multifunção, só para ver. Trem de pouso, luzes e freios foram para o painel do acelerador.
- A posição da chave é o estado desejado (para cima = ligado); o LED de cada sistema mostra o estado no jogo.
- **Painel em módulos:** cada seção vira uma placa, ligada por cabo flat a um backplane de 12 slots no Mega. A placa pequena tem 8 entradas e 8 LEDs (1 × 74HC165 + 1 × 74HC595); a média, 16 e 24 (2 + 3), com um jack JST-XH para cada korry; a grande, 24 e 32 (3 + 4). Os LEDs só mostram o que vem do jogo: nenhum é ligado a um botão. Cada módulo tem uma etiqueta numa chave DIP, e o Mega descobre sozinho o que está encaixado. Esquemáticos, etiquetas e qual placa vai em cada seção em [hardware/](../hardware/README.md).
- Enquanto o primeiro módulo não fica pronto, os controles básicos continuam direto nos pinos do Mega, como em [docs/fase2.md](fase2.md).
- Próximo passo: o firmware do Mega lendo a fila de módulos pelas etiquetas, e testar o primeiro módulo direto no Mega.
- **Tela e encoder:** a [tela multifunção](../hardware/construcao.md#tela-multifunção) agora é um tablet Galaxy Tab S 8.4, atrás do painel duplo. Um encoder só, o AJUSTE, no [VOO](../hardware/construcao.md#painel-de-sistemas-de-controle), logo embaixo da tela, mexe na página aberta: o piloto automático, o Δv do editor, o alvo e a subida. As luzes do piloto e os avisos ficam ao lado dele. As barras de recursos saíram, e o painel da asa esquerda virou só [EVA](../hardware/construcao.md#eva).
- **Sidestick e acelerador no painel:** um joystick JH-D400X-R4 de 3 eixos, com o botão do manche trocando entre VOO, CÂMERA e TRANSLAÇÃO, e uma alavanca deslizante de 60 mm, os dois lidos pelo Mega nas linhas analógicas do backplane ([sidestick](../hardware/construcao.md#sidestick), [acelerador](../hardware/construcao.md#acelerador)). O Extreme 3D Pro fica para desenvolver no PC; mapeamento em [hardware/construcao.md](../hardware/construcao.md#joystick-logitech-extreme-3d-pro).
- **Korry switches:** botões iluminados com legenda, como nos aviões, 35 no cockpit. Legenda impressa em duas cores na FlashForge Inventor, encaixada num corpo igual para todos, com a chave e os LEDs num suporte impresso. As bases de cada grupo saem numa grade impressa, parafusada atrás do painel. O modelo, os STL das 31 legendas, das grades e das peças, o `gerar.py` e a ligação estão em [hardware/korry/](../hardware/korry/README.md); o primeiro passo é o teste de folga e um korry ligado direto no Mega.

**A fazer na ponte, para a versão B** (o que cada controle faz e o comando do kRPC estão em [hardware/construcao.md](../hardware/construcao.md#os-painéis)):

- [ ] Definir no [protocolo](protocolo.md) as mensagens dos painéis novos: tempo, navegação, action groups e peças, câmera, EVA, acelerador e sidestick.
- [ ] Tempo: WARP, PARAR, FISICO, ATE O NO, PAUSA, SALVAR, CARREGAR e REVERTER.
- [x] Encoder AJUSTE da tela: o firmware do Uno, mandando `ENC AJUSTE` e `BTN AJUSTE` ([docs/encoder.md](encoder.md)).
- [x] Encoder AJUSTE da tela: a ponte lê o Uno (`--encoder`) e manda o giro e o aperto para a página aberta: a SUBIDA ou o piloto automático ([docs/encoder.md](encoder.md#na-ponte-da-tela)).
- [ ] Encoder AJUSTE: o Δv do editor e o alvo, quando a ponte da tela tiver as páginas deles.
- [ ] Navegação: PROCURAR abre a página ALVO, e o AJUSTE escolhe o alvo; LIMPAR; REFERENCIA; trocar de nave.
- [ ] Action groups 1 a 8 e os korry das peças (paraquedas, painéis solares, antenas, compartimento de carga), com a luz do estado.
- [ ] Câmera: IVA, MODO CAM, FOTO e ESCONDER. O MAPA já existe na página de botões e abre a página MAPA do tablet.
- [ ] Acelerador pela alavanca; TREM, FREIOS e LUZES em korry.
- [ ] Sidestick: os 3 eixos pelo Mega, e o botão trocando o modo, com as luzes.
- [ ] EVA, quando houver o kRPC 0.7: andar e voar pelo manche, JATO, LUZ, SAIR, EMBARCAR, AGARRAR e SOLTAR.
- [x] Tela no tablet: a página SUBIDA no navegador, com o menu e o desenho do voo, como na mikromedia.
- [ ] Testar a tela no Tab S pela Wi-Fi, em tela cheia.
- [x] Página MAPA no tablet: a órbita em 3D, as luas, o alvo e o nó de manobra, no lugar do mapa do jogo ([docs/mfd.md](mfd.md#a-página-mapa)). Depois: as trajetórias que trocam de esfera de influência.
- [ ] Páginas novas na tela: ORBITA, DELTA-V, SUBIDA, ALVO, TEMPO, EVA e RECURSOS (combustível, oxidante, monopropelente e eletricidade, no lugar das barras de LED).

**Pronto quando:** dá para lançar e colocar um foguete em órbita usando só o painel.

## Fase 3 — Tela de telemetria

- Na tela multifunção: altitude, velocidades, apoapse/periapse, tempo até Ap/Pe, combustível e delta-v por estágio.
- Depois: gráfico de altitude × tempo, desenho simples da órbita, indicador de atitude.
- O tablet é velho, então vale o bom hábito: redesenhar só o que mudou e limitar a taxa de quadros.
- A tela do cockpit é um tablet Galaxy Tab S 8.4, com a página da tela no Chrome, com a página chegando pela Wi-Fi de casa e o tablet no próprio carregador ([docs/mfd.md](mfd.md#no-tablet-do-cockpit)). A mesma tela roda no simulador do PC, no celular e na mikromedia ([fase 6](#fase-6--tela-multifunção-mikromedia-for-arm)).
- A tela multifunção ([docs/mfd.md](mfd.md)) já mostra navball, velocidades, altitude e Ap/Pe, na placa, no simulador e numa página web.

**Pronto quando:** dá para circularizar uma órbita olhando só para a tela.

## Fase 4 — Instrumentos físicos

**Status: editor de manobras escrito, com botões numa página no lugar das chaves; falta testar no jogo.** [`bridge/manobras.py`](../bridge/manobras.py) cria e edita os nós pelo kRPC e mostra os números do nó e da órbita (antes e depois) no navegador do PC ou do celular: [docs/manobras.md](manobras.md). A página manda linhas do protocolo pela rede; o painel vai mandar as suas pela serial, com o encoder no lugar dos pares `+`/`-` do Δv. Por enquanto a página também gira a câmera do mapa, **o que tem que sair dela:** no cockpit, a câmera do mapa vai ser mexida pelo joystick, no modo CÂMERA.

**A fazer no editor, para ficar igual ao painel desenhado** ([desenho](../hardware/construcao.md#painel-do-editor-de-manobras), [mensagens](protocolo.md#no-painel)):

- [ ] Ponte (`bridge/manobras.py`): guardar o eixo escolhido (PRO, NRM ou RAD), começando pelo PRO em cada nó novo, e trocar de eixo com `BTN PRO`, `BTN NRM` e `BTN RAD`.
- [ ] Ponte: aceitar `ENC DV <cliques>` (horário positivo) e aplicar os cliques × passo no eixo escolhido.
- [ ] Ponte: aceitar `SW PASSO <0 a 3>`, o passo pela posição da chave rotativa, no lugar do `BTN PASSO`.
- [ ] Ponte: mandar ao painel qual eixo está escolhido, para acender o korry certo.
- [ ] Página do celular (`bridge/celular/manobras.html`): trocar os pares `PRO -`/`PRO +`, `NRM -`/`NRM +` e `RAD -`/`RAD +` por três botões de eixo e um par `-`/`+` que faz o papel do encoder, com o eixo escolhido destacado.
- [ ] Testes (`bridge/tests/test_manobras.py`) para o eixo escolhido, o `ENC DV` e o `SW PASSO`.
- [ ] Atualizar [docs/manobras.md](manobras.md) e tirar o "planejado" da seção [No painel](protocolo.md#no-painel) do protocolo.

- Displays de 7 segmentos com MAX7219 para os números mais importantes.
- Encoder rotativo para escolher o que cada display mostra. Lido pela mesma cadeia de 74HC165 dos módulos: o Mega lê a cadeia inteira mil vezes por segundo numa **interrupção de timer**, e assim o redesenho do LCD (~20 ms) não faz perder cliques. O painel acumula os cliques e manda `ENC <nome> <cliques>`.
- **Editor de nós de manobra** (pelo kRPC: `control.add_node`, `node.prograde` etc.):
  - Painel duplo de 250 × 125 mm, desenho e peças em [hardware/construcao.md](../hardware/construcao.md#painel-do-editor-de-manobras).
  - **Δv por um encoder só**, porque os três eixos nunca são mexidos ao mesmo tempo. Três korry (PRO, NRM e RAD) escolhem o eixo, e a legenda do escolhido acende na cor da alça do nó no KSP. Girar no sentido horário soma o passo; no anti-horário, tira. Um nó novo já vem com o PRO escolhido. O encoder é o AJUSTE, no VOO: com a página do editor aberta, a ponte manda o giro como `ENC DV <cliques>`, e quem sabe o eixo escolhido é ela.
  - **PERCURSO:** uma tecla basculante com mola para o centro, como a do TIME WARP, montada deitada, move o nó ao longo da órbita (para a esquerda, antes; para a direita, depois). Segurando, repete; o painel manda `INC TEMPO <passos>`. Embaixo dela, ANT e PROX trocam de nó.
  - **PASSO:** chave rotativa de 4 posições, com a legenda gravada em volta: 0,1 / 1 / 10 / 100 m/s no Δv e 1 s / 10 s / 1 min / 10 min no tempo.
  - Korry NOVO (nó novo no apoastro), APAGAR e CIRC (circulariza no ponto do nó, com o Δv calculado pela ponte). Sem AP e PE: o tempo já leva o nó a qualquer ponto.
  - São 14 entradas e 3 LEDs (os korry de eixo): cabe numa placa média.
  - **Sem tela no módulo:** Δv, tempo de queima, T− até o nó e o Ap/Pe resultante aparecem numa página do editor na tela multifunção, que abre sozinha quando uma tecla ou botão do editor é usado (ver os [princípios](arquitetura.md#princípios)).
  - O botão MAPA fica na seção da câmera e abre a página MAPA do tablet, onde o nó aparece com a órbita depois dele. A câmera do mapa (girar e aproximar) é o toque no tablet, não o editor.
- O que resta de combustível, oxidante, monopropelente e eletricidade vai para a página RECURSOS da tela multifunção, no lugar das barras de LED que estavam no painel da [EVA](../hardware/construcao.md#eva).
- Ponteiro analógico com motor de passo X27.168.
- Fonte 5V externa (a USB não aguenta muitos LEDs).

**Pronto quando:** um voo inteiro (lançamento → órbita → reentrada) é feito sem olhar para o monitor do PC, inclusive planejar a circularização pelo editor de manobras.

## Fase 5 — Protocolo v1 + scripts de voo

**Status: script de pouso escrito, em teste no jogo; o korry POUSO já dispara o script pela página de botões.** No primeiro teste, em Kerbin, a freada terminou alta e a nave tocou o chão inclinada e tombou. Corrigido: o pé agora é medido pelas pernas do trem. No segundo teste o pé ficou certo (0,4 m de erro no toque), mas a nave balançou até 31° na freada: o piloto automático do kRPC não segurava a nave. Agora quem aponta a nave é o SAS do KSP (falta testar de novo). [`scripts/pouso.py`](../scripts/pouso.py) faz a queima de suicídio numa descida vertical, em qualquer planeta, contando o arrasto do ar; roda pela linha de comando ou pelo korry POUSO do [painel de scripts](../hardware/construcao.md#painel-de-scripts), e a tela multifunção mostra o pouso numa página própria ([docs/mfd.md](mfd.md#painel-de-scripts-e-a-página-do-pouso)). [`scripts/tests/test_pouso.py`](../scripts/tests/test_pouso.py) testa a mesma guiagem numa nave simulada, sem o KSP, em planetas com e sem atmosfera.

- Migrar para o protocolo binário (COBS + CRC).
- **Painel de scripts** ([desenho](../hardware/construcao.md#painel-de-scripts)): um korry por script, em faixas na ordem do voo (SUBIDA, ORBITA, DESCIDA). Por enquanto o POUSO e o LANCAR, da [subida até a órbita](scripts-de-voo.md#subida-até-a-órbita); os outros quatro lugares ficam vagos, com a tampa lisa. Segurar o korry 5 s abre o script; segurar de novo 5 s aborta. O korry pisca âmbar enquanto conta, fica verde com o script voando e vermelho se ele foi abortado ou falhou.
- Korry "EXEC" (um lugar vago do painel de scripts) que executa o nó de manobra da fase 4: aponta a nave para o nó, acelera o tempo até perto dele, queima e corta quando o Δv restante chega a zero.
- Painel e tela mostram o estado do script (armando, voando, pousado, abortado). A página POUSO da tela, inspirada na tela do booster da SpaceX, mostra a nave descendo até o alvo, a fase, a altura, a descida, o empuxo/peso e quanto do empuxo a freada precisa. O pouso e o EXEC seguem a [base comum dos scripts](scripts-de-voo.md#base-comum).

**A fazer no painel de scripts:**

- [x] Ponte (`bridge/painel_scripts.py`): segurar `BTN POUSO` 5 s abre o `scripts/pouso.py` num processo; segurar de novo aborta; a linha `SCR POUSO` acende o korry.
- [x] `scripts/pouso.py`: estado por UDP (linhas `POU`), código de saída e `--demo` com uma nave simulada.
- [x] Página POUSO no simulador e no celular; korry POUSO na página de botões (`bridge/celular/painel.html`).
- [ ] Testar no jogo: o korry abre o pouso, a página acompanha, e segurar de novo aborta com o motor cortado.
- [ ] Firmware do Mega: o korry POUSO no módulo da ação executiva, mandando `BTN POUSO 1` e `0`, e o LED de duas cores pela linha `SCR POUSO`.
- Os outros scripts (piloto automático de avião, [subida até a órbita](scripts-de-voo.md#subida-até-a-órbita), pouso de precisão...) estão em [Scripts de voo](scripts-de-voo.md#scripts-de-voo) e não entram no critério desta fase.

**Pronto quando:** um booster pousa sozinho a partir de um botão no painel, e um nó de manobra é executado pelo botão EXEC.

## Fase 6 — Tela multifunção (mikromedia for ARM)

**Fora do cockpit de novo:** a tela do cockpit passou a ser um tablet Galaxy Tab S 8.4, com a mesma página do celular ([decisões](decisoes.md)), porque a tela de 2,8" ficava pequena no meio do painel. O firmware continua aqui e roda na placa, com o jogo.

Placa da MikroElektronika com **NXP LPC2148** (ARM7TDMI-S, 60 MHz, 512 KB de flash, 32 KB de RAM), tela 320x240 com touch resistivo, microSD, saída de áudio e carregador de Li-Po. Aqui o firmware é escrito **sem framework**: C, registradores, script de linker e código de inicialização próprios.

**Status: rodando na placa, com o jogo.** O firmware em `firmware/mfd/` faz na placa o que o simulador faz no PC: navball, números, botões de toque e as páginas SAS, AP e POUSO, no protocolo em texto. A página SUBIDA ([subida até a órbita](scripts-de-voo.md#subida-até-a-órbita)) existe na placa e no navegador; o simulador mostra a navball no lugar dela. Ligada no Pi pela PROG, com a ponte da tela aberta pelo serviço, a placa mostra a navball ao vivo, lisa, e o toque funciona no jogo. O controlador da tela é o `0047`, o HX8347-D. Falta o áudio. Gravar e ligar: [docs/mikromedia.md](mikromedia.md). A tela também roda no simulador do PC e no navegador do celular: [docs/mfd.md](mfd.md).

- **Placa:** duas mini-USB. A **USB** vai direto no LPC2148, e a **PROG** tem um conversor USB-serial **FT232RL**, por onde o PC conversa com a placa e o Flash Magic grava o firmware. No cockpit, o Pi liga na PROG; a USB só alimenta a placa, porque o firmware não usa ela. A tela é um módulo MI0283QT2 (320x240, barramento de 16 bits), com touch resistivo lido pelo ADC. Pinos em [docs/mikromedia.md](mikromedia.md#como-o-firmware-funciona).
- **Ferramentas:** LLVM (clang, ld.lld e llvm-objcopy), chamado pelo `firmware/mfd/compilar.py`; o `mfd.hex` já vem compilado. Gravação pelo bootloader serial de fábrica do LPC2148, pela PROG, com o Flash Magic.
- **Passos:**
  1. [x] Código de inicialização, script de linker, PLL a 60 MHz.
  2. [x] Serial com interrupção e o protocolo da tela ([docs/protocolo.md](protocolo.md#tela-multifunção-mikromedia)), em texto como o simulador; mais tarde o v1.
  3. [x] Driver da tela (HX8347) e desenho em faixas de 16 linhas, porque não cabe um *framebuffer* (320×240×2 = 150 KB contra 32 KB de RAM).
  4. [x] Touch pelo ADC, com a orientação e a calibração escolhidas na própria tela e guardadas na flash.
  5. [x] Páginas: navball, roda do SAS, piloto automático, pouso e subida. Depois: mapa da órbita, informações e uma página para cada módulo do painel que precisa de números (a começar pelo editor de nós de manobra).
  6. [x] Rodar na placa: o controlador é o `0047` (HX8347-D), o toque responde e a navball anda lisa ([conferido na placa](mikromedia.md#conferido-na-placa)).
  7. [ ] Áudio: alarme de estol e avisos gravados no microSD (combustível baixo, contagem de altitude no pouso), pelo VS1053.

**Pronto quando:** a mikromedia mostra telemetria ao vivo recebida do Pi e toca um alarme de combustível baixo.

## Fase 7 — Hardware definitivo

- PCB no **KiCad** a partir dos esquemáticos de [hardware/](../hardware/README.md): uma placa de módulo, fabricada em quantidade, e o backplane. Fabricação na JLCPCB, PCBWay… A do módulo médio já está pronta, com os Gerbers ([hardware/](../hardware/README.md#pcb-do-módulo-médio)).
- Caixa em MDF cortado a laser (no colégio), com peças impressas em 3D (em casa): um painel removível por seção, legendas gravadas, korry switches, o Pi e o tablet embutidos. Formato, aparência e ordem para construir em [hardware/construcao.md](../hardware/construcao.md).

## Fase 8 — Embarcados avançado (opcional)

- Painéis modulares, cada um com seu micro, falando com um mestre via I2C, RS-485 ou CAN.
- Painel sem fio com **ESP32**.
- Reescrever o firmware do Mega sem o framework Arduino (registradores do AVR) ou migrar para RP2040 (Raspberry Pi Pico) com o C SDK ou Rust + Embassy.
