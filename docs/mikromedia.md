# Tela multifunção na mikromedia: gravar e ligar

O firmware da mikromedia for ARM (MIKROE-780) está em [`firmware/mfd/`](../firmware/mfd/). Ele faz na placa o que o [simulador](mfd.md) faz no PC: recebe o [protocolo da tela](protocolo.md#tela-multifunção-mikromedia) pela porta PROG, desenha a navball e as páginas SAS, AP e POUSO e manda os toques. O desenho copia o do simulador, com as mesmas posições, tamanhos e cores.

O **`mfd.hex` já vem compilado** no repositório. Para gravar, só é preciso o Flash Magic; o compilador só entra se o código mudar ([abaixo](#compilar-de-novo)).

**Onde estamos:** o firmware compila sem avisos, e o desenho foi conferido no PC contra o simulador, com o mesmo código compilado para o PC. **Nada rodou na placa ainda.** O controlador da tela, a orientação, o touch e a velocidade só se confirmam na placa ([o que falta confirmar](#o-que-ainda-falta-confirmar-na-placa)).

## Passo a passo, no Windows

### 1. Achar a porta COM da PROG

1. Ligue o cabo mini-USB na **PROG**, a mini-USB do lado do FT232RL, e não na **USB**.
2. No **Gerenciador de Dispositivos**, em *Portas (COM e LPT)*, deve aparecer **USB Serial Port (COMx)**. Anote o número.
   - Se aparecer **FT232R USB UART** em *Outros dispositivos*, falta o driver VCP da FTDI (ftdichip.com → Drivers → VCP).
   - Se aparecer *Dispositivo USB desconhecido*, o cabo não tem os fios de dados.
3. Uma vez só (manual da placa, pág. 12 e 13): botão direito na porta → *Propriedades* → *Configurações de Porta* → *Avançado* → desmarque **Serial Enumerator** → OK.

### 2. Instalar o Flash Magic

Baixe no site do Flash Magic (flashmagictool.com), que é gratuito, e instale.

### 3. Guardar o demo de fábrica

Gravar o firmware **apaga o demo da MikroE**. Antes, procure o `.hex` do demo na página da MIKROE-780, no site da MikroE (em *Downloads* ou *Examples*) e guarde. Se não achar, decida se pode perder o demo: dá para voltar a ele só se o arquivo aparecer depois.

### 4. Gravar o `mfd.hex`

No Flash Magic, com a placa ligada pela PROG (os valores são os do manual, pág. 14 a 18):

| Campo | Valor |
|---|---|
| *Select Device* | **LPC2148** (ARM7) |
| *COM Port* | a COMx do passo 1 |
| *Baud Rate* | **19200** |
| *Interface* | None (ISP) |
| *Oscillator (MHz)* | **12.000** |
| *Erase* | **Erase blocks used by Hex File** |
| *Hex File* | `firmware\mfd\mfd.hex` |
| *Verify after programming* | marcado |

Clique em **Start**. O Flash Magic põe a placa no modo de gravação sozinho, pelos fios DTR e RTS da PROG, sem jumper nem botão. No fim aparece *Finished* embaixo.

- **Não apague a flash inteira** (*Erase all Flash*), como no exemplo do manual: isso apaga também o ajuste da tela, e ele terá de ser feito de novo.
- Se o Flash Magic não conectar, veja [Problemas](#problemas).

Depois de gravar, **feche o Flash Magic** (ele prende a porta COM) e aperte o **RESET** da placa.

### 5. Primeira vez ligada: o ajuste da tela

1. **A luz da tela pisca 3 vezes.** É o sinal de que o firmware está rodando.
2. Aparece **KSP / TELA MULTIFUNCAO** e embaixo `CONTROLADOR xxxx`. **Anote esse número.**
3. Na primeira vez, a placa abre o **AJUSTE DA TELA**. Ele fica guardado na flash e só se faz uma vez:
   - **Orientação.** O certo é o quadrado **1 vermelho em cima à esquerda**, o **2 verde** em cima à direita, o **3 azul** embaixo à esquerda e o texto legível, sem estar espelhado. **Toque** para passar para a próxima opção (são 8) e **segure 2 s** na que estiver certa.
   - **Touch.** Aparece uma cruz de cada vez, em 3 lugares. Toque bem no centro de cada uma, de preferência com a ponta de uma caneta sem tinta ou com a unha.
   - **Conferir.** Toque em qualquer lugar: a cruz laranja tem que aparecer embaixo do dedo. Sem toque por 10 s, a tela segue sozinha.
   - Se ninguém tocar na tela por 30 s no ajuste da orientação, ela segue sem ajustar e pede o ajuste de novo na próxima vez.
4. Depois aparece a navball com **SEM SINAL**. Está certo: a ponte ainda não está mandando nada.

Para **refazer o ajuste**, segure o dedo na tela enquanto aperta o RESET e mantenha até aparecer o AJUSTE DA TELA.

### 6. Ligar na ponte

Sem o jogo, com a nave de mentira:

```
cd bridge
python mfd.py --demo --porta COM7
```

- O terminal mostra **`Tela pronta.`** e **`Controlador da tela: 0047`** (ou outro número).
- A navball da placa se mexe, os números mudam e tocar em **SAS**, **RCS** e na caixa da velocidade (**MODO**) aparece no terminal e muda a tela.
- Ao abrir a porta, a ponte reinicia a placa, como a Arduino IDE faz com o Mega. É normal a luz piscar 3 vezes.

Com o jogo, como sempre, só trocando a janela pela porta: `python mfd.py --porta COM7`. A lista do que conferir é a mesma do simulador: [Testar com o KSP](mfd.md#testar-com-o-ksp).

## Problemas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Flash Magic: *Autobaud* ou *Operation failed* | Porta errada, ou outro programa com a porta aberta (o `mfd.py`, um monitor serial) | Fechar os outros programas e conferir a COMx |
| Flash Magic continua sem conectar | O Flash Magic não está usando o DTR e o RTS para entrar na gravação | *Options* → *Advanced Options* → *Hardware Config*: marcar **Use DTR and RTS to control RST and ISP pin**. Tentar também 9600 no *Baud Rate* |
| A luz não pisca 3 vezes depois do RESET | A gravação não terminou | Gravar de novo, com *Verify* marcado |
| A luz pisca, mas a tela fica branca ou cinza | O controlador da tela não é o que o firmware espera (HX8347) | Rodar o `mfd.py --porta COMx` e anotar o número de `Controlador da tela`, que diz qual é o chip. O driver da tela (`lcd.c`) terá que ganhar a inicialização dele |
| Cores trocadas (vermelho aparece azul) ou imagem espelhada | Orientação errada | Refazer o ajuste (segurar a tela no RESET) e escolher outra opção |
| O toque cai no lugar errado | Ajuste do touch mal feito | Refazer o ajuste, tocando bem no centro das cruzes |
| O toque não reage nem no ajuste | O limiar do touch (`LIMIAR_TOQUE` em `toque.c`) não serve para esta tela | Anotar e ajustar o limiar no código ([compilar de novo](#compilar-de-novo)) |
| `A tela não mandou READY; seguindo assim mesmo.` | A placa estava no ajuste, ou é a porta errada | Terminar o ajuste; a ponte reenvia tudo quando o `READY` chegar |
| A placa trava ao abrir outro programa na porta (monitor serial, Arduino IDE) | Esses programas ligam o DTR, que na PROG segura a placa em reset | Usar só o `mfd.py`, que abre a porta com o DTR desligado |

## Como o firmware funciona

| Arquivo | O que faz |
|---|---|
| `inicio.s`, `lpc2148.ld` | Vetores, pilhas, cópia do `.data` e zeragem do `.bss`; mapa da memória (flash até 0x7C000, RAM de 32 KB) |
| `lpc2148.h` | Os registradores usados, com os endereços do manual do LPC214x (UM10139) |
| `main.c` | Liga tudo, mostra a abertura, chama o ajuste, manda `READY` e `ID` e roda o laço: serial, toque a cada 30 ms e um quadro a cada 40 ms |
| `relogio.c` | PLL: cristal de 12 MHz × 5 = 60 MHz; o Timer0 conta microssegundos |
| `serial.c` | UART0 a 115200 baud, com interrupção e uma fila de 2 KB, para não perder bytes enquanto a tela é desenhada |
| `lcd.c` | Barramento paralelo de 16 bits da tela, leitura do ID e inicialização do HX8347-D ou do HX8347-G |
| `toque.c` | Touch resistivo pelo ADC: detecta o toque e mede as duas placas |
| `ajuste.c` | Orientação e calibração do touch, guardadas na flash (setor 26) pela IAP do LPC2148 |
| `desenho.c` | Desenho em faixas: retângulos, círculos, linhas, polígonos, elipses e texto |
| `navball.c` | A navball do `bridge/navball.py`, em ponto fixo |
| `mfd.c` | O protocolo e as páginas, copiados do `mfd_simulador.py` |
| `texto.c` | Números em texto, com os mesmos formatos do simulador, e o logaritmo das barras |
| `tabelas.c` | Seno, latitude, a altura da bola e as 4 fontes, geradas pelo `gerar_tabelas.py` |
| `suporte.c` | Divisão e cópia de memória, que o compilador espera achar numa biblioteca |

**Pinos** (esquemático da placa, pág. 25; a tela é um módulo MI0283QT2 em modo de 16 bits):

| Sinal | Pino |
|---|---|
| Dados D15..D8 | P1.23..P1.16 |
| Dados D7..D0 | P0.22..P0.15 |
| RS, RD, CS, RESET, WR | P0.8, P0.9, P0.10, P0.11, P0.12 |
| Luz de fundo | P0.13 (nível alto acende) |
| Touch XR, YD, XL, YU | P0.29 (AD0.2), P0.30 (AD0.3), P0.25 (AD0.4), P0.28 (AD0.1) |
| Serial (PROG, FT232RL) | P0.0 (TX), P0.1 (RX); o DTR vai no reset e o RTS no P0.14 |

**Decisões:**

- **Desenho em faixas de 16 linhas.** Não cabe a tela inteira na RAM (150 KB contra 32 KB), e desenhar direto na tela faria piscar. A cada quadro, a cena inteira é desenhada 15 vezes, cada vez numa faixa de 320 × 16 pontos (10 KB), que vai pronta para a tela. Cada ponto é escrito uma vez só, e não pisca. O que fica fora da faixa é descartado logo no começo de cada função de desenho.
- **Sem ponto flutuante.** O ARM7 não tem, e os ângulos já chegam em décimos de grau. Seno, arco-seno e a altura da bola são tabelas; o resto é multiplicação de inteiros com 14 bits de fração.
- **O ajuste mora na placa.** Orientação e touch se escolhem na própria tela e ficam na flash. Assim não é preciso compilar nada em casa se a imagem vier espelhada ou o toque cair torto.
- **A abertura da porta.** Na PROG, o DTR vai no reset do LPC2148 e o RTS no P0.14 (o pino que faz entrar na gravação). O pyserial liga os dois ao abrir a porta, o que deixaria a placa presa no reset; por isso a `TelaMikromedia` do `mfd.py` abre com os dois desligados e dá um pulso no DTR para reiniciar a placa.
- **LLVM no lugar do GCC.** O clang compila para o ARM7 sem instalar um compilador à parte para cada placa, e o `compilar.py` roda igual no Windows e no Linux, sem `make`.

## Compilar de novo

Só é preciso se o código mudar.

1. Instale o LLVM: `winget install LLVM.LLVM` (ou o instalador do site do LLVM).
2. Na pasta `firmware/mfd`: `python compilar.py`. Ele compila com todos os avisos tratados como erro, confere a RAM que sobra para a pilha e grava o `mfd.hex`, já com a soma de verificação que o bootloader do LPC2148 confere.
3. Mudou uma fonte, o raio da bola ou as linhas da navball? Antes, `python gerar_tabelas.py` (precisa do pygame). Por padrão ele usa a DejaVu Sans Mono; no Windows, `python gerar_tabelas.py --fonte C:\Windows\Fonts\consola.ttf` usa a Consolas, a mesma do simulador.

## O que ainda falta confirmar na placa

- **O controlador da tela.** O manual não diz qual é. O módulo MI0283QT2 costuma vir com o HX8347-D (o firmware escolhe a inicialização do HX8347-G se o ID terminar em 75). O número de `CONTROLADOR` confirma.
- **A orientação e o touch**, resolvidos pelo ajuste na tela, e o **limiar do toque**.
- **A velocidade.** A conta dá uns 10 a 20 quadros por segundo, mas só medindo na placa.
- **O divisor fracionário da serial** (115200 baud a partir de 60 MHz), que o manual do LPC214x descreve. Se a ponte receber lixo, é aqui.

Fica para depois: o **alarme de estol**, que o simulador toca e a placa ainda não, porque precisa do chip de áudio (VS1053); e os sons de alarme do roteiro, no microSD.
