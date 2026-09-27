"""Pouso autônomo: queima de suicídio numa descida vertical, em qualquer planeta.

A nave cai com o motor desligado, acende o mais tarde possível e freia até
tocar o chão devagar. Nos planetas com atmosfera, o arrasto do ar também freia;
o script mede esse arrasto em voo e acende mais tarde por causa dele. Sem
atmosfera (Mun, Minmus...), o arrasto é zero e sobram só gravidade e motor.

A cada volta do laço (20 vezes por segundo):
 1. Lê do jogo a altura do pé da nave, a velocidade, a massa, o empuxo e o
    arrasto.
 2. Estima a "área de arrasto" da nave: arrasto medido / (densidade · v²).
 3. Procura, por bisseção, a aceleração fixa do motor que leva a descida a
    V_TOQUE a ALTURA_FOLGA do chão. Para testar cada valor, simula a freada
    daqui até o fim, com gravidade, motor e arrasto (que muda com a velocidade
    e com a densidade do ar, maior perto do chão).
 4. Enquanto essa aceleração for menor que IGNICAO do máximo, cai sem motor.
    Quando chega nela, acende e passa a usar a aceleração calculada, refeita a
    cada volta: os erros da previsão se corrigem sozinhos no caminho.
 5. Perto do chão, segura a descida em V_TOQUE até a nave pousar.

Quem aponta a nave é o SAS do próprio KSP: retrógrado enquanto a nave desce
rápido, e segurando a atitude no fim, quando a velocidade fica pequena e o
retrógrado começa a pular de um lado para o outro.

No cockpit, quem abre o script é a ponte da tela (bridge/mfd.py), quando o
korry POUSO fica apertado 5 s; segurar de novo 5 s aborta. O script manda o
estado dele para a ponte por UDP (as linhas POU de docs/protocolo.md), e a
ponte mostra na página POUSO da tela multifunção. Sem a ponte aberta, os
pacotes se perdem e o script pousa do mesmo jeito.

Uso:
    python scripts/pouso.py                  # KSP neste computador
    python scripts/pouso.py 192.168.1.10     # KSP em outro computador (ex.: a partir do Pi)
    python scripts/pouso.py --tela 192.168.1.20   # ponte da tela em outro computador
    python scripts/pouso.py --demo           # sem o KSP: uma nave simulada cai em Kerbin

Rode com o motor já ativado (no estágio) e a nave caindo ou subindo num salto.
O script desce na vertical, onde estiver: não escolhe o lugar do pouso.
A nave precisa de SAS com o modo retrógrado (piloto ou sonda de nível 1).
Ctrl+C corta o motor e devolve o controle ao piloto.

Sai com o código 0 se a nave pousou, 1 se não pousou (erro, nave perdida) e
130 se foi interrompido (Ctrl+C, ou o korry segurado de novo): a ponte usa o
código para acender o korry.
"""

import argparse
import math
import os
import signal
import socket
import sys
import time
from dataclasses import dataclass

IGNICAO = 0.85          # acende quando a freada precisa de 85% do empuxo: sobram 15% para corrigir
FATOR_ARRASTO = 0.7     # a previsão só conta com 70% do arrasto medido (ver Guiagem._medir_arrasto)
V_TOQUE = 2.0           # m/s: velocidade de descida no toque
ALTURA_FOLGA = 2.0      # m: a freada mira terminar aqui; o resto desce em V_TOQUE
ALTURA_TOQUE = 10.0     # m: abaixo disso, com a descida já lenta, não desliga mais o motor
GANHO_TOQUE = 2.0       # 1/s: quanto o motor corrige a velocidade na descida final
V_RETROGRADO = 10.0     # m/s: descendo mais devagar que isso, o SAS para de seguir o retrógrado
CIMA_MIN = 0.5          # nariz a mais de 60° da vertical: motor desligado até a nave virar
Q_MIN = 20.0            # Pa: com menos pressão dinâmica que isso, o arrasto medido é só ruído
SUAVIZACAO = 0.2        # peso de cada medida nova na média da área de arrasto
PASSOS_PREVISAO = 50    # passos da simulação da freada
ITERACOES = 14          # passos da bisseção: precisão de 1/16000 do empuxo
AMOSTRAS_ATMOSFERA = 100  # pontos da tabela de densidade do ar
INTERVALO = 0.05        # s: 20 voltas por segundo
INTERVALO_LENTO = 1.0   # s: altura do pé e empuxo no chão, que mudam devagar
INTERVALO_STATUS = 1.0  # s: uma linha de situação no terminal
INTERVALO_STATUS_PERTO = 0.25  # s: idem, nos últimos ALTURA_PERTO metros
ALTURA_PERTO = 100.0    # m
PASCAL_POR_ATM = 101_325
PORTA_TELA = 50100      # UDP: a ponte da tela (bridge/mfd.py) escuta aqui
INTERVALO_TELA = 0.1    # s: o estado vai para a ponte 10 vezes por segundo
FREADA_MAX = 999        # % do empuxo: "nem o motor todo dá" vai como 999

POUSOU, NAO_POUSOU, INTERROMPIDO = 0, 1, 130   # códigos de saída

QUEDA = "QUEDA"         # motor desligado, esperando a hora de acender
QUEIMA = "QUEIMA"       # freando
TOQUE = "TOQUE"         # descida final, em V_TOQUE
POUSADA = "POUSADA"

RETROGRADO = "retrógrado"          # modos do SAS pedidos pela guiagem
ATITUDE = "segurar a atitude"


@dataclass
class Leitura:
    altura: float        # m: do ponto mais baixo da nave até o chão (ou o mar, se estiver mais perto)
    altitude: float      # m: do centro de massa até o nível do mar
    velocidade: tuple    # m/s: (cima, norte, leste), em relação ao chão
    massa: float         # kg
    empuxo: float        # N: empuxo dos motores ativos com o acelerador em 100%, agora
    empuxo_chao: float   # N: o mesmo com a pressão do ar no chão (ar mais grosso tira empuxo)
    arrasto: float       # N
    cima: float          # quanto o nariz aponta para cima: 1 = na vertical, 0 = deitado
    g: float             # m/s²: gravidade no chão
    pousada: bool


class Guiagem:
    """Decide o acelerador e a direção a cada leitura.

    Não conhece o kRPC: recebe uma Leitura e devolve o acelerador e o modo
    do SAS. Assim os testes (tests/test_pouso.py) usam esta mesma guiagem com uma
    nave simulada.
    """

    def __init__(self, densidade):
        self._densidade = densidade  # função: altitude sobre o mar (m) → densidade do ar (kg/m³)
        self.fase = QUEDA
        self.area = 0.0              # m²: arrasto / (densidade · v²), medida em voo
        self.necessaria = 0.0        # m/s²: aceleração do motor que a freada precisa agora
        self._freou = False          # a freada já trouxe a descida abaixo de V_RETROGRADO

    def passo(self, l):
        """Devolve (acelerador de 0 a 1, modo do SAS: RETROGRADO ou ATITUDE)."""
        self._medir_arrasto(l)
        vc = l.velocidade[0]
        self.necessaria = self._aceleracao_necessaria(l)
        maxima_chao = l.empuxo_chao / l.massa

        if l.pousada:
            self.fase = POUSADA
        elif self.fase == TOQUE:
            pass  # perto do chão não volta atrás
        elif vc >= -V_TOQUE:
            # Já lenta (ou subindo): perto do chão, desce devagar; longe dele,
            # cai sem motor de novo e acende outra vez quando precisar.
            self.fase = TOQUE if l.altura <= ALTURA_TOQUE else QUEDA
        elif self.fase == QUEIMA or 0 < IGNICAO * maxima_chao <= self.necessaria:
            self.fase = QUEIMA  # sem motor ativo (maxima_chao = 0) não adianta acender
        else:
            self.fase = QUEDA

        if self.fase == QUEIMA:
            aceleracao = self.necessaria
        elif self.fase == TOQUE:
            # Segura a gravidade e corrige a diferença para -V_TOQUE. A essa
            # velocidade o arrasto não conta.
            aceleracao = l.g + GANHO_TOQUE * (-V_TOQUE - vc)
        else:
            aceleracao = 0.0
        return self._acelerador(aceleracao, l), self._modo(l)

    def _modo(self, l):
        """Para onde o SAS aponta a nave.

        Descendo rápido, retrógrado: o motor freia contra o movimento e a
        deriva para os lados some junto. Devagar, o retrógrado fica instável:
        a 2 m/s de descida, meio metro por segundo de deriva já inclina a mira
        14°, e o SAS, correndo atrás dela com o motor ligado, cria mais deriva
        e começa a balançar a nave. Aí o SAS só segura a atitude que a nave
        tem, quase em pé depois da freada retrógrada.

        Antes da freada (ex.: no alto de um salto, quase parada) também segura
        a atitude. Depois que a freada deixa a nave devagar, não volta mais ao
        retrógrado.
        """
        descendo_rapido = -l.velocidade[0] >= V_RETROGRADO
        if self.fase in (QUEIMA, TOQUE) and not descendo_rapido:
            self._freou = True
        return RETROGRADO if descendo_rapido and not self._freou else ATITUDE

    def _acelerador(self, aceleracao, l):
        """Converte a aceleração vertical desejada em posição do acelerador.

        Com o nariz inclinado, só parte do empuxo vai para cima: divide por
        l.cima para compensar.
        """
        if aceleracao <= 0 or l.empuxo <= 0 or l.cima < CIMA_MIN:
            return 0.0
        return min(1.0, aceleracao * l.massa / (l.empuxo * l.cima))

    def _medir_arrasto(self, l):
        """Atualiza a área de arrasto a partir do arrasto que o jogo mediu.

        No KSP, arrasto = área · densidade · v² (a área já inclui o
        coeficiente de arrasto e o 1/2). Guardar a área em vez do arrasto
        permite prever o arrasto em outra altitude e outra velocidade.

        A área de verdade muda com a velocidade do som: perto de Mach 1 ela
        passa do dobro da área em baixa velocidade. Medida ainda rápida, ela
        faria a previsão contar com mais arrasto do que vai haver no fim da
        freada, e a ignição sairia tarde demais. Por isso a previsão só usa
        FATOR_ARRASTO dela.
        """
        v2 = sum(c * c for c in l.velocidade)
        densidade = self._densidade(l.altitude)
        if densidade * v2 / 2 < Q_MIN:
            return  # ar ralo demais para medir: fica a última estimativa
        medida = l.arrasto / (densidade * v2)
        if self.area == 0.0:
            self.area = medida
        else:
            self.area += SUAVIZACAO * (medida - self.area)

    def _aceleracao_necessaria(self, l):
        """Aceleração do motor que, fixa daqui até o fim, termina a freada na hora certa.

        "Na hora certa" = a descida chega a V_TOQUE a ALTURA_FOLGA do chão.
        Devolve 0 se o ar sozinho dá conta, e infinito se nem o motor todo dá.
        Bisseção: se a nave para acima do alvo, dá para frear menos; se bate no
        chão antes, precisa frear mais.
        """
        if l.velocidade[0] >= -V_TOQUE:
            return 0.0
        maxima = max(l.empuxo, l.empuxo_chao) / l.massa

        def sobra(aceleracao):
            return self._prever(l, aceleracao) - ALTURA_FOLGA

        if sobra(0.0) >= 0:
            return 0.0
        if sobra(maxima) < 0:
            return math.inf
        baixo, alto = 0.0, maxima
        for _ in range(ITERACOES):
            meio = (baixo + alto) / 2
            if sobra(meio) >= 0:
                alto = meio
            else:
                baixo = meio
        return alto  # o lado que ainda para a tempo

    def _prever(self, l, aceleracao):
        """Simula a freada com o motor fixo em `aceleracao` (m/s², para cima).

        Devolve a altura em que a descida chega a V_TOQUE; negativa se a nave
        bater no chão antes. Anda em passos iguais de velocidade, não de tempo:
        são sempre PASSOS_PREVISAO passos, esteja a nave a 50 m ou a 50 km.

        Fica do lado seguro: usa a gravidade do chão (a mais forte do caminho),
        a massa de agora (o combustível gasto deixaria a nave mais leve) e
        FATOR_ARRASTO do arrasto.
        """
        altura = l.altura
        v = l.velocidade[0]
        base = l.altitude - l.altura  # altitude do centro de massa com o pé no chão
        dv = (-V_TOQUE - v) / PASSOS_PREVISAO  # positivo: a descida vai diminuindo
        for _ in range(PASSOS_PREVISAO):
            v_meio = v + dv / 2
            arrasto = FATOR_ARRASTO * self.area * self._densidade(base + altura) * v_meio**2 / l.massa
            freada = aceleracao + arrasto - l.g
            if freada <= 0:
                return -1.0  # nessa condição a nave nem desacelera
            dt = dv / freada
            altura += v_meio * dt
            if altura < 0:
                return altura
            v += dv
        return altura


def ler_atmosfera(corpo):
    """Tabela da densidade do ar por altitude, lida do jogo uma vez só.

    Consultar o jogo a cada passo da previsão seria lento demais (são
    milhares de consultas por segundo); a tabela é interpolada aqui mesmo.
    """
    if not corpo.has_atmosphere:
        return lambda altitude: 0.0
    topo = corpo.atmosphere_depth
    passo = topo / AMOSTRAS_ATMOSFERA
    tabela = [corpo.density_at(i * passo) for i in range(AMOSTRAS_ATMOSFERA + 1)]

    def densidade(altitude):
        if altitude >= topo:
            return 0.0
        x = max(altitude, 0.0) / passo
        i = min(int(x), AMOSTRAS_ATMOSFERA - 1)
        return tabela[i] + (tabela[i + 1] - tabela[i]) * (x - i)

    return densidade


class NaveKrpc:
    """Lê a nave pelo kRPC, com streams, e monta a Leitura para a guiagem."""

    def __init__(self, conn, nave):
        space_center = conn.space_center
        self._nave = nave
        self.corpo = corpo = nave.orbit.body
        self._gm = corpo.gravitational_parameter
        self._raio = corpo.equatorial_radius
        self._atmosfera = corpo.has_atmosphere
        situacao = space_center.VesselSituation
        self._pousada = (situacao.landed, situacao.splashed)

        # Referencial "híbrido": velocidade em relação ao chão, que gira com o
        # planeta, escrita nos eixos do horizonte local (x = cima, y = norte,
        # z = leste). A direção do nariz vem nos mesmos eixos.
        self.referencial = space_center.ReferenceFrame.create_hybrid(
            position=corpo.reference_frame, rotation=nave.surface_reference_frame
        )
        voo = nave.flight(self.referencial)
        stream = conn.add_stream
        self._streams = {
            "radar": stream(getattr, voo, "surface_altitude"),
            "altitude": stream(getattr, voo, "mean_altitude"),
            "velocidade": stream(getattr, voo, "velocity"),
            "arrasto": stream(getattr, voo, "drag"),
            "massa": stream(getattr, nave, "mass"),
            "empuxo": stream(getattr, nave, "available_thrust"),
            "direcao": stream(nave.direction, self.referencial),
            "situacao": stream(getattr, nave, "situation"),
            "trem": stream(getattr, nave.control, "gear"),
        }
        self.pernas = [perna.part for perna in nave.parts.legs]
        self._proxima_lenta = 0.0
        self._trem_medido = None  # posição do trem na última medida do pé
        self._fundo = 0.0       # m: do centro de massa até o pé da nave (negativo)
        self._fator_chao = 1.0  # empuxo com a pressão do chão / empuxo agora

    def _atualizar_lento(self, terreno, trem):
        """O que muda devagar, relido uma vez por segundo e quando o trem muda.

        A altitude do jogo é medida do centro de massa, não do pé. O pé vem
        da caixa que envolve as peças, nos eixos do horizonte (x = cima).

        Com o trem baixado, o pé é a ponta da perna mais baixa, e só as pernas
        entram na conta. Nas versões lançadas do kRPC (até a 0.6.0), a caixa
        de uma peça junta tudo o que está pendurado nela, como o efeito da
        chama do motor ligado. Aí a caixa da nave inteira desce metros abaixo
        do pé de verdade, e a freada termina alta demais. Com o trem
        recolhido (ou sem trem), fica a caixa da nave inteira: se ela errar,
        erra para baixo, e a ignição só sai um pouco mais cedo.

        O empuxo cai quando o ar engrossa (depende do motor: os de vácuo
        perdem muito). A previsão usa o empuxo com a pressão do chão, o menor
        do caminho.
        """
        referencial = self._nave.surface_reference_frame
        if trem and self.pernas:
            self._fundo = min(peca.bounding_box(referencial)[0][0] for peca in self.pernas)
        else:
            self._fundo = self._nave.bounding_box(referencial)[0][0]
        self._trem_medido = trem
        agora = self._nave.available_thrust
        if agora > 0:
            pressao = self.corpo.pressure_at(max(terreno, 0.0)) if self._atmosfera else 0.0
            self._fator_chao = self._nave.available_thrust_at(pressao / PASCAL_POR_ATM) / agora

    def ler(self):
        s = {nome: stream() for nome, stream in self._streams.items()}
        terreno = s["altitude"] - s["radar"]  # altitude do chão (ou do mar) abaixo da nave
        agora = time.monotonic()
        if agora >= self._proxima_lenta or s["trem"] != self._trem_medido:
            self._atualizar_lento(terreno, s["trem"])
            self._proxima_lenta = agora + INTERVALO_LENTO
        return Leitura(
            altura=s["radar"] + self._fundo,
            altitude=s["altitude"],
            velocidade=s["velocidade"],
            massa=s["massa"],
            empuxo=s["empuxo"],
            empuxo_chao=s["empuxo"] * self._fator_chao,
            arrasto=math.hypot(*s["arrasto"]),
            cima=s["direcao"][0],
            g=self._gm / (self._raio + terreno) ** 2,
            pousada=s["situacao"] in self._pousada,
        )

    def remover(self):
        for stream in self._streams.values():
            stream.remove()


class Avisos:
    """Imprime cada aviso uma vez só, e de novo depois que ele deixar de valer."""

    def __init__(self):
        self.ativos = set()

    def conferir(self, chave, vale, texto):
        if vale and chave not in self.ativos:
            print(f"AVISO: {texto}")
            self.ativos.add(chave)
        elif not vale:
            self.ativos.discard(chave)


class Sas:
    """O SAS do KSP, que aponta a nave. Só troca o modo quando a guiagem pede outro."""

    def __init__(self, conn, controle):
        space_center = conn.space_center
        self._controle = controle
        self._modos = {
            RETROGRADO: space_center.SASMode.retrograde,
            ATITUDE: space_center.SASMode.stability_assist,
        }
        self._faltando = set()  # modos que o SAS desta nave não tem
        self.modo = None
        controle.sas = True
        controle.speed_mode = space_center.SpeedMode.surface  # retrógrado em relação ao chão

    def pedir(self, modo):
        """Troca o modo do SAS. Se a nave não tiver o modo, fica segurando a atitude."""
        if modo in self._faltando:
            modo = ATITUDE
        if modo == self.modo:
            return
        try:
            self._controle.sas_mode = self._modos[modo]
        except RuntimeError:
            # O kRPC recusa um modo que a nave não tem. Segurar a atitude
            # existe em todo SAS.
            self._faltando.add(modo)
            print(f"AVISO: o SAS desta nave não tem o modo {modo} (precisa de piloto "
                  "ou sonda de nível 1); a nave fica segurando a atitude.")
            self._controle.sas_mode = self._modos[ATITUDE]
            modo = ATITUDE
        self.modo = modo
        print(f"SAS: {modo}")


def inclinacao(l):
    """Graus entre o nariz e a vertical."""
    return math.degrees(math.acos(min(max(l.cima, -1.0), 1.0)))


def status(l, guiagem, acelerador):
    maxima = l.empuxo_chao / l.massa
    if maxima <= 0 or math.isinf(guiagem.necessaria):
        precisa = "  ---"
    else:
        precisa = f"{guiagem.necessaria / maxima * 100:4.0f}%"
    if guiagem.fase == QUEDA:
        precisa += f" (acende em {IGNICAO:.0%})"
    arrasto = f"  area de arrasto {guiagem.area:5.2f} m2" if guiagem.area else ""
    return (
        f"{guiagem.fase:7} altura {l.altura:8.1f} m  descida {-l.velocidade[0]:6.1f} m/s  "
        f"inclinacao {inclinacao(l):2.0f} graus  motor {acelerador * 100:3.0f}%  "
        f"freada precisa {precisa}{arrasto}"
    )


def linhas_de_estado(l, guiagem, acelerador, modo_sas, aviso):
    """O estado do pouso nas linhas POU do protocolo da tela (docs/protocolo.md).

    Altura em décimos de metro, descida em décimos de m/s (negativa
    descendo, como o VV), empuxo/peso em centésimos e a freada em % do
    empuxo máximo no chão.
    """
    maxima = l.empuxo_chao / l.massa if l.massa > 0 else 0.0
    if maxima <= 0:
        freada = "OFF"
    elif math.isinf(guiagem.necessaria):
        freada = str(FREADA_MAX)
    else:
        freada = str(min(FREADA_MAX, round(guiagem.necessaria / maxima * 100)))
    twr = l.empuxo_chao / (l.massa * l.g) if l.massa > 0 and l.g > 0 else 0.0
    return [
        f"POU FASE {guiagem.fase}",
        f"POU ALT {round(max(-9e7, min(9e7, l.altura * 10)))}",
        f"POU VV {round(max(-9e7, min(9e7, l.velocidade[0] * 10)))}",
        f"POU MOTOR {round(100 * max(0.0, min(1.0, acelerador)))}",
        f"POU TWR {min(9999, round(twr * 100))}",
        f"POU FREADA {freada}",
        f"POU IGN {round(IGNICAO * 100)}",
        f"POU SAS {'RETRO' if modo_sas == RETROGRADO else 'ESTAB'}",
        f"POU INCL {round(inclinacao(l))}",
        f"POU AVISO {aviso or 'OFF'}",
    ]


class TelaPouso:
    """Manda o estado do pouso para a ponte da tela, por UDP, 10 vezes por segundo.

    Um pacote só, com uma linha POU por vez. Sem a ponte aberta, o pacote se
    perde e nada acontece: a tela é opcional.
    """

    def __init__(self, endereco):
        """endereco: IP da ponte, ou IP:PORTA (a porta padrão é PORTA_TELA)."""
        ip, _, porta = endereco.partition(":")
        self._destino = (ip, int(porta) if porta else PORTA_TELA)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._proximo = 0.0

    def enviar(self, linhas, agora=True):
        """agora=False: só manda se já passou INTERVALO_TELA desde o último pacote."""
        instante = time.monotonic()
        if not agora and instante < self._proximo:
            return
        self._proximo = instante + INTERVALO_TELA
        try:
            self._socket.sendto("\n".join(linhas).encode("ascii"), self._destino)
        except OSError:
            pass

    def fechar(self):
        self._socket.close()


def aviso_principal(avisos):
    """O aviso mais importante que vale agora, para a tela (ou None)."""
    for chave, nome in (("empuxo", "EMPUXO"), ("motor", "MOTOR"), ("nariz", "NARIZ")):
        if chave in avisos.ativos:
            return nome
    return None


def pousar(conn, nave, tela=None):
    """Pousa a nave. Devolve True se ela pousou."""
    corpo = nave.orbit.body
    # has_solid_surface só existe nas versões novas do kRPC.
    if not getattr(corpo, "has_solid_surface", True):
        print(f"{corpo.name} não tem chão para pousar.")
        return False
    if corpo.has_atmosphere:
        print(f"Lendo a atmosfera de {corpo.name}...")
    guiagem = Guiagem(ler_atmosfera(corpo))
    fonte = NaveKrpc(conn, nave)
    controle = nave.control
    try:
        l = fonte.ler()
        if l.pousada:
            print("A nave já está pousada.")
            return False

        twr = l.empuxo_chao / (l.massa * l.g)
        print(f"Nave: {nave.name} ({corpo.name})  empuxo/peso no chão: {twr:.2f}")
        horizontal = math.hypot(l.velocidade[1], l.velocidade[2])
        if horizontal > 50:
            print(f"AVISO: {horizontal:.0f} m/s de velocidade horizontal; o script supõe descida vertical.")
        if 0 < twr < 1:
            print("AVISO: o motor não segura o peso da nave no chão; não vai dar para pousar.")
        if not fonte.pernas:
            print("AVISO: a nave não tem trem de pouso; o pé vem da caixa da nave inteira, "
                  "que no kRPC pode ficar metros abaixo do real (a freada termina alta).")

        controle.throttle = 0.0
        sas = Sas(conn, controle)

        avisos = Avisos()
        fase = None
        proximo_status = 0.0
        descida = 0.0
        while True:
            l = fonte.ler()
            acelerador, modo = guiagem.passo(l)
            if guiagem.fase == POUSADA:
                # A altura estimada no toque mostra o erro da medida do pé: o
                # certo é perto de zero.
                print(f"Pousou! Descia a {descida:.1f} m/s, com o nariz a "
                      f"{inclinacao(l):.0f}° da vertical. No toque, o script achava "
                      f"que o pé estava a {l.altura:.1f} m do chão.")
                if tela is not None:
                    tela.enviar(linhas_de_estado(l, guiagem, 0.0, sas.modo, None))
                return True
            controle.throttle = acelerador
            sas.pedir(modo)
            descida = -l.velocidade[0]

            if guiagem.fase != fase:
                fase = guiagem.fase
                print(f"--> {fase} a {l.altura:.0f} m do chão")
                if fase in (QUEIMA, TOQUE):
                    controle.gear = True
            ligado = fase in (QUEIMA, TOQUE)
            avisos.conferir("motor", l.empuxo <= 0, "nenhum motor ativo: ative o estágio do motor.")
            avisos.conferir(
                "empuxo", fase == QUEIMA and math.isinf(guiagem.necessaria),
                "empuxo insuficiente, não dá mais para parar a tempo!",
            )
            avisos.conferir(
                "nariz", ligado and l.cima < CIMA_MIN,
                "nariz longe da vertical: motor desligado até a nave virar.",
            )
            if tela is not None:
                tela.enviar(linhas_de_estado(l, guiagem, acelerador, sas.modo, aviso_principal(avisos)), agora=False)

            agora = time.monotonic()
            if agora >= proximo_status:
                print(status(l, guiagem, acelerador))
                perto = l.altura < ALTURA_PERTO
                proximo_status = agora + (INTERVALO_STATUS_PERTO if perto else INTERVALO_STATUS)
            time.sleep(INTERVALO)
    finally:
        try:
            controle.throttle = 0.0
            controle.sas = True
            controle.sas_mode = conn.space_center.SASMode.stability_assist
            fonte.remover()
        except (ValueError, RuntimeError):
            pass  # a nave pode não existir mais


class NaveDemo:
    """Uma nave de mentira caindo na vertical em Kerbin, para testar sem o KSP (--demo).

    Gravidade, empuxo, arrasto e gasto de combustível simples, em tempo real.
    Os testes (tests/test_pouso.py) usam uma nave simulada mais malvada.
    """

    G = 9.81                # m/s²
    G0 = 9.80665            # m/s²: a do Isp
    DENSIDADE_MAR = 1.225   # kg/m³
    ESCALA = 5_600          # m: a densidade cai para 1/e
    TOPO = 70_000           # m: fim da atmosfera
    AREA = 1.2              # m²: arrasto = área · densidade · v²
    ISP = 300.0             # s
    ALTURA_CM = 3.0         # m: do pé ao centro de massa
    PASSO = 0.02            # s: a física anda em passos pequenos

    def __init__(self, altura=4_000.0, velocidade=-200.0, massa=8_000.0, twr=2.2):
        self.altura = altura
        self.v = velocidade
        self.massa = massa
        self.empuxo_max = twr * massa * self.G
        self.toque = None   # m/s de descida no toque

    def densidade(self, altitude):
        if altitude >= self.TOPO:
            return 0.0
        return self.DENSIDADE_MAR * math.exp(-max(altitude, 0.0) / self.ESCALA)

    def _arrasto(self):
        return self.AREA * self.densidade(self.altura + self.ALTURA_CM) * self.v**2

    def leitura(self):
        return Leitura(
            altura=self.altura,
            altitude=self.altura + self.ALTURA_CM,
            velocidade=(self.v, 0.0, 0.0),
            massa=self.massa,
            empuxo=self.empuxo_max,
            empuxo_chao=self.empuxo_max,
            arrasto=self._arrasto(),
            cima=1.0,
            g=self.G,
            pousada=self.toque is not None,
        )

    def avancar(self, acelerador, dt):
        while dt > 0 and self.toque is None:
            passo = min(dt, self.PASSO)
            dt -= passo
            empuxo = acelerador * self.empuxo_max
            arrasto = -math.copysign(self._arrasto(), self.v)
            self.v += ((empuxo + arrasto) / self.massa - self.G) * passo
            self.altura += self.v * passo
            self.massa -= empuxo / (self.ISP * self.G0) * passo
            if self.altura <= 0:
                self.toque, self.altura, self.v = -self.v, 0.0, 0.0


def pousar_demo(tela=None):
    """O mesmo laço de pousar(), com a NaveDemo no lugar do kRPC e do SAS."""
    nave = NaveDemo()
    guiagem = Guiagem(nave.densidade)
    avisos = Avisos()
    print(f"Demonstração: nave de mentira a {nave.altura:.0f} m, descendo a {-nave.v:.0f} m/s, em Kerbin.")
    fase = None
    proximo_status = 0.0
    anterior = time.monotonic()
    while True:
        l = nave.leitura()
        acelerador, modo = guiagem.passo(l)
        if guiagem.fase == POUSADA:
            print(f"Pousou! Descia a {nave.toque:.1f} m/s.")
            if tela is not None:
                tela.enviar(linhas_de_estado(l, guiagem, 0.0, modo, None))
            return True
        if guiagem.fase != fase:
            fase = guiagem.fase
            print(f"--> {fase} a {l.altura:.0f} m do chão")
        avisos.conferir(
            "empuxo", fase == QUEIMA and math.isinf(guiagem.necessaria),
            "empuxo insuficiente, não dá mais para parar a tempo!",
        )
        if tela is not None:
            tela.enviar(linhas_de_estado(l, guiagem, acelerador, modo, aviso_principal(avisos)), agora=False)
        agora = time.monotonic()
        if agora >= proximo_status:
            print(status(l, guiagem, acelerador))
            proximo_status = agora + (INTERVALO_STATUS_PERTO if l.altura < ALTURA_PERTO else INTERVALO_STATUS)
        time.sleep(INTERVALO)
        agora = time.monotonic()
        nave.avancar(acelerador, agora - anterior)
        anterior = agora


def main():
    """Devolve o código de saída: POUSOU, NAO_POUSOU ou INTERROMPIDO."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "address",
        nargs="?",
        default="127.0.0.1",
        help="IP do computador onde o KSP está rodando (padrão: este computador)",
    )
    parser.add_argument(
        "--tela",
        default="127.0.0.1",
        metavar="IP",
        help="IP do computador da ponte da tela, bridge/mfd.py (padrão: este computador)",
    )
    parser.add_argument("--demo", action="store_true", help="não conecta no KSP: pousa uma nave simulada")
    args = parser.parse_args()

    # No Windows, a ponte aborta o script com CTRL_BREAK (o Ctrl+C não chega
    # num processo aberto por outro). Aqui ele vira o mesmo KeyboardInterrupt.
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.default_int_handler)

    tela = TelaPouso(args.tela)
    try:
        if args.demo:
            try:
                return POUSOU if pousar_demo(tela) else NAO_POUSOU
            except KeyboardInterrupt:
                print("\nInterrompido: motor cortado.")
                return INTERROMPIDO

        # Importado só aqui: os testes usam a guiagem sem precisar do kRPC nem da serial.
        # A ponte fica em bridge/, ao lado de scripts/.
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bridge"))
        from ponte import conectar_krpc

        conn = conectar_krpc(args.address)
        try:
            try:
                nave = conn.space_center.active_vessel
            except (ValueError, RuntimeError):
                print("Nenhuma nave ativa: rode o script na cena de voo.")
                return NAO_POUSOU
            return POUSOU if pousar(conn, nave, tela) else NAO_POUSOU
        except KeyboardInterrupt:
            print("\nInterrompido: motor cortado, o controle volta para o piloto.")
            return INTERROMPIDO
        except (ValueError, RuntimeError) as e:
            print(f"\nPerdi a nave (explodiu ou o jogo saiu da cena de voo): {e}")
            return NAO_POUSOU
        finally:
            conn.close()
    finally:
        tela.fechar()


if __name__ == "__main__":
    sys.exit(main())
