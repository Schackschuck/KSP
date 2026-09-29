# Avisos de voo por voz (GPWS)

**Pronto quando:** voando baixo no jogo, a caixa de som ligada no Pi fala `SINK RATE`, `TERRAIN`, `PULL UP` e os outros avisos na hora certa, a luz GPWS do painel acende junto e o pouso normal só tem as chamadas de altura.

Como o GPWS dos aviões de linha (o "Ground Proximity Warning System"), a ponte da tela ([`bridge/avisos.py`](../bridge/avisos.py), chamado pelo `mfd.py`) olha a altura acima do chão, a velocidade vertical, o trem de pouso, a inclinação e a pressão dinâmica, e fala o aviso em inglês. Vale em **qualquer nave voando na atmosfera**, com ou sem o [fly by wire](fbw.md), porque quem lê o jogo é a ponte.

**Onde estamos:** a lógica passa nos testes ([`bridge/tests/test_avisos.py`](../bridge/tests/test_avisos.py)); a voz foi testada só no terminal. Falta ouvir no Pi, com o alto-falante USB, e voar no jogo.

## Os avisos

Em ordem de prioridade: só o mais importante fala, e duas frases nunca saem juntas (pelo menos 1 s entre elas).

| Frase | Quando | Luz | Repete |
|---|---|---|---|
| **PULL UP** | Descendo muito rápido para a altura (mais que 8,6 m/s + 4,2% da altura, abaixo de 750 m), ou o TERRAIN continua por 1,6 s | PULL UP, vermelha piscando | A cada 1,2 s |
| **TERRAIN, TERRAIN** | O chão chegando rápido (a altura caindo mais que 10 m/s + 7,5% da altura, abaixo de 500 m), com o trem recolhido: um morro na frente, ou mergulhando | PULL UP, vermelha piscando | A cada 2,5 s |
| **TOO LOW, TERRAIN** | Abaixo de 150 m, com o trem recolhido e a mais de 100 m/s (fora da decolagem) | GPWS âmbar | A cada 3 s |
| **TOO LOW, GEAR** | Abaixo de 150 m, com o trem recolhido e a menos de 100 m/s: esqueceu o trem no pouso | GPWS âmbar | A cada 3 s |
| **SINK RATE** | Descendo rápido para a altura (mais que 4,9 m/s + 2,8% da altura, abaixo de 750 m): a 100 m, 7,7 m/s | GPWS âmbar | A cada 2 s |
| **DON'T SINK** | Depois da decolagem, abaixo de 300 m, perdendo altura (10 m, ou 10% da maior altura desde a decolagem) | GPWS âmbar | A cada 2 s |
| **BANK ANGLE, BANK ANGLE** | Inclinação alta perto do chão, abaixo de 300 m: 45° acima de 40 m, e menos perto do chão (10° no chão) | GPWS âmbar | Uma vez por inclinação: fala de novo depois de voltar abaixo do limite |
| **OVERSPEED** | Pressão dinâmica acima de 50 kPa (uns 290 m/s ao nível do mar), em qualquer altura | GPWS âmbar | A cada 3 s |
| **One hundred, fifty, forty, thirty, twenty, ten** | No pouso, com o trem baixado e descendo, ao passar por 100, 50, 40, 30, 20 e 10 pés de altura (30 m a 3 m) | — | Uma vez; rearma acima de 200 pés |

- **Só no ar e na atmosfera:** no chão, ou com a pressão dinâmica abaixo de 500 Pa (fora da atmosfera, ou quase parado), nada fala.
- **A altura é a do radar** (acima do chão, ou do mar), a mesma do `RADAR` da tela.
- **Nave sem trem** (sem rodas nem pernas): os avisos de trem e as chamadas de altura não valem.
- **A decolagem** só conta se a ponte viu o avião no chão antes. Abrindo a ponte com o avião já voando, o DON'T SINK não arma.
- Os números estão no começo do [`avisos.py`](../bridge/avisos.py). São os do GPWS de verdade, passados para metros, e podem precisar de ajuste para os aviões do KSP.

## A voz

A frase sai pelo **`espeak-ng`**, um sintetizador de voz que roda no Pi, ou por uma **gravação**: se existir `bridge/sons/<nome>.wav` (ex.: `pull_up.wav`, `sink_rate.wav`, `100.wav`), ela toca no lugar da voz sintetizada. Os nomes são as chaves de `FRASES` no `avisos.py`, em minúsculas.

Sem o `espeak-ng` e sem gravação, o aviso só aparece no terminal (`[AVISO] SINK RATE`). A voz toca numa thread separada: a ponte não trava enquanto fala.

### Instalar no Pi

```bash
sudo apt install -y espeak-ng alsa-utils
```

Com o **alto-falante USB** ligado:

```bash
aplay -l                          # lista as placas de som; o USB aparece como "card 1", por exemplo
speaker-test -D plughw:1,0 -t wav -c 2 -l 1   # ouve "front left, front right" no USB
```

Para a voz sair no USB, dê o dispositivo à ponte:

```bash
python KSP/bridge/mfd.py 192.168.1.10 --porta /dev/ttyUSB0 --voz plughw:1,0
```

Sem `--voz`, a voz sai no som padrão do Pi. Para deixar o USB como padrão (e não precisar do `--voz`), crie o arquivo `~/.asoundrc` com:

```
defaults.pcm.card 1
defaults.ctl.card 1
```

### Testar

```bash
python KSP/bridge/mfd.py --testar-voz --voz plughw:1,0
```

Fala cada aviso, um a cada 2 s, e sai. `--sem-voz` deixa os avisos só no terminal e na luz.

## No painel

A linha `GPWS <0|1|2>` vai para o painel de sistemas ([protocolo](protocolo.md#painel-de-sistemas-de-controle)): `1` acende **GPWS** em âmbar, `2` acende **PULL UP** em vermelho, piscando. Na página de botões, a luz fica embaixo da ESTOL. A tela multifunção não recebe essa linha: o aviso é a voz.

**No painel de verdade**, a luz ainda não está no desenho ([painel de sistemas](../hardware/construcao.md#painel-de-sistemas-de-controle)): falta um LED bicolor (vermelho e âmbar) com a legenda GPWS / PULL UP, ao lado do ESTOL.

## Testar no jogo

Com a ponte aberta e a voz testada, num avião pequeno:

| Você faz | Resultado esperado |
|---|---|
| Decola e sobe | Nada fala |
| A uns 100 m, depois da decolagem, desce de propósito | `DON'T SINK`, luz GPWS âmbar |
| Voa reto a 100 m com o trem recolhido, devagar | `TOO LOW, GEAR` |
| O mesmo, rápido | `TOO LOW, TERRAIN` |
| A 300 m, mergulha a uns 30 m/s | `SINK RATE`, e `PULL UP` com a luz vermelha se piorar |
| Voa baixo e rápido na direção de um morro | `TERRAIN, TERRAIN` e, se continuar, `PULL UP` |
| A 100 m, inclina mais de 45° | `BANK ANGLE, BANK ANGLE`, uma vez |
| Mergulha até passar de uns 290 m/s perto do mar | `OVERSPEED` |
| Pousa normalmente, com o trem baixado, descendo a 3 m/s | Só `one hundred`, `fifty`, `forty`, `thirty`, `twenty`, `ten` |

## Próximos passos

1. **Ouvir no Pi** com o alto-falante USB e ajustar os limites no jogo.
2. **Gravações** melhores que o `espeak-ng`, em `bridge/sons/`.
3. **Luz GPWS no painel de verdade** (o desenho e o LED).
4. **Olhar à frente** (o "E" do EGPWS): comparar o caminho do avião com a altura do terreno à frente. O kRPC dá a altura do terreno em qualquer ponto (`body.surface_height`).
