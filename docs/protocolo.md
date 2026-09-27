# Protocolo serial v0 (texto)

Protocolo entre o computador de bordo (a ponte, `bridge/ponte.py`) e as placas (hoje, o Mega com `firmware/painel/painel.ino`). Os nomes (`STAGE`, `SAS`, `GEAR`...) vêm das tabelas `ENTRADAS` e `LEDS` do firmware e dos dicionários `BOTOES` e `SISTEMAS` da ponte; um controle novo entra nos dois lados. É texto puro, para dar para testar e depurar pelo Serial Monitor. A tela multifunção usa o mesmo formato, com mensagens próprias: ver [a última seção](#tela-multifunção-mikromedia). A versão binária (v1, com COBS e CRC) vem na fase 5.

## Camada física e enquadramento

- Serial pela USB, **115200 baud**, 8N1.
- Texto ASCII, **uma mensagem por linha**, terminada em `\n`. Um `\r` antes do `\n` é ignorado.
- Formato: palavras separadas por **um** espaço, como `READY`, `ALT 1234` ou `SW GEAR 1`. Maiúsculas e minúsculas fazem diferença.
- Linhas vazias são ignoradas. Linhas com mais de 31 caracteres são descartadas inteiras.

## Mensagens

### Painel → ponte

| Mensagem | Quando | Significado |
|---|---|---|
| `READY` | Ao terminar de ligar (inclusive depois de um reset) | O painel está pronto para receber. Tudo o que foi enviado antes disso se perdeu. |
| `BTN <nome> 1` | Um botão foi apertado | Enviada **uma vez por mudança**, já sem trepidação (debounce de 20 ms) |
| `BTN <nome> 0` | Um botão foi solto | idem |
| `SW <nome> 1` | Uma chave foi ligada (para cima) | idem |
| `SW <nome> 0` | Uma chave foi desligada (para baixo) | idem |
| `ERR <linha>` | Chegou uma linha que o painel não reconhece | Devolve a linha recebida, para ajudar a depurar |

Botões hoje: `STAGE` e `ABORT`. Chaves hoje: `SAS`, `RCS`, `GEAR`, `LIGHTS` e `BRAKES`.

### Ponte → painel

| Mensagem | Valores | Efeito no painel |
|---|---|---|
| `SAS <0\|1>` | `0` desligado, `1` ligado | LED do SAS e linha "SAS" do LCD |
| `RCS <0\|1>` | idem | LED do RCS |
| `GEAR <0\|1>` | `0` recolhido, `1` baixado | LED do trem de pouso |
| `LIGHTS <0\|1>` | `0` apagadas, `1` acesas | LED das luzes |
| `BRAKES <0\|1>` | `0` soltos, `1` acionados | LED dos freios |
| `ALT <metros>` | Inteiro com sinal, 32 bits | Linha "Alt" do LCD |

## Comportamento

- **Reset ao abrir a porta.** Abrir a serial reinicia o Mega, que leva cerca de 2 s para voltar. A ponte espera o `READY` antes de enviar qualquer coisa. Se receber `READY` no meio do voo, o painel reiniciou, e a ponte reenvia o estado.
- **Frequência de envio.** A ponte envia `ALT` 10 vezes por segundo, mesmo que a altitude não mude. Cada estado (`SAS`, `RCS`...) vai quando muda, e todos vão também uma vez por segundo, caso alguma mensagem tenha se perdido.
- **Chaves: a posição é o estado desejado.** `SW GEAR 1` quer dizer "a chave do trem foi para cima: baixe o trem". A ponte leva o sistema para a posição da chave. Se o jogo mudar o sistema por conta própria (ex.: SAS pela tecla **T**), o LED mostra o estado real, e a chave fica fora de posição até ser mexida de novo.
- **Posição inicial das chaves não é enviada.** O painel só avisa quando alguém mexe numa chave, nunca ao ligar. Assim, ligar o painel ou reiniciar a ponte nunca muda nada no jogo sozinho.
- **Sinal.** Se o painel passar **1 s** sem receber nenhuma mensagem válida, considera que está sem sinal: apaga todos os LEDs, mostra `--` no LCD e "Ponte: sem sinal". A primeira mensagem válida que chegar restabelece o sinal. Com isso, o painel nunca mostra um dado velho como se fosse atual.
- **Botões e chaves fora da cena de voo.** Enquanto não há nave ativa, a ponte lê e **descarta** as mensagens de botão e de chave. Um STAGE apertado no hangar não fica guardado para disparar quando o foguete chegar à plataforma.
- **Quem manda no estado.** O painel só relata o que aconteceu (ex.: "o botão foi apertado"). É a ponte que decide o que fazer, e é o jogo que confirma o resultado. Os LEDs mostram o estado no jogo, não o que o painel pediu.

## Tela multifunção (mikromedia)

Protocolo entre a ponte da tela (`bridge/mfd.py`) e a mikromedia for ARM. Enquanto o firmware da placa não existe, quem responde é o simulador (`bridge/mfd_simulador.py`), que segue estas mesmas regras. Roteiro e testes: [mfd.md](mfd.md).

A camada física e o enquadramento são os mesmos do painel: 115200 baud, uma mensagem por linha, no máximo 31 caracteres, e `ERR <linha>` para o que a tela não reconhece.

No **celular** (`bridge/mfd_celular.py`), as mesmas linhas vão por HTTP, pelo Wi-Fi:

- ponte → celular: a página abre `GET /eventos`, um fluxo *Server-Sent Events* que fica aberto, e cada linha do protocolo chega como um evento (`data: ALT 84321`);
- celular → ponte: cada linha vai num `POST /linha`, com a linha no corpo (no máximo 64 bytes);
- a página manda `READY` sempre que o fluxo de eventos abre, inclusive quando reconecta sozinha.

### Tela → ponte

| Mensagem | Quando | Significado |
|---|---|---|
| `READY` | Ao terminar de ligar | A tela está pronta. A ponte reenvia tudo. |
| `TOQUE <nome>` | Um botão da tela foi tocado | Uma vez por toque. Botões hoje: `SAS` e `RCS` (redondos, embaixo da navball) e `MODO` (a caixa da velocidade). |
| `ERR <linha>` | Chegou uma linha que a tela não reconhece | Devolve a linha recebida |

### Ponte → tela

Ângulos e velocidades vão em **décimos**, como inteiros: 45,3° vira `453`, e 345,6 m/s vira `3456`.

**Estados**, que vão quando mudam e também 1 vez por segundo:

| Mensagem | Valores | Efeito na tela |
|---|---|---|
| `MODO <SUP\|ORB\|ALVO>` | Velocidade em relação à superfície, à órbita ou ao alvo | Título da caixa da velocidade e o que o painel de baixo mostra. Vai **antes** dos números |
| `SAS <0\|1>`, `RCS <0\|1>` | `1` = ligado no jogo | Cor do botão: verde = ligado |

**Navball.** Cada marcador é uma direção no mundo, em `<pitch> <rumo>`; a tela desenha também o marcador oposto, do outro lado da bola. `OFF` esconde os dois.

| Mensagem | Direção | Marcadores | Frequência |
|---|---|---|---|
| `ATT <pitch> <rumo> <rolagem>` | pitch de -900 a 900; rumo de 0 a 3599 (0 = norte, 900 = leste); rolagem de -1800 a 1800 | A bola e os números do rumo e do pitch pintados nela | 20 por segundo |
| `PRO <p> <r>` ou `PRO OFF` | Do movimento, no modo da navball. `OFF` com a nave parada (menos de 0,5 m/s) | Pró-grado e retrógrado, em amarelo | 10 por segundo |
| `NRM <p> <r>` ou `NRM OFF` | Normal à órbita (numa órbita para leste, aponta para o norte). `OFF` no modo `ALVO`, parado ou andando na vertical | Normal e antinormal, em roxo | 10 por segundo |
| `RDL <p> <r>` ou `RDL OFF` | Radial para fora: perpendicular ao movimento, do lado de fora do planeta. `OFF` como o `NRM` | Radial para fora e para dentro, em ciano | 10 por segundo |
| `TGT <p> <r>` ou `TGT OFF` | Do alvo. `OFF` sem alvo ou com o alvo a menos de 1 m | Alvo e anti-alvo, em rosa, em qualquer modo | 10 por segundo |
| `MNV <p> <r>` ou `MNV OFF` | Da queima que falta no próximo nó de manobra. `OFF` sem nó ou com a queima terminada | Nó de manobra, em azul (sem oposto) | 10 por segundo |
| `FBW <p> <r>` ou `FBW OFF` | Para onde o fly by wire (`scripts/fbw.py`) está levando o avião: o ponto do manche, já corrigido pela trava de altitude. `OFF` sem o FBW voando | Ponto do FBW: quatro cantos de um quadrado, em verde (sem oposto), em qualquer modo | 10 por segundo |

**Números**, que valem só até chegar um `MODO` diferente, exceto `VV` e `ACEL`:

| Mensagem | Valores | Efeito na tela | Frequência |
|---|---|---|---|
| `ALT <metros>` | Acima do nível do mar | Caixa `ALT` | 10 por segundo |
| `RAD <metros>` | Acima do chão, ou do mar se ele estiver mais perto. Vai no lugar do `ALT` perto do chão | Caixa `RADAR` | 10 por segundo |
| `VEL <décimos de m/s>` | Velocidade no modo da navball | Caixa da velocidade | 10 por segundo |
| `VV <décimos de m/s>` | Velocidade vertical: positiva subindo, negativa descendo. Em todo modo | Barra da direita | 10 por segundo |
| `ACEL <0 a 100>` | Acelerador, em % | Barra da esquerda | 10 por segundo |
| `DIST <metros>` ou `DIST OFF` | Distância até o alvo. Só no modo `ALVO` | Painel: `DIST` | 10 por segundo |
| `AP <metros>` ou `AP OFF` | `OFF` numa trajetória de escape, que não tem apoastro. Só no modo `ORB` | Painel: `AP` | 2 por segundo |
| `PE <metros>` ou `PE OFF` | Negativo quando a órbita passa por dentro do planeta. Só no modo `ORB` | Painel: `PE` | 2 por segundo |
| `TAP <segundos>` ou `TAP OFF` | Tempo até o apoastro. Só no modo `ORB` | Painel: `T-00:27:53` ao lado do `AP` | 2 por segundo |
| `TPE <segundos>` ou `TPE OFF` | Tempo até o periastro. Só no modo `ORB` | Painel: ao lado do `PE` | 2 por segundo |

Distâncias e tempos são inteiros de 32 bits. Acima de 2,1 milhões de km, o que só acontece com planetas distantes, `DIST`, `AP` e `PE` vão como `OFF`, e a tela mostra `---`.

### Scripts → ponte da tela

Um script de voo pode pôr um marcador na navball sem depender da ponte. Hoje, só o fly by wire faz isso.

- O script manda a **própria linha do protocolo da tela** (`FBW 52 2700` ou `FBW OFF`), num pacote **UDP** para a porta **50100** do computador da ponte, 10 vezes por segundo. Sem a ponte aberta, o pacote se perde e o script segue voando.
- A ponte (`bridge/mfd.py`) escuta em todas as redes (o script pode rodar noutro computador), confere a linha e a repassa para a tela na vez dos marcadores. Linhas que não entende, ela mostra no terminal e descarta.
- Se o script parar de mandar por **1 s** (fechou ou travou), a ponte manda `FBW OFF`.

### Comportamento

- **A tela só desenha.** Toda conta que envolve o jogo é feita na ponte, e a tela recebe as direções prontas. A imagem não vai pela serial: um quadro de 320x240 com 16 bits por ponto tem 150 KB, o que levaria 13 s a 115200 baud. A atitude inteira cabe numa linha de 20 caracteres, e tudo junto dá uns 2 KB/s, menos de 20% da serial.
- **Marcadores a 10 por segundo, atitude a 20.** Os marcadores são direções fixas no mundo, que mudam devagar; quem faz eles andarem na bola é a atitude da nave. A tela reprojeta todos a cada `ATT`.
- **Sinal.** Se a tela passar **1 s** sem receber nenhuma mensagem válida, mostra `SEM SINAL` na navball, `---` nos números, esvazia as barras e apaga os botões. O `ALT` (ou o `RAD`), que vai 10 vezes por segundo, serve de "estou vivo". Fora da cena de voo a ponte não manda nada, então a tela também mostra `SEM SINAL`.
- **O botão mostra o estado do jogo, não o toque**, como os LEDs do painel. `TOQUE SAS` faz a ponte inverter o SAS, e o botão só fica verde quando o jogo confirma. Se a nave não tem SAS, o botão continua apagado, e está certo.
- **O que depende do modo.** Altitude, `VEL`, as duas barras e os marcadores aparecem sempre. O painel de baixo mostra `AP` e `PE` com o tempo até cada um no `ORB` e `DIST` no `ALVO`; no `SUP` ele não aparece, porque a velocidade vertical já está na barra. Normal e radial não existem no `ALVO`; o ponto do FBW, o alvo e a manobra aparecem em qualquer modo. Quando o `MODO` muda, a tela apaga os números do modo antigo e os marcadores pró-grado, normal e radial, e a ponte manda os novos na mesma hora, logo depois do `MODO`.
- **Altitude pelo radar.** A ponte manda `RAD` no lugar de `ALT` quando o radar fica abaixo de 5 km, e só volta ao `ALT` acima de 5,5 km. Essa folga evita ficar trocando quando o terreno sobe e desce perto do limite.
- **O modo é da ponte**, e ela troca sozinha como a navball do KSP:
  - `ORB` quando a nave sobe acima de 6% do raio do planeta (36 km em Kerbin), e `SUP` quando desce abaixo de 5,5% (33 km);
  - `ALVO` quando um alvo é escolhido no jogo (uma nave, uma porta de acoplamento ou um planeta), ou trocado por outro; sem alvo, volta para `SUP` ou `ORB` conforme a altitude;
  - `TOQUE MODO` passa para o próximo modo: `SUP` → `ORB` → `ALVO` (se houver alvo) → `SUP`. A escolha vale até a próxima troca automática.
