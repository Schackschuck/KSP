# Subida automática até a órbita

O [`scripts/subida.py`](../scripts/subida.py) leva a nave da plataforma até uma órbita circular. O piloto escolhe a altitude e a inclinação, ou pede o plano de um alvo. O script decola, faz a curva de gravidade com o giro escolhido por simulação, corta o motor quando o apoastro chega na altitude pedida, circulariza e, se for o caso, iguala o plano do alvo. Funciona em qualquer planeta, com ar ou sem.

**Status: escrito e testado numa nave simulada; falta testar no jogo.** Os testes sem o KSP estão em [`scripts/tests/test_subida.py`](../scripts/tests/test_subida.py), e o roteiro para o jogo está [abaixo](#testar-no-jogo).

## Como usar

**Pela linha de comando**, como o pouso, no PC ou no Pi:

```
python scripts/subida.py                                     # KSP neste computador: 80 km, 0°
python scripts/subida.py --altitude 100000 --inclinacao 45   # 100 km, 45°
python scripts/subida.py --plano-do-alvo                     # no plano do alvo escolhido no jogo
python scripts/subida.py 192.168.50.1                        # KSP noutro computador (do Pi, pelo cabo)
python scripts/subida.py --demo                              # sem o KSP: uma nave simulada sobe de Kerbin
```

A nave tem que estar parada no chão, com o primeiro estágio ainda por acender. O script dá a ignição e troca de estágio sozinho. A carenagem (fairing) fica com o piloto. Ctrl+C corta o motor e devolve a nave.

**No cockpit**, a subida tem uma página na tela multifunção, a SUBIDA, e um korry, o LANCAR, no painel de scripts. Enquanto o painel não existe, os dois ficam na página de botões ([docs/mfd.md](mfd.md#painel-de-scripts-e-a-página-do-pouso)):

1. Gire o encoder da subida: a tela abre a página SUBIDA, com três linhas, `ALTITUDE`, `INCLINACAO` e `PLANO DO ALVO`.
2. Girando, o cursor passa pelas linhas; apertando, a linha fica escolhida (a caixa âmbar), e girando muda o valor. Devagar, 1 km ou 1°; rápido, 10. Apertando de novo, sai da linha.
3. Para o plano de um alvo, escolha o alvo no jogo antes (uma nave ou um planeta que orbite o mesmo planeta da base) e ligue o `PLANO DO ALVO`.
4. Segure o LANCAR 5 s. O korry pisca âmbar contando, fica verde com o script voando, e a página passa a mostrar o voo. Segurar de novo 5 s aborta.
5. No fim, a página mostra `EM ORBITA`, `ABORTADO` ou `FALHOU` por 10 s.

**A página SUBIDA só aparece na mikromedia.** O simulador e o celular aceitam as linhas dela, mas mostram a navball. Depois de mudar o firmware, é preciso gravar o `mfd.hex` de novo pelo Flash Magic ([docs/mikromedia.md](mikromedia.md)).

## As fases

| Fase | O que acontece |
|---|---|
| `JANELA` | Só com o plano de um alvo: acelera o tempo até 60 s antes de a base passar debaixo do plano, e espera o resto em tempo real |
| `DECOLAGEM` | Ignição e subida na vertical, medindo a área de arrasto, até 50 m/s e 100 m do chão (300 m sem ar) |
| `GIRO` | Escolhe o giro por simulação e inclina o nariz desse ângulo, até o movimento acompanhar |
| `CURVA` | No ar: o nariz segue o movimento em relação ao ar, com ângulo de ataque perto de zero. É a curva de gravidade |
| `VACUO` | Acima de 60% da atmosfera (ou sem ar): o nariz segue o pró-grado orbital |
| `COSTA` | Motor cortado com o apoastro na altitude pedida. Sobe até o apoastro, com time warp, acendendo de leve se o ar baixar o apoastro |
| `CIRCULARIZA` | Queima em malha fechada até a velocidade circular, centrada no apoastro |
| `PLANO` | Só com o plano de um alvo: queima na linha dos nós para tirar o erro de plano que sobrou |
| `ORBITA` | Fim bom: o script sai com o código 0 |
| `FALHA` | Fim ruim: o motor é cortado, e o script sai com o código 1 |

Os estágios saem sozinhos em qualquer fase, quando algum motor ativo fica sem combustível ou o empuxo acaba, desde que ainda haja motor nos estágios de baixo. Sem motor nenhum embaixo, é `FALHA`, com o aviso `COMBUSTIVEL`.

## As contas

### O rumo

Para cair na inclinação `i` a partir da latitude `φ`, o rumo "parado no espaço" sai de `sen β = cos(i) / cos(φ)`. O planeta gira, e a nave já sai com a velocidade do chão para leste.

O script não usa essa fórmula uma vez só. A cada passo, ele mira a velocidade horizontal que ainda falta: a velocidade circular da órbita pedida, na direção do plano, menos a velocidade horizontal de agora. No chão, a velocidade horizontal é a rotação, e a conta dá o rumo com a rotação descontada. Por exemplo, em Kerbin, para 80 km e 45°, o rumo é 41,7°, e não 45°.

No ar denso, o rumo fica a no máximo 3° do rumo do movimento, para o ângulo de ataque continuar pequeno.

### O plano

- **Sem alvo**, o plano é refeito a cada passo, da decolagem até o fim da circularização. É o plano que passa pela posição de agora com a inclinação pedida, com o ramo para o norte ou para o sul escolhido pela velocidade de agora. A rotação do planeta empurra a nave para fora do plano da decolagem; refazendo o plano, ela não precisa voltar a ele, e a inclinação final sai a menos de 0,1° da pedida. É o que o MechJeb faz, refazendo o rumo pela latitude de agora.
- **Com o plano de um alvo**, o plano é fixo no espaço: o normal da órbita do alvo. O que sobra de erro de posição depois da subida (uns décimos de grau) é tirado pela fase `PLANO`, com uma queima na linha dos nós, onde os dois planos se cruzam.
- **Uma inclinação menor que a latitude da base não existe.** O script lança na menor possível, com o aviso `INCLINACAO`. Do KSC, que fica a −0,1°, qualquer inclinação serve.

### A janela de lançamento

A base fica dentro do plano do alvo duas vezes por volta do planeta. Em Kerbin, o dia é de 6 h, então a espera é de no máximo umas 3 h.

O script gira a posição da base em volta do eixo do planeta e procura o primeiro instante em que ela fica no plano: o produto do normal do plano pela direção da base troca de sinal. A procura amostra uma volta inteira e refina por bisseção. Se a base nunca passa pelo plano (a latitude é maior que a inclinação do alvo), é `FALHA`, com o aviso `INCLINACAO`.

A Mun tem inclinação 0, e qualquer lançamento para leste do KSC já cai no plano dela. Para Minmus (6°), a janela importa.

### O giro mais eficiente

"Eficiente" é gastar o menor Δv somando a subida e a circularização. Três perdas brigam entre si:

- **gravidade:** cada segundo subindo na vertical gasta `g` à toa, e ela pede para curvar cedo;
- **arrasto:** curvar cedo deixa a nave rápida no ar denso, e ele pede para curvar tarde;
- **direção:** apontar fora do movimento gasta empuxo de lado e põe força de ar na nave.

Na curva de gravidade, o único parâmetro do perfil é o **giro**: o quanto o nariz inclina no começo. Depois, o nariz só segue o movimento, e a gravidade curva a trajetória sozinha.

No fim da decolagem, o script simula a subida inteira, em 2D, no plano da órbita. A simulação conta:

- a gravidade;
- o empuxo e o Isp de cada estágio, que mudam com a pressão;
- o arrasto, com a área medida na decolagem;
- a troca de estágios e o limite de pressão dinâmica;
- o corte no apoastro, a costa no ar e a circularização.

Ela testa 12 giros na faixa (de 0,5° a 30° com ar; de 5° a 85° sem) e refina o melhor por seção áurea. Leva uns 20 ms. Em Kerbin, com o foguete de teste, o giro escolhido é de uns 7,5° e o voo gasta uns 3 300 m/s até 80 km.

Os estágios da simulação vêm do jogo: os motores e o combustível que cada separação larga. A conta vale bem para foguetes em série. Com boosters laterais ou asparagus, a previsão erra um pouco, e o resto do voo, que é em malha fechada, corrige.

### O corte e a circularização

- **O corte:** o apoastro sai da posição e da velocidade (vis-viva). Faltando menos de 5 km, o motor vai baixando; ele corta com o apoastro a 100 m do pedido. Na costa, ainda no ar, se o arrasto baixar o apoastro mais de 300 m, o motor acende a 10% até corrigir.
- **A circularização:** `Δv = √(μ/ra) − v_ap`, com a duração pela equação do foguete. Ela começa metade da duração antes do apoastro, com o time warp parando 30 s antes. A queima é em malha fechada: a cada passo, mira a diferença entre a velocidade circular ali, no plano, e a velocidade de agora. O motor só acende com o nariz a menos de 5° dessa direção e vai baixando no fim, para terminar em uns 3 s. Termina com menos de 0,3 m/s de diferença.

### O limite de pressão dinâmica

Acima de 30 kPa, o motor vai baixando, até 40% em 50 kPa. Protege a nave sem mudar muito o perfil.

## Avisos

| Aviso | Quando | O que acontece |
|---|---|---|
| `EMPUXO` | O empuxo/peso na decolagem está abaixo de 1,05 | Só o aviso: a nave tenta subir |
| `ALTITUDE` | A altitude pedida está dentro do ar (menos de 5 km acima do topo) ou, sem ar, abaixo de 10 km | Não decola |
| `INCLINACAO` | A inclinação pedida é menor que a latitude da base; ou a base nunca passa pelo plano do alvo | Lança na menor possível; sem janela, não decola |
| `ALVO` | O plano do alvo foi pedido sem alvo, ou com um alvo que orbita outro planeta | Não decola |
| `COMBUSTIVEL` | Acabaram os motores antes da órbita, ou nenhum giro simulado chegou em órbita | Motor cortado, `FALHA` (no segundo caso, voa com o giro padrão) |

## Testar sem o KSP

```
python scripts/tests/test_subida.py -v
python scripts/subida.py --demo
python scripts/subida.py --demo --plano-do-alvo
```

- **Os testes** voam a guiagem numa nave simulada: um ponto de massa em volta de Kerbin ou da Mun, que giram, com atmosfera, arrasto, estágios e o nariz virando a no máximo 15°/s. Eles cobrem as contas, o giro escolhido, voos em várias inclinações e latitudes, o plano de um alvo com a janela e a falta de combustível.
- **O `--demo`** faz a mesma nave simulada subir de Kerbin, 4 vezes mais rápido que o tempo real, mandando as linhas `SUB` para a ponte da tela. Com `--plano-do-alvo`, o alvo é um plano de mentira de 10°, com a janela a uns 20 min de jogo.
- **Pela ponte da tela**, `python bridge/mfd.py --demo --porta <porta da mikromedia>` abre a página de botões, e segurar o LANCAR 5 s abre o `subida.py --demo` com os valores da página SUBIDA.

## Testar no jogo

Comece com uma órbita sem inclinação, num foguete simples de dois estágios em série, com empuxo/peso de uns 1,5 na plataforma.

1. **80 km, 0°**, pela linha de comando, com o jogo na plataforma. Confira na janela do kRPC o cliente "KSP Cockpit", e no terminal a fase, o apoastro e o giro escolhido. Fim: `ORBITA` com o apoastro e o periastro a menos de 1 km de 80 km.
2. **A inclinação:** 100 km e 45°. A inclinação final, no mapa do jogo, tem que bater com a pedida.
3. **O plano de um alvo:** escolha uma nave em órbita inclinada (ou Minmus) como alvo e rode com `--plano-do-alvo`. O script acelera o tempo até a janela, decola e, no fim, a inclinação relativa do mapa do jogo tem que ficar perto de 0°.
4. **Sem ar:** pouse na Mun e rode com `--altitude 20000`.
5. **Pelo cockpit:** a página SUBIDA na mikromedia, o korry LANCAR segurado 5 s e o aborto segurando de novo.

Se algo der errado, anote a fase, o que o terminal imprimiu e o foguete. O primeiro ponto a conferir é a primeira mensagem do script: se o referencial do kRPC não for o que o script espera, ele para antes de decolar, com uma mensagem sobre o referencial.

## Limites

- **Foguetes em série.** Com boosters laterais, a simulação do giro erra um pouco, e a guiagem em voo corrige.
- **A carenagem e os painéis** ficam com o piloto, num action group.
- **O time warp:** abortar durante um `warp_to` corta o motor, mas o warp pode continuar no jogo até o fim.
- **A guiagem do vácuo** segue o pró-grado orbital. A guiagem dos ônibus espaciais (PEG), que é a forma ótima no vácuo, fica para depois.
- **O encoder de verdade** da configuração ainda não tem lugar no painel: por enquanto, é o da página de botões.
