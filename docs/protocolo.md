# Protocolo serial v0 (texto)

Protocolo entre o computador de bordo (a ponte, `bridge/ponte.py`) e as placas (hoje, o Mega com `firmware/painel/painel.ino`). É texto puro, para dar para testar e depurar pelo Serial Monitor. A versão binária (v1, com COBS e CRC) vem na fase 5.

## Camada física e enquadramento

- Serial pela USB, **115200 baud**, 8N1.
- Texto ASCII, **uma mensagem por linha**, terminada em `\n`. Um `\r` antes do `\n` é ignorado.
- Formato: `COMANDO` ou `COMANDO VALOR`, separados por **um** espaço. Maiúsculas e minúsculas fazem diferença.
- Linhas vazias são ignoradas. Linhas com mais de 31 caracteres são descartadas inteiras.

## Mensagens

### Painel → ponte

| Mensagem | Quando | Significado |
|---|---|---|
| `READY` | Ao terminar de ligar (inclusive depois de um reset) | O painel está pronto para receber. Tudo o que foi enviado antes disso se perdeu. |
| `BTN STAGE 1` | O botão STAGE foi apertado | Enviada **uma vez por mudança**, já sem trepidação (debounce de 20 ms) |
| `BTN STAGE 0` | O botão STAGE foi solto | idem |
| `ERR <linha>` | Chegou uma linha que o painel não reconhece | Devolve a linha recebida, para ajudar a depurar |

### Ponte → painel

| Mensagem | Valores | Efeito no painel |
|---|---|---|
| `SAS <0\|1>` | `0` desligado, `1` ligado | LED do SAS e linha "SAS" do LCD |
| `ALT <metros>` | Inteiro com sinal, 32 bits | Linha "Alt" do LCD |

## Comportamento

- **Reset ao abrir a porta.** Abrir a serial reinicia o Mega, que leva cerca de 2 s para voltar. A ponte espera o `READY` antes de enviar qualquer coisa. Se receber `READY` no meio do voo, o painel reiniciou, e a ponte reenvia o estado.
- **Frequência de envio.** A ponte envia `ALT` 10 vezes por segundo, mesmo que a altitude não mude. `SAS` vai quando muda e também uma vez por segundo, caso alguma mensagem tenha se perdido.
- **Sinal.** Se o painel passar **1 s** sem receber nenhuma mensagem válida, considera que está sem sinal: apaga o LED do SAS, mostra `--` no LCD e "Ponte: sem sinal". A primeira mensagem válida que chegar restabelece o sinal. Com isso, o painel nunca mostra um dado velho como se fosse atual.
- **Botões fora da cena de voo.** Enquanto não há nave ativa, a ponte lê e **descarta** as mensagens de botão. Um STAGE apertado no hangar não fica guardado para disparar quando o foguete chegar à plataforma.
- **Quem manda no estado.** O painel só relata o que aconteceu (ex.: "o botão foi apertado"). É a ponte que decide o que fazer, e é o jogo que confirma o resultado. O LED mostra o estado do SAS no jogo, não o que o painel pediu.
