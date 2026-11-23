# bridge: o computador de bordo

O código Python que roda no Raspberry Pi, ou no PC durante o desenvolvimento. Ele liga o jogo, pelo kRPC, às placas do painel e à tela multifunção. Como as partes se ligam está na [arquitetura](../docs/arquitetura.md).

Por enquanto são duas pontes separadas: a do painel (`ponte.py`), que fala com o Arduino Mega pela serial, e a da tela (`mfd.py`), que é a que o Pi abre sozinho quando liga. A da tela também cuida da página de botões que faz o papel dos painéis de sistemas e de scripts enquanto os módulos não existem.

| Arquivo | O que faz |
|---|---|
| [`ponte.py`](ponte.py) | Ponte kRPC ⇄ painel (Arduino Mega), no [protocolo](../docs/protocolo.md) v0 em texto ([fase 2](../docs/fase2.md)) |
| [`mfd.py`](mfd.py) | Ponte kRPC ⇄ tela multifunção: lê o jogo, manda a navball, a telemetria e as páginas, e executa os toques ([docs/mfd.md](../docs/mfd.md)) |
| [`mfd_simulador.py`](mfd_simulador.py) | O simulador da tela, numa janela, na resolução da mikromedia |
| [`mfd_celular.py`](mfd_celular.py) | Serve a página da tela para o navegador do tablet ou do celular |
| [`celular/`](celular/) | As páginas do navegador: a tela (`index.html`), a página de botões dos painéis (`painel.html`) e o editor de manobras (`manobras.html`) |
| [`navball.py`](navball.py) | A conta que desenha a navball |
| [`mapa.py`](mapa.py) | O mapa da órbita em 3D, na página MAPA do tablet |
| [`sistemas.py`](sistemas.py) | Painel de sistemas de controle: os modos do SAS, o SAS, o RCS, o FBW e o piloto automático |
| [`painel_scripts.py`](painel_scripts.py) | Painel de scripts: segurar o korry POUSO ou LANCAR 5 s abre o script de voo, e segurar de novo aborta |
| [`ajuste.py`](ajuste.py) | O encoder AJUSTE, num Uno à parte ([encoder.md](../docs/encoder.md)) |
| [`avisos.py`](avisos.py) | Os avisos de voo por voz, como o GPWS ([avisos.md](../docs/avisos.md)) |
| [`manobras.py`](manobras.py) | O editor de nós de manobra, com botões no navegador ([manobras.md](../docs/manobras.md)) |
| [`fase0_altitude.py`](fase0_altitude.py) | Fase 0: imprime a altitude ao vivo, para testar a conexão com o jogo |
| [`servico/`](servico/) | O serviço do systemd que abre a ponte da tela quando o Pi liga ([setup-pi.md](../docs/setup-pi.md#9-a-ponte-da-tela-abrindo-sozinha)) |
| [`tests/`](tests/) | Os testes, que rodam sem o jogo |

## Usar

A tela com uma nave de mentira, sem o jogo, no navegador (http://localhost:8000 e, para os botões, http://localhost:8001):

```bash
python bridge/mfd.py --demo --celular
```

Com o jogo aberto neste computador, ou em outro, pelo IP:

```bash
python bridge/mfd.py 192.168.1.10 --celular
```

Todas as opções:

```bash
python bridge/mfd.py --help
```

As dependências estão no [`requirements.txt`](../requirements.txt) da raiz.

## Testes

```bash
python -m unittest discover -s bridge/tests
```
