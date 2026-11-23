# Arquitetura

Como as partes do cockpit se ligam, o papel de cada uma e os princípios que valem para todas. O porquê de cada escolha está nas [decisões](decisoes.md), e o que já foi feito, no [roteiro](roteiro.md).

```
 PC com Windows: KSP 1 + servidor kRPC
          ▲
          │  cabo de rede direto, com IP fixo (kRPC, TCP/protobuf)
          │  (pela Wi-Fi de casa durante o desenvolvimento)
          ▼
 Raspberry Pi 4 = computador de bordo ............... bridge/
   • ponte kRPC ⇄ placas, aberta sozinha quando o Pi liga
   • tela multifunção no navegador do tablet ........ bridge/celular/
   • dispara os scripts de voo ....................... scripts/
          ▲                         ▲
          │ USB/serial              │ Wi-Fi de casa
          │ (protocolo próprio)     │ (página da tela, por HTTP)
          ▼                         ▼
 Arduino Mega = I/O do painel    tablet = tela multifunção
 firmware/painel/                (Galaxy Tab S 8.4, no Chrome)
          ▲
          │  SPI + linhas analógicas
          ▼
 Backplane: 12 slots ................................ hardware/backplane/
          ▲
          │  um cabo flat de 16 vias por módulo
          ▼
 Módulos do painel, um por seção .......... hardware/modulo_pequeno/, _medio/ e _grande/
   pequeno: 8 entradas + 8 LEDs (1 × 74HC165 + 1 × 74HC595)
   médio: 16 entradas + 24 LEDs (2 × 74HC165 + 3 × 74HC595), com 12 jacks de korry
   grande: 24 entradas + 32 LEDs (3 × 74HC165 + 4 × 74HC595)
   korry, botões, LEDs, sidestick, acelerador
```

Cada parte tem um papel bem definido:

| Parte | Responsabilidade | Não faz |
|---|---|---|
| **KSP + kRPC** (PC) | Expõe o estado da nave e aceita comandos. | — |
| **Computador de bordo** (Raspberry Pi 4, Python) | Conecta no kRPC pela rede, abre *streams* de telemetria, traduz eventos do painel em comandos do jogo e telemetria em mensagens para o painel e para a tela multifunção, cuja página ele serve pela rede. Dispara os scripts de voo de `scripts/` (ex.: pouso autônomo). | Não lê pino nenhum. |
| **Sidestick** (joystick JH-D400X-R4 no painel, lido pelo Mega) | Manda os 3 eixos e o botão como qualquer controle do painel; a ponte os traduz em comandos do kRPC. | O KSP não enxerga o joystick: tudo passa pela ponte. |
| **Painel** (Arduino Mega, C++) | Lê entradas (com debounce), envia eventos; recebe valores e atualiza LEDs, displays e ponteiros. | **Não sabe que o KSP existe.** É um painel de I/O genérico. |
| **Celular** (opcional, página no navegador) | Mostra a mesma página do tablet, em qualquer celular na mesma Wi-Fi, sem instalar nada. | Não fala com o kRPC nem guarda estado: só desenha o que a ponte manda. |
| **Tela multifunção** (um tablet Galaxy Tab S 8.4, pela Wi-Fi de casa e no próprio carregador) | Abre no Chrome a mesma página do celular e desenha as páginas (navball, órbita, recursos, pouso, piloto) com o que a ponte manda; troca de página pelo toque ou sozinha, pelo painel mexido. | Não fala com o kRPC; só mostra o que o computador de bordo manda. |

Durante o desenvolvimento, o mesmo código Python roda no PC — só muda o endereço do servidor kRPC e a porta serial.

## Princípios

- **O LED mostra o estado do jogo, não a posição da chave.** A chave só avisa para onde foi ("SAS para cima"); o computador de bordo decide o que fazer e o jogo confirma. Assim o painel nunca fica dessincronizado (ex.: SAS desligado pelo jogo).
- **Uma tela só, no meio do painel: a tela multifunção.** Os módulos não têm tela própria. Cada módulo que precisa mostrar números (editor de manobras, piloto automático, rendezvous...) tem uma página na tela multifunção. Quando o piloto mexe num módulo, a ponte troca a tela para a página dele; uns segundos depois do último toque no módulo (uns 10 s, a ajustar), a tela volta sozinha para a página de antes, em geral a navball.
- **Protocolo serial em duas versões:**
  - **v0 — texto**, uma mensagem por linha. Fácil de depurar no Serial Monitor.
    ```
    Pi → placa:  ALT 12345      SAS 1      FUEL 73
    placa → Pi:  BTN STAGE 1    SW SAS 0   AX PITCH -312
    ```
  - **v1 — binário**, com enquadramento [COBS](https://en.wikipedia.org/wiki/Consistent_Overhead_Byte_Stuffing), ID de mensagem e CRC. Mais rápido e robusto; vem quando a v0 começar a apertar. É o mesmo protocolo para o Mega e para a mikromedia.
- **Entradas analógicas** (joystick, acelerador) são enviadas a uma taxa fixa, com zona morta e filtro; **entradas digitais** são enviadas só quando mudam.

## Estrutura do repositório

```
bridge/           computador de bordo em Python: ponte kRPC ⇄ serial do painel (ponte.py);
                  tela multifunção: ponte (mfd.py), simulador, navball e a página do navegador,
                  para o tablet e o celular (celular/), com o mapa 3D (mapa.py) e o encoder AJUSTE (ajuste.py);
                  painel de sistemas de controle (sistemas.py), com a página de botões (celular/painel.html);
                  painel de scripts (painel_scripts.py): o korry POUSO abre o scripts/pouso.py, e o
                  LANCAR, o scripts/subida.py, com o menu da subida;
                  avisos de voo por voz, como o GPWS (avisos.py);
                  editor de nós de manobra com botões na página (manobras.py); testes em bridge/tests/;
                  o serviço do systemd que abre a ponte da tela quando o Pi liga (servico/)
scripts/          scripts de voo (pouso, subida até a órbita, rendezvous, fly by wire...), que rodam com ou sem o cockpit; testes em scripts/tests/
firmware/painel/  Arduino Mega (Arduino IDE ou PlatformIO)
firmware/encoder/ Arduino Uno com o encoder AJUSTE da tela (docs/encoder.md)
firmware/passos/  sketches de aprendizado, um por passo da fase 1
firmware/mfd/     mikromedia for ARM / LPC2148 (C, compilado com o LLVM pelo compilar.py): a tela multifunção
hardware/         esquemáticos e PCBs (KiCad), desenhos da caixa; ver hardware/README.md
                  e hardware/construcao.md (o cockpit da versão B, a caixa e os painéis);
                  cada peça própria numa pasta, com ficha e desenhos (hardware/korry/:
                  modelo no OpenSCAD, STL das legendas, das grades e das peças, gerar.py e o desenho da ligação);
                  identidade visual (hardware/identidade_visual.md) e desenhos dos painéis
                  gerados por código (hardware/desenho/, SVG em hardware/img/)
docs/             a documentação em português: protocolo, arquitetura, decisões, roteiro e um guia por parte
                  (índice em docs/README.md); imagens em docs/img/
.claude/          o fluxo do Claude Code: skills /verificar, /publicar e /desenhar-painel, o hook e os revisores;
                  as regras do projeto ficam no CLAUDE.md
```
