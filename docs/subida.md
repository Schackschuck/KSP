# Subida automática até a órbita

O [`scripts/subida.py`](../scripts/subida.py) leva a nave da plataforma até uma órbita circular. O piloto escolhe a altitude e a inclinação, ou pede o plano de um alvo. O script decola, faz a curva de gravidade com o giro escolhido por simulação, corta o motor quando o apoastro chega na altitude pedida, circulariza e, se for o caso, iguala o plano do alvo. Funciona em qualquer planeta, com ar ou sem.

**Status: voou no jogo em 20/10/2026 e chegou em órbita sozinho, com um foguete de 552 t; o giro ainda está em ajuste.** Os testes sem o KSP estão em [`scripts/tests/test_subida.py`](../scripts/tests/test_subida.py), e o roteiro para o jogo está [abaixo](#testar-no-jogo).

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

**O desenho do voo.** No meio da página, entre os números de cima e a fase embaixo, a tela desenha o voo. É um desenho só (o planeta, a atmosfera, a trajetória e o círculo tracejado do alvo) visto por uma câmera que abre em dois zooms de 1,5 s:

- **Na decolagem**, a câmera fica no KSC: o VAB, a torre da plataforma, a caixa d'água e o foguete, com a chama pelo acelerador. Quando o foguete sobe, ela abre aos poucos para ele não sair da tela.
- **No giro**, o primeiro zoom: o KSC some, o chão vira a curva do planeta e aparece a trajetória prevista, uma parábola. O trecho verde é o já voado, o tracejado o que falta, e a marca âmbar é o apoastro. A parábola cresce até o círculo do alvo.
- **Na circularização**, o segundo zoom: o planeta inteiro, e a parábola, que já era um pedaço da órbita, vira a elipse. O periastro sobe até a órbita fechar no círculo do alvo.

O desenho não está em escala: a altitude é esticada 3 vezes, para a órbita não ficar colada no planeta. Os números de verdade estão em cima. Kerbin aparece visto de cima do polo, como uma órbita equatorial é vista: o gelo no meio, os continentes e o mar em volta, e o KSC no litoral, com o mar a leste. A Mun é cinza com crateras, e Minmus, verde-claro. O script manda o que o desenho precisa nas linhas `SUB ANOM`, `RAIO`, `TOPO` e `CORPO` ([protocolo](protocolo.md#subida--ponte-da-tela)).

**A página SUBIDA aparece na mikromedia e no navegador** (o celular e o tablet do cockpit, em `bridge/celular/index.html`). O simulador aceita as linhas dela, mas mostra a navball. Depois de mudar o firmware, é preciso gravar o `mfd.hex` de novo, pelo Flash Magic ou pelo Pi ([docs/mikromedia.md](mikromedia.md#gravar-pelo-pi-sem-tirar-o-cabo)).

### O log do voo

Cada voo grava um CSV em `logs/subida-AAAAMMDD-HHMMSS.csv`, na raiz do repositório (no Pi, `~/cockpit/logs/`). A pasta fica fora do git. O script imprime o caminho na abertura (`Log do voo: ...`). `--log ARQUIVO` escolhe outro arquivo, e `--sem-log` não grava.

Uma linha a cada 0,1 s de jogo, gravada na hora: dá para acompanhar o voo no Pi com `tail -f` e trazer para o PC com `scp USUARIO@192.168.50.2:cockpit/logs/subida-*.csv .`. Os ângulos são em graus, e `t` em segundos de jogo desde a primeira linha.

| Colunas | O que são |
|---|---|
| `t`, `fase`, `alt_km`, `ap_km`, `pe_km`, `q_pa`, `massa_t`, `empuxo_kn` | A situação da nave; `empuxo_kn` é o disponível |
| `acel`, `pitch_pedido`, `rumo_pedido`, `desvio` | O que a guiagem pede |
| `pitch_nariz`, `rumo_nariz` | Para onde o nariz aponta de verdade |
| `pitch_vel`, `rumo_vel` | O movimento em relação ao ar, que a CURVA segue |
| `aoa`, `derrapagem` | O ângulo de ataque e o de derrapagem, do kRPC |
| `giro_pitch`, `giro_yaw`, `giro_roll` | A velocidade de giro da nave nos eixos dela, em graus/s: é aqui que aparece o balanço |
| `erro_pitch`, `erro_rumo` | Os erros do piloto automático do kRPC |
| `kp_pitch`, `ki_pitch`, `kp_roll`, `ki_roll` | Os ganhos que o piloto automático ajustou sozinho |

As colunas do giro, dos erros e dos ganhos só existem no jogo; no `--demo`, ficam vazias.

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

- **Sem alvo**, o plano é refeito a cada passo, da decolagem até o começo da circularização. É o plano que passa pela posição de agora com a inclinação pedida, com o ramo para o norte ou para o sul escolhido pela velocidade de agora. A rotação do planeta empurra a nave para fora do plano da decolagem; refazendo o plano, ela não precisa voltar a ele, e a inclinação final sai a menos de 0,1° da pedida. É o que o MechJeb faz, refazendo o rumo pela latitude de agora. Na circularização o plano fica parado: refeito perto da latitude máxima da órbita, ele mudava a cada passo, e a queima ficava empurrando para o lado sem nunca zerar a diferença (achado num voo simulado na Mun a 30°, que queimou o combustível todo assim).
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

Na curva de gravidade, o parâmetro do perfil é o **giro**: o quanto o nariz inclina no começo. Depois, o nariz segue o movimento, e a gravidade curva a trajetória, com o **desvio** replanejado em voo corrigindo o caminho ([abaixo](#a-curva-em-malha-fechada)).

No fim da decolagem, o script simula a subida inteira, em 2D, no plano da órbita. A simulação conta:

- a gravidade;
- o empuxo e o Isp de cada estágio, que mudam com a pressão;
- o arrasto, com a área medida na decolagem;
- a troca de estágios e o limite de pressão dinâmica;
- o corte no apoastro, a costa no ar e a circularização, como uma queima de verdade: a nave costeia até faltar metade da queima para o apoastro (contada pelos estágios que sobram) e queima mirando a velocidade circular na altitude pedida, como a guiagem. Uma circularização longa perde altura e gasta empuxo segurando, e a conta impulsiva (`√(μ/ra) − v_ap`) escondia isso: no primeiro voo no jogo, ela previa ~3 260 m/s para uma subida em pé que gastou 3 942.

Ela testa 16 giros na faixa (de 0,5° a 30° com ar; de 5° a 85° sem), em progressão geométrica, e refina o melhor por seção áurea. A progressão deixa as amostras mais juntas nos giros pequenos: com empuxo/peso perto de 1, só uma janela estreita chega em órbita (no foguete de 552 t, de ~0,8° a ~1,5°), e uma grade igual, de 2,7° em 2,7°, pulava a janela inteira. Leva menos de 0,5 s no Pi. Em Kerbin, com o foguete de teste, o giro escolhido é de uns 7,5° e o voo gasta uns 3 300 m/s até 80 km.

### A curva em malha fechada

Com empuxo/peso perto de 1, a curva passiva é sensível demais. O giro é escolhido com a nave virando na hora; no jogo, a nave de 552 t levou 14 s para virar 2,9°, e a curva começou com ~90 m/s em vez de ~55 m/s. A curva de gravidade dobra a trajetória no ritmo `g·cos γ / v`, então começar mais rápido deixa toda a subida mais em pé: o voo a 100 km cortou o motor a 44 km com o periastro em −573 km e gastou 3 868 m/s.

Por isso, na CURVA e no VACUO, a cada 5 s, o script simula de novo o resto da subida a partir do estado de agora e escolhe o desvio do nariz em relação ao movimento, de −4° a 4°, que gasta menos Δv. Positivo deita a subida; negativo deixa em pé. Os estágios são os lidos no giro, descontando a massa já gasta, para não reler as peças pelo kRPC. No Pi, cada replanejamento leva uns 0,2 s.

Numa nave simulada que vira a 1°/s (no lugar de 15°/s), o voo até 80 km gasta 3 313 m/s com o replanejamento e 3 477 sem.

Os estágios da simulação vêm do jogo: os motores e o combustível que cada separação larga. A conta vale bem para foguetes em série. Com boosters laterais ou asparagus, a previsão erra um pouco, e o resto do voo, que é em malha fechada, corrige.

### O corte e a circularização

- **O corte:** o apoastro sai da posição e da velocidade (vis-viva). Faltando menos de 5 km, o motor vai baixando; ele corta com o apoastro a 100 m do pedido. Na costa, ainda no ar, se o arrasto baixar o apoastro mais de 300 m, o motor acende a 10% até corrigir.
- **A circularização:** `Δv = √(μ/ra) − v_ap`, com a duração pela equação do foguete, passando pelos estágios que sobram. Ela começa metade da duração antes do apoastro, com o time warp parando 30 s antes. A queima é em malha fechada: a cada passo, mira a diferença entre a velocidade que se quer e a de agora. A velocidade que se quer tem a parte horizontal circular ali, no plano. A parte vertical sobe ou desce até a altitude pedida: o dobro da distância dividido pelo tempo que falta de queima, numa reta que chega a zero no fim. Com menos de 20 s de queima, ela vai a zero junto com o tempo, para a órbita terminar circular mesmo se a altitude não fechou. O motor só vai a toda com o nariz a menos de 5° dessa direção e vai baixando no fim, para terminar em uns 3 s. Termina com menos de 0,3 m/s de diferença.
- **Por que a altitude entra na circularização:** no voo do SmalLifter, a 100 km, o núcleo cortou com só 307 kg de combustível. A duração saiu com o empuxo dele, 12 s, e a queima começou 6 s antes do apoastro; quem queimou de verdade foi o estágio de cima, de 125 kN, por 85 s. A queima mirava a circular de onde a nave estivesse, e a órbita ficou em 96,7 × 96,4 km. Na nave simulada, com esse mesmo estado, a conta antiga dá 97,4 × 97,1 km. Só com a duração pelos estágios, a queima começa 28 s mais cedo, a nave zera a subida antes do apoastro e termina em 98,9 × 98,5. Com a altitude na queima, termina em 99,8 × 99,4, gastando o mesmo Δv.
- **A virada para a queima:** fora da direção, o motor nunca apaga. Um foguete grande, com rodas de reação fracas, só vira pelo gimbal, e o gimbal só funciona com empuxo. No primeiro voo no jogo, com o motor em 0% nessa hora, um foguete de 265 t ficou 42° fora da direção até o apoastro e caiu de volta. O acelerador máximo vai pelo erro do nariz: 100% até 5°, 10% de 45° para cima e, no meio, uma curva no logaritmo do erro. A 15° ele fica em 55%; a 10°, em 72%; a 30°, em 27%. Perto da direção ele sobe depressa, porque ali quase todo o empuxo já ajuda: a 10° de erro, perde 1,5%.
- **O RCS:** liga junto com o piloto automático, para ajudar a virar a nave quando o gimbal tem pouco empuxo. Na subida, gasta um pouco do monopropelente da nave. No fim, volta como estava antes do voo. Antes ele ficava ligado, e com o SAS que o script liga no fim, os propulsores soltavam pulsos o tempo todo para segurar a atitude. No voo do SmalLifter, em uns 18 min parado na órbita, o periastro foi de 96,46 para 96,50 km.
- **O rolamento e as aletas:** o piloto automático liga com o `target_roll` em NaN (sem alvo de rolamento: ele só segura a velocidade de rolamento em zero) e com as superfícies de controle (aletas) fora do controle, nos três eixos; no fim, o script devolve as aletas como estavam. O motivo: o KSP estima o torque das aletas com o sinal trocado (no foguete de 552 t, −7.418 kN·m no rolamento), e o piloto automático do kRPC ajusta os ganhos dividindo pelo torque disponível. Com os motores acesos, a soma passava por zero e ficava negativa: o ganho de rolamento ia a 45, trocava de sinal (−126) e o controle passava a empurrar o rolamento em vez de frear. Medido no jogo: a nave chegou a 250°/s. Sem as aletas, a estimativa fica certa (+1.312 kN·m), o ganho volta positivo, e o rolamento parou de −88°/s para 0 em 6 s. As aletas continuam estabilizando a nave, paradas; quem pilota é o gimbal, com as rodas e o RCS.
- **No terminal,** a linha de cada segundo mostra o `pitch` pedido, o `nariz` (o pitch de verdade, para ver se a nave acompanha a curva) e o `desvio` replanejado. A linha da fase GIRO traz o giro escolhido.

### O limite de pressão dinâmica

Acima de 30 kPa, o motor vai baixando, até 40% em 42 kPa, e fica em 40% acima disso. Protege a nave sem mudar muito o perfil.

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
- **O `--demo`** faz a mesma nave simulada subir de Kerbin, 4 vezes mais rápido que o tempo real, mandando as linhas `SUB` para a ponte da tela. Leva pouco mais de 1 min de relógio até a órbita. Com `--plano-do-alvo`, o alvo é um plano de mentira de 10°, com a janela a uns 20 min de jogo, pulados pelo time warp: leva 1,5 min, passa pelas fases `JANELA` e `PLANO`, e termina com 0,01° de erro de plano.
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
- **As versões do kRPC.** O Pi tem o cliente 0.6.0, e o jogo, o servidor 0.5.4. Quase tudo bate, menos o piloto automático: o cliente liga e desliga pela propriedade `engaged`, que o servidor 0.5.4 não tem. Quando o servidor recusa, o script chama direto os procedimentos dele, `AutoPilot_Engage` e `AutoPilot_Disengage`. Com o mod do kRPC atualizado, a propriedade passa a funcionar sozinha.
- **A carenagem e os painéis** ficam com o piloto, num action group.
- **O time warp:** abortar durante um `warp_to` corta o motor, mas o warp pode continuar no jogo até o fim.
- **A guiagem do vácuo** segue o pró-grado orbital. A guiagem dos ônibus espaciais (PEG), que é a forma ótima no vácuo, fica para depois.
- **O encoder de verdade** da configuração ainda não tem lugar no painel: por enquanto, é o da página de botões.
