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

### Tela → ponte

| Mensagem | Quando | Significado |
|---|---|---|
| `READY` | Ao terminar de ligar | A tela está pronta. A ponte reenvia tudo. |
| `TOQUE <nome>` | Um botão da tela foi tocado | Uma vez por toque. Botões hoje: `SAS`, `RCS` e `MODO`. |
| `ERR <linha>` | Chegou uma linha que a tela não reconhece | Devolve a linha recebida |

### Ponte → tela

Ângulos vão em **décimos de grau**, como inteiros: 45,3° vira `453`.

| Mensagem | Valores | Efeito na tela | Frequência |
|---|---|---|---|
| `ATT <pitch> <rumo> <rolagem>` | pitch de -900 a 900; rumo de 0 a 3599 (0 = norte, 900 = leste); rolagem de -1800 a 1800 | Navball e o `RUMO` acima dela | 20 por segundo |
| `PRO <pitch> <rumo>` | Direção do movimento, no modo da navball | Marcadores pró-grado e retrógrado | 20 por segundo |
| `PRO OFF` | Nave parada (menos de 0,5 m/s) | Esconde os marcadores | idem |
| `ALT <metros>` | Inteiro com sinal, 32 bits; acima do nível do mar | `ALT` | 10 por segundo |
| `VEL <décimos de m/s>` | `3456` = 345,6 m/s, no modo da navball | `VEL` | 10 por segundo |
| `AP <metros>` ou `AP OFF` | `OFF` numa trajetória de escape, que não tem apoastro | `AP` | 2 por segundo |
| `PE <metros>` ou `PE OFF` | Negativo quando a órbita passa por dentro do planeta | `PE` | 2 por segundo |
| `SAS <0\|1>`, `RCS <0\|1>` | `1` = ligado no jogo | Cor do botão: verde = ligado | Quando muda, e todos 1 vez por segundo |
| `MODO <SUP\|ORB>` | Velocidade em relação à superfície ou à órbita | Texto do botão `MODO` e da `VEL` | idem |

### Comportamento

- **A tela só desenha.** Toda conta que envolve o jogo é feita na ponte, e a tela recebe os ângulos prontos. A imagem não vai pela serial: um quadro de 320x240 com 16 bits por ponto tem 150 KB, o que levaria 13 s a 115200 baud. A atitude inteira cabe numa linha de 20 caracteres.
- **Sinal.** Se a tela passar **1 s** sem receber nenhuma mensagem válida, mostra `SEM SINAL` na navball, `---` nos números e apaga os botões. O `ALT`, que vai 10 vezes por segundo, serve de "estou vivo". Fora da cena de voo a ponte não manda nada, então a tela também mostra `SEM SINAL`.
- **O botão mostra o estado do jogo, não o toque**, como os LEDs do painel. `TOQUE SAS` faz a ponte inverter o SAS, e o botão só fica verde quando o jogo confirma. Se a nave não tem SAS, o botão continua apagado, e está certo.
- **O modo é da ponte.** `TOQUE MODO` faz a ponte trocar entre `SUP` e `ORB`, o que muda o que ela manda em `VEL` e `PRO`. A tela só mostra o modo que recebe em `MODO`.
