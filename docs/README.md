# Documentação

A documentação detalhada do [KSP Cockpit](../README.pt-BR.md). Para começar, leia a [arquitetura](arquitetura.md) e depois o [roteiro](roteiro.md), que diz o que já está pronto em cada fase.

## Visão geral

| Documento | O que tem |
|---|---|
| [arquitetura.md](arquitetura.md) | Como as partes se ligam, o papel de cada uma, os princípios e a estrutura do repositório |
| [decisoes.md](decisoes.md) | Cada escolha do projeto e o porquê, incluindo as que foram trocadas depois |
| [roteiro.md](roteiro.md) | As 8 fases, do ambiente ao hardware definitivo, com o critério de pronto e o que falta em cada uma |
| [protocolo.md](protocolo.md) | O protocolo serial v0, em texto, mensagem por mensagem: o painel, a tela, o encoder e os scripts |
| [compras.md](compras.md) | A lista de compras, por fase |

## Montar e ligar

| Documento | O que tem |
|---|---|
| [setup-pi.md](setup-pi.md) | Fase 0: o Raspberry Pi 4 e o PC, o cabo de rede direto e a ponte da tela abrindo sozinha |
| [fase1.md](fase1.md) | Fase 1, passo a passo: um botão, um LED e um LCD no Mega, em circuito fechado com o jogo |
| [fase2.md](fase2.md) | Fase 2: chaves, botões e LEDs direto nos pinos do Mega, e como acrescentar um controle |
| [encoder.md](encoder.md) | O encoder AJUSTE da tela, num Arduino Uno: ligação, gravação e a ponte |
| [mikromedia.md](mikromedia.md) | O firmware da tela na mikromedia for ARM: gravar, ligar, compilar e como ele funciona |

## A tela multifunção

| Documento | O que tem |
|---|---|
| [mfd.md](mfd.md) | A tela: a navball, o simulador, o celular, o tablet do cockpit, a página MAPA e as páginas dos painéis de sistemas e de scripts |
| [manobras.md](manobras.md) | O editor de nós de manobra, com botões no navegador |
| [avisos.md](avisos.md) | Os avisos de voo por voz, como o GPWS, e a luz do painel |

## Scripts de voo

| Documento | O que tem |
|---|---|
| [scripts-de-voo.md](scripts-de-voo.md) | Todos os scripts, os prontos e as ideias, e a base comum a eles |
| [subida.md](subida.md) | A subida automática até a órbita: como usar, as contas e o teste no jogo |
| [rendezvous.md](rendezvous.md) | O rendezvous automático até 100 m de outra nave |
| [fbw.md](fbw.md) | O fly by wire de avião, com a lei de um caça, e o piloto automático |
| [roteiro.md, fase 5](roteiro.md#fase-5--protocolo-v1--scripts-de-voo) | O pouso autônomo com queima de suicídio |

## Hardware

| Documento | O que tem |
|---|---|
| [hardware/README.md](../hardware/README.md) | Os módulos do painel, o backplane, as etiquetas, a ligação e a lista de peças por placa |
| [hardware/construcao.md](../hardware/construcao.md) | O cockpit versão B, a caixa, cada painel e o joystick |
| [hardware/korry/README.md](../hardware/korry/README.md) | O korry feito em casa: medidas, peças, impressão, montagem e circuito |
| [hardware/identidade_visual.md](../hardware/identidade_visual.md) | Cores, letras, peças e as regras para desenhar um painel |
| [hardware/desenho/README.md](../hardware/desenho/README.md) | Os desenhos dos painéis, gerados por código |

As imagens usadas nos documentos ficam em [img/](img/).
