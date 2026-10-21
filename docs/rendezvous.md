# Rendezvous automático

O [`scripts/rendezvous.py`](../scripts/rendezvous.py) leva a nave ativa, já em órbita, até 100 m (ou a distância pedida) de outra nave, parada em relação a ela. Os dois têm de orbitar o mesmo planeta, em órbita fechada e fora do ar. O script iguala o plano, acha a queima de transferência, corrige o caminho, anula a velocidade relativa e se aproxima. O acoplamento não faz parte dele.

**Status: script escrito e testado numa nave simulada; o plano foi conferido no jogo em 21/10/2026; falta o voo completo no jogo.** Os testes sem o KSP estão em [`scripts/tests/test_rendezvous.py`](../scripts/tests/test_rendezvous.py), e o roteiro para o jogo está [abaixo](#testar-no-jogo).

## Como usar

**Pela linha de comando**, como a subida:

```
python scripts/rendezvous.py                      # KSP neste computador, alvo do jogo
python scripts/rendezvous.py 192.168.50.1         # KSP noutro computador (do Pi, pelo cabo)
python scripts/rendezvous.py --so-planejar        # só cria o nó e imprime o plano
python scripts/rendezvous.py --distancia 200 --voltas-max 10
python scripts/rendezvous.py --demo               # sem o KSP: módulo e estação de mentira
```

- **O Python do PC não tem o `krpc`.** Tudo que fala com o jogo roda no Pi do cockpit, pelo cabo: `ssh admin@192.168.50.2`, `source ~/ksp/bin/activate` e `python ~/cockpit/scripts/rendezvous.py 192.168.50.1` (o PC é o `192.168.50.1`). No PC, só o `--demo` e os testes.
- **O alvo** é o que está escolhido no jogo: uma nave em órbita do mesmo planeta. O script segue o alvo que estava escolhido na largada, mesmo que o piloto troque de alvo depois.
- **`--so-planejar`** cria o nó da transferência no jogo, imprime o plano e espera o Enter para apagar o nó e sair. Não liga o piloto automático, não toca no motor nem no SAS. Serve para conferir o plano no mapa antes de entregar a nave.
- **`--distancia`** é a distância final ao alvo, em metros (padrão 100).
- **`--voltas-max`** limita o tempo de voo da transferência, em voltas da nave (padrão 6). Mais voltas dão uma transferência mais barata e mais demorada ([limites](#limites)).
- **`--demo`** não conecta no KSP: uma nave simulada, com os números de 20/10/2026 (o módulo de 10,3 t e a Estação um), faz o rendezvous 50 vezes mais rápido que o tempo real. Leva uns 13 s de relógio. Vale também com `--so-planejar`.
- **Os códigos de saída** são os da subida: 0 no encontro, 1 se não chegou (ou se recusou começar) e 130 se foi interrompido.
- **Ctrl+C** corta o motor, desliga o piloto automático, liga o SAS, apaga o nó que o script criou (os nós do piloto ficam) e devolve o RCS e as aletas como estavam.

**No começo**, o script imprime o plano: a queima de transferência (Δv e T−), o encontro (em quantas voltas e a que horas de jogo), a velocidade relativa no encontro e o Δv previsto contra o disponível. Com `--so-planejar`, imprime também a menor distância pela conta do script ao lado da que o kRPC prevê com o nó criado, e o ângulo entre o `burn_vector` do nó e o `dv1` do script (tem que ficar abaixo de 0,1°).

**Durante o voo**, uma linha por segundo: a fase, a distância ao alvo, a velocidade relativa, o T− e o Δv da próxima queima, o Δv gasto e o motor. Cada troca de fase imprime `--> FASE`.

## O que mudou da ideia original

O README previa um script que só criasse nós de manobra, para o piloto conferir e o EXEC da fase 5 queimar. **O EXEC ainda não existe, então o script queima sozinho**, como a subida. O nó que ele põe no jogo é só para mostrar: no mapa, o KSP desenha a aproximação, e o piloto confere o plano. A cada queima, o script apaga o nó anterior e cria o da próxima. Os nós que o piloto já tinha no jogo ficam, com um aviso.

Também mudou a transferência: a Hohmann com busca do momento da queima virava uma queima de 0 m/s quando a nave já está na altitude do alvo, que é o caso de hoje e o mais comum depois da subida. A busca nova ([abaixo](#a-busca-da-transferência)) cobre as duas situações.

## As fases

| Fase | O que acontece |
|---|---|
| `PLANO` | Só se a inclinação relativa passa de 0,05°. Espera o nó relativo com time warp e queima na direção normal, em malha fechada, como a fase `PLANO` da subida |
| `TRANSFERENCIA` | Planeja a transferência. Espera `t1 − duração/2`, com warp até a margem antes, apontando para a queima. Queima "como um nó do KSP" |
| `CORRECAO` | Refaz o tiro a partir do estado de agora, em frações de volta antes do encontro. Queima se a correção passa da tolerância; pula a fração cujo instante já passou |
| `VELOCIDADE` | Acha a menor distância a partir do estado de agora, espera a hora e anula a velocidade relativa |
| `APROXIMA` | Sem warp, em tempo real: vai para o alvo com uma velocidade que cai com a distância, até a distância final |
| `ENCONTRO` | Fim bom: motor em 0, piloto automático desligado, SAS ligado e código 0 |
| `FALHA` | Fim ruim, com um aviso; código 1 |

**No início:** sem alvo válido ou fora de órbita, é `FALHA`. Se o alvo já está a menos de 3 km, o script vai direto para `VELOCIDADE`: anular a velocidade relativa agora. Antes da primeira queima há sempre 120 s de espera, para a nave virar.

**Todas as queimas** seguem a regra da subida:

- o acelerador é o menor entre o da virada (100% até 5° de erro do nariz, 10% de 45° para cima) e o que faz a queima acabar em ~3 s, com piso mínimo;
- a queima acaba quando o Δv que falta (`|w|`) fica abaixo da tolerância, ou quando volta a crescer perto do fim;
- o nariz aponta para a queima desde 60 s antes (mais, se o nariz vira devagar).

**As travas de alinhamento:** nenhuma queima começa com o nariz a mais de 5° da direção dela, e o motor fica em 0 com o nariz a mais de 45°. Sem isso, um nariz lento queimava para o lado errado. Na subida o motor acende de leve para o gimbal virar a nave; aqui o nariz vira sozinho, pelas rodas de reação.

**Nas esperas**, o nariz fica no pró-grado até a margem antes da queima, e depois vira para ela. Parado em `APROXIMA`, o nariz fica apontado para o lado oposto ao alvo, pronto para frear.

## As contas

### A previsão das órbitas: Kepler com f e g

O script prevê as órbitas por conta própria, sem perguntar ao kRPC. Cada pergunta ao jogo vai pela rede, e a busca da transferência faz milhares delas. Sem motor, as órbitas seguem as leis de Kepler: a previsão é exata, sem o arrasto que complica o pouso.

A função `propagar(mu, r, v, dt)` resolve a equação de Kepler na anomalia excêntrica em diferença (ΔE):

```
n·dt = ΔE − (1 − r0/a)·sen ΔE + (σ0/√a)·(1 − cos ΔE),   σ0 = r0·v0/√μ
f = 1 − (a/r0)(1 − cos ΔE)        g = dt + √(a³/μ)(sen ΔE − ΔE_total)
r = f·r0 + g·v0                   v = ḟ·r0 + ġ·v0
```

O Newton em ΔE usa o `n·dt` reduzido a menos de 2π, e as voltas inteiras entram de volta no `g`. Aceita `dt` negativo (volta no tempo). Numa órbita de escape (`a ≤ 0`) levanta `ValueError`, e o tiro trata como candidato ruim. Erro de 0 m em uma volta.

### A menor distância

`menor_distancia(mu, nave, alvo, t_ini, t_fim)` amostra 32 pontos por volta da nave, pega o melhor e refina por seção áurea (30 iterações) entre as amostras vizinhas. Devolve a distância, o instante e a velocidade relativa.

### O tiro

`interceptar(...)` acerta uma queima `dv` em `t1` para a nave passar, em `tm`, na **mira**: 300 m acima do alvo, na direção radial dele. A mira nunca é o alvo: a nave passa ao lado, e a fase `VELOCIDADE` para ali.

É um Newton em 3D:

- o jacobiano é numérico, com passo de 0,01 m/s, e o sistema 3×3 sai por Cramer;
- o passo é limitado a 30 m/s (sem limite, o Newton salta para órbitas de escape);
- no máximo 25 iterações, até 0,5 m da mira;
- devolve `None` se não converge, se o determinante zera ou se cai em escape.

Em voltas inteiras (ou meias, no eixo normal) a matriz do Newton fica singular (as equações de Clohessy-Wiltshire): a queima não muda a posição de chegada naquela direção. Por isso o tempo de voo da busca e as correções evitam essas voltas.

### A busca da transferência

`planejar_transferencia` procura o instante da queima `t1` e o tempo de voo `tof`.

1. **`t1`:** vai de 120 s depois de agora até uma janela depois, com 4 amostras por volta da nave (no mínimo 24). A janela é o **período sinódico**, `1/|1/T_nave − 1/T_alvo|`: a posição relativa das duas naves se repete a cada período sinódico, e a janela de uma Hohmann volta nesse ritmo. Se o sinódico passa de 15 voltas da nave, esperar quase não muda a fase, e a janela vira uma volta. (Uma janela de só uma volta deixava de fora a janela boa de uma Hohmann de 80 km: 254 m/s achados, contra 121.)
2. **`tof`:** de meia volta da nave até `--voltas-max` voltas, em passos de 1/8 de volta, pulando os múltiplos inteiros do período da nave (a singularidade do tiro).
3. **O palpite** (`chute_tangencial`): a fase é o ângulo do alvo à frente da nave em `t1`. A nave precisa dar `tof/T_alvo + fase` voltas em `tof` (mais um inteiro, de −1 a 2). Daí sai o período da órbita de transferência, o semieixo e o Δv tangencial.
4. **O tiro** acerta a queima a partir do palpite.
5. **O custo** é `|Δv1| + |v_rel no encontro|`: o que se gasta para ir mais o que se gasta para parar. Fica o menor.
6. **As restrições:** o periastro da órbita de transferência fica 5 km acima da atmosfera (ou 10 km acima do chão, sem ar) e o apoastro dentro da esfera de influência.
7. **O refinamento:** o melhor par é refinado por seção áurea, alternando `t1` e `tof`, em duas passadas.

A busca leva ~2,5 s no PC e ~11 s no Pi 4 (medido em 21/10/2026 contra o jogo, de 100 km até a Estação um). O motor fica em 0 enquanto ela roda.

Com a nave quase na altitude do alvo, uma Hohmann dá 0 m/s: o que resolve a fase é uma transferência de várias voltas, com um período um pouco diferente do do alvo. É por isso que o tiro, e não a fórmula fechada, é a base.

### As correções

Depois da queima de transferência, o erro dela cresce com o tempo: um erro de 0,1 m/s custa ~0,1 m/s para corrigir agora e ~5 m/s a 0,3 volta do encontro. Por isso a fase `CORRECAO` refaz o tiro, a partir do estado de agora, em vários instantes:

- **a correção cedo:** logo depois da transferência, a 0,3 + k voltas do alvo antes do encontro (k inteiro, o maior que cabe). Queima a partir de 0,1 m/s;
- **as correções em 0,3 e 0,1 volta** antes do encontro: queimam a partir de 0,3 m/s;
- **a correção atrasada:** se o nariz ainda estava virando quando chegou a hora, o tiro é refeito a partir do estado de agora, antes de queimar;
- uma fração cujo instante já passou (transferências curtas) é pulada.

As frações de 0,3 e 0,1 volta, e não voltas inteiras, mantêm o tiro bem condicionado.

### `w_no`: queimar como um nó do KSP

As queimas planejadas (transferência e correções) não miram uma direção fixa: seguem o **Δv que ainda falta**, como o "remaining burn vector" do KSP. `w_no(mu, estado, t_no, v_depois)` é `v_depois − (velocidade que a nave teria em t_no, seguindo a órbita de agora)`, e `v_depois` é a velocidade planejada logo depois da queima. Vale antes, durante e depois de `t_no`: a malha fecha sozinha, e o que a queima fez de errado volta no vetor.

Uma queima longa começa metade da duração antes do nó, senão o encontro erra por quilômetros. A duração sai da equação do foguete.

### O nariz lento

A guiagem mede o giro de verdade do nariz enquanto ele está a mais de 20° da direção pedida. O warp para `max(60 s, 180°/giro + 10 s)` antes de cada queima, e a aproximação usa `max(60 s, 1,5·180°/giro)` de tempo. Com o giro de 5°/s, nada muda; com 1°/s, o voo do caso de hoje passou de 87 m/s gastos e 26 m do alvo para 38 m/s e 117 m. O `angular_velocity(nave.reference_frame)` do kRPC é sempre 0, então o giro vem da posição do nariz, não dele.

### A aproximação final

Sem warp. `v_des = limitar((d − D_FINAL)/tempo, 0, 5 m/s)`, na direção do alvo, com `tempo` de 60 s. Se `|v_des − v_rel|` passa de 0,3 m/s mais 10% de `v_des`, aponta e queima para corrigir; senão, motor em 0. Termina quando a distância fica abaixo da final mais 20 m e `|v_rel|` abaixo de 0,2 m/s. Passou de 1 200 s sem chegar, é `FALHA`.

O RCS de translação fica para o acoplamento: a aproximação usa o motor principal, com as mesmas queimas apontadas das outras fases.

### O Δv e o combustível

`dv_disponivel` é `isp·g0·ln(m/(m − combustível))`. O combustível é o que os motores acesos usam, nas peças que sairiam com eles, como na subida. Antes de começar, o script confere que o Δv previsto (plano + transferência + 20 m/s de reserva para as correções e a aproximação) cabe em 90% do disponível.

### O referencial

É o da subida: inercial, destro, com a origem no centro do planeta e o polo em (0, 1, 0). O kRPC entrega o canhoto, e a calibração do `z` é a da subida. Os vetores que voltam para o jogo (`target_direction` e os componentes do nó) passam pela mesma correção de sinal. Os componentes do nó são, com `p = unit(v)` e `n = unit(r × v)`: `prograde = dv·p`, `normal = dv·n` e `radial = dv·(p × n)`.

## Avisos

| Aviso | Quando | O que acontece |
|---|---|---|
| `ALVO` | Sem alvo, o alvo não é uma nave, orbita outro planeta, ou sumiu | Não começa, ou `FALHA` |
| `ORBITA` | A nave ou o alvo não está em órbita fechada fora do ar | Não começa |
| `TRANSFERENCIA` | Nenhum par (`t1`, `tof`) convergiu dentro das restrições | Não começa (tente `--voltas-max` maior) |
| `COMBUSTIVEL` | O Δv previsto passa de 90% do disponível, ou não há motor aceso (ou ele apagou) | Não começa, ou `FALHA` |

Sem troca de estágio: se o estágio aceso não tem Δv, o aviso é `COMBUSTIVEL`, e o piloto acende o próximo estágio à mão.

## Testar sem o KSP

```
py -3.14 -m unittest scripts.tests.test_rendezvous
py -3.14 scripts/rendezvous.py --demo
py -3.14 scripts/rendezvous.py --demo --so-planejar
```

- **Os testes** são 110 e levam uns 100 s. Cobrem:
  - as contas: Kepler contra a integração passo a passo, a energia e o momento angular, `dt` negativo, o tiro, o palpite, a busca da transferência (o caso de hoje, 100 e 200 km a menos de 5% de uma Hohmann, 80 km a menos de 10%, alvo à frente e atrás, sem ar) e o `w_no`;
  - os voos numa nave simulada (a `NaveOrbital`: um ponto de massa que gira o nariz a 5°/s, com a gravidade e o empuxo em subpassos de 0,05 s e o time warp por Kepler), até `ENCONTRO` ou `FALHA`;
  - o kRPC, com um jogo de mentira: a calibração do `z`, o alvo faltando ou em outro planeta, o nó criado com os componentes certos e removido no fim, o `liberar()` depois de Ctrl+C e o `--so-planejar` sem ligar o piloto automático.
- **O `--demo`** faz o caso de hoje: o módulo, 45° à frente da Estação um, 586 km de distância. Termina em `ENCONTRO` a uns 90 m do alvo, com ~41 m/s gastos.

**Os voos simulados** (Δv gasto / distância final):

| Voo | Δv gasto | Distância final |
|---|---|---|
| O caso de hoje (alvo 45° atrás) | 41 m/s | 89 m |
| Alvo à frente | 40 m/s | 102 m |
| Nave a 100 km, alvo a 158 km | 98 m/s | 103 m |
| Nariz virando a 1°/s | 38 m/s | 117 m |
| Empuxo ou Isp 3% diferentes do que a guiagem acha | ~41 m/s | ~90 m |

Os testes de voo conferem também que o periastro da nave nunca cai abaixo do ar mais 5 km, e que a distância nunca fica abaixo da final menos 50 m (a nave não bate no alvo).

## Testar no jogo

O primeiro caso real: o módulo `AEAS - SmalLifter` (10,3 t, um Cheetah de 125 kN e Isp 355 s, com uns 1 100 m/s de sobra) e a `Estação um`, em Kerbin.

1. **`--so-planejar`**, com a Estação um como alvo. **Feito em 21/10/2026.** O SmalLifter estava a 99,7 × 99,4 km, e a Estação um a 167,8 × 148,7 km, com 0,25° de plano. O script planejou:
   - o plano: 10,0 m/s;
   - a transferência: 49,6 m/s, com 39,8 m/s de velocidade relativa no encontro;
   - 99,5 m/s ao todo (uma Hohmann de 100 a 158 km custa ~88 m/s).

   Conferir no mapa: o nó, a aproximação que o KSP desenha (tem que ficar a ~300 m, perto da nossa) e o `burn_vector` do nó contra o `dv1`. O script apaga o nó sozinho.
2. **Voo completo no jogo: a fazer.** Tem que terminar a ~100 m, parado. Anotar o Δv gasto contra o previsto, e o monopropelente gasto.
3. **Depois:** uma nave a 80 km, para testar a transferência tipo Hohmann até a estação.

Se algo der errado, anote a fase, o que o terminal imprimiu e a nave. O primeiro ponto a conferir é a primeira mensagem do script: se o referencial do kRPC não for o que o script espera, ele para antes de qualquer queima, com uma mensagem sobre o referencial.

## Limites

- **Nave quase na altitude do alvo, com o alvo longe na fase** (por exemplo, de 140 a 170 km até 158 km, com o alvo de 90° a 180° à frente ou atrás): o período sinódico passa de 15 voltas, e a fase é corrigida dentro de `--voltas-max` voltas de transferência, a **60–170 m/s**, contra 12–26 m/s de uma Hohmann depois de dezenas de voltas de espera. Um `--voltas-max` maior barateia: o custo cai com 1/voltas.
- **Sem troca de estágio.** O script confere antes se o Δv do estágio aceso basta; se não basta, não começa.
- **Só o motor principal.** O RCS de translação e o acoplamento ficam para depois.
- **A busca é lenta no Pi:** ~2,5 s no PC e ~11 s no Pi 4 (medido em 21/10/2026 contra o jogo, de 100 km até a Estação um). O motor fica em 0 enquanto ela roda, o que não atrapalha: a busca roda antes da queima, com a nave em queda livre. Se passar muito disso, o próximo passo é guardar o estado do alvo numa grade de tempo.
- **O nariz lento:** a guiagem mede o giro e começa a virar mais cedo; testado a 1°/s. Uma nave que vira bem mais devagar que isso precisa de margens maiores.
- **As versões do kRPC.** O Pi tem o cliente 0.6.0, e o jogo, o servidor 0.5.4. O `auto_pilot.engaged` não existe no servidor: o script usa o contorno da subida (`ligar_piloto`). No cliente 0.6.0, o `relative_inclination` recebe o `Orbit` do alvo, não a nave.
- **Órbitas elípticas** servem, porque a busca é numérica; o protótipo usou a estação real, com e = 0,0126.
- **A página na tela multifunção e o korry** do painel de scripts ficam para depois, assim como a menor distância na página do editor de manobras.
