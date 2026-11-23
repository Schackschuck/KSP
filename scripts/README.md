# scripts: os scripts de voo

Cada script pilota a nave pelo kRPC e roda sozinho pela linha de comando, no PC ou no Pi, com ou sem o cockpit. No cockpit, a ponte da tela abre o script quando o korry dele é segurado 5 s, e a tela mostra o voo. As ideias de scripts novos e a base comum estão em [scripts de voo](../docs/scripts-de-voo.md).

| Script | O que faz | Situação | Documentação |
|---|---|---|---|
| [`subida.py`](subida.py) | Leva a nave da plataforma até uma órbita circular, em qualquer planeta, com ar ou sem | Voou no jogo | [subida.md](../docs/subida.md) |
| [`rendezvous.py`](rendezvous.py) | Leva a nave até 100 m de outra, em órbita do mesmo planeta, parada em relação a ela | Voou no jogo | [rendezvous.md](../docs/rendezvous.md) |
| [`pouso.py`](pouso.py) | Queima de suicídio numa descida vertical, em qualquer planeta, contando o arrasto | Em teste no jogo | [fase 5](../docs/roteiro.md#fase-5--protocolo-v1--scripts-de-voo) |
| [`fbw.py`](fbw.py) | Fly by wire de avião, com a lei de um caça, e o piloto automático (HDG, ALT e V/S) | Testado num avião simulado | [fbw.md](../docs/fbw.md) |

## Como são feitos

- **A guiagem não conhece o kRPC:** ela recebe uma leitura da nave e devolve comandos. Por isso os testes voam a mesma guiagem numa nave simulada, sem o jogo.
- **O estado vai para a tela por UDP** na subida, no pouso e no fly by wire (`--tela IP`, se a ponte da tela estiver em outro computador), em linhas do [protocolo da tela](../docs/protocolo.md#painel-de-scripts). Sem a ponte da tela aberta, as linhas se perdem e o script voa do mesmo jeito.
- **Ctrl+C aborta:** o script corta o motor, ou solta o manche no fly by wire, e devolve a nave ao piloto. Na subida, no pouso e no rendezvous, o código de saída diz como o voo terminou.

## Usar

Com uma nave simulada, sem o jogo (`subida.py`, `pouso.py` e `rendezvous.py`):

```bash
python scripts/subida.py --demo
```

Com o jogo aberto neste computador:

```bash
python scripts/subida.py
```

Com o jogo em outro computador, pelo IP, como a partir do Pi:

```bash
python scripts/subida.py 192.168.1.10
```

Cada script mostra as opções com `--help`. As dependências estão no [`requirements.txt`](../requirements.txt) da raiz; o `fbw.py` também precisa de um joystick, ou da opção `--sem-joystick`.

## Testes

Os testes levam uns 3 minutos e não precisam do jogo:

```bash
python -m unittest discover -s scripts/tests
```
