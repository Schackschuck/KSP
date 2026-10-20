"""Subida automática: da plataforma até uma órbita circular, em qualquer planeta.

A nave decola, faz a curva de gravidade, corta o motor quando o apoastro chega
na altitude pedida, sobe sem motor até o apoastro e circulariza. Se for pedido
o plano de um alvo, espera a janela de lançamento (a hora em que a base passa
pelo plano do alvo) e, no fim, corrige o que sobrou de erro de plano.

Referencial
-----------
Todo vetor da guiagem está no referencial inercial do planeta, destro (regra da
mão direita): origem no centro, sem girar com o planeta, com o eixo do polo
norte em corpo.polo. Quem lê a nave entrega tudo nele. Daí saem:
 - cima = unit(r); latitude = asin(cima · polo);
 - o normal da órbita n = unit(r × v); a inclinação é acos(n · polo): 0° é leste
   no equador, 180° é retrógrada;
 - a direção do movimento num plano de normal n, na posição r:
   d(r) = unit(n × unit(r)), horizontal, no sentido da órbita;
 - o planeta gira para leste em volta de polo: leste = unit(polo × r) e
   norte = cima × leste.

Fases
-----
 JANELA       espera, sem motor, a hora em que a base passa pelo plano do alvo
 DECOLAGEM    sobe na vertical até ter ar (ou velocidade) para começar o giro
 GIRO         inclina o nariz do ângulo escolhido por simulação e espera o
              movimento acompanhar o nariz
 CURVA        no ar: o nariz segue o movimento em relação ao ar (sem ângulo de
              ataque), só o rumo pode desviar um pouco, para ir ao plano
 VACUO        acima de parte da atmosfera (ou sem ar): o nariz segue o pró-grado
              orbital
 COSTA        motor cortado no apoastro pedido; sobe até o apoastro, esperando
              com time warp, e acende de leve se o ar baixar o apoastro
 CIRCULARIZA  queima em malha fechada até a velocidade circular, no plano
 PLANO        se pediu o plano de um alvo e sobrou erro: queima no nó
 ORBITA       fim bom
 FALHA        fim ruim (sem combustível, plano fora do alcance...)

O giro
------
O ângulo de inclinação inicial (o "giro") é o único parâmetro do perfil. Perto
do chão a guiagem simula a subida inteira, em 2D, no plano da órbita: gravidade,
empuxo e Isp que mudam com a pressão, arrasto do ar (com a área medida em voo),
troca de estágios, o limite de pressão dinâmica e o corte no apoastro, com o
Δv de circularização no fim. Testa AMOSTRAS_GIRO valores na faixa e refina o
melhor por seção áurea: fica o giro de menor Δv total. A simulação usa as mesmas
funções de acelerador (acel_q, acel_corte) da guiagem.

Rumo e plano
------------
A cada instante o rumo vem da velocidade horizontal inercial que ainda falta
para ter a velocidade circular no plano (rumo_do_plano): isso já desconta a
rotação do planeta.

Com o plano de um alvo, o plano é fixo no espaço, e o erro de posição que sobra
da subida é corrigido pela fase PLANO. Sem alvo, o plano é refeito a cada passo,
da decolagem até o fim da circularização: é o plano que passa pela posição de
agora com a inclinação pedida (plano_pela_posicao), com o ramo para o norte ou
para o sul escolhido pela velocidade. A rotação do planeta empurra a nave para
fora do plano da decolagem, e assim ela não precisa voltar a ele: a inclinação
final sai a menos de 0,1° da pedida.

Sem a janela (inclinação pedida, sem alvo), o plano é o do lançamento para a
inclinação pedida, a partir da latitude da base. Inclinação menor que a
latitude não existe: sai na menor possível, com o aviso INCLINACAO.

No cockpit, quem abre o script é a ponte da tela (bridge/mfd.py), quando o
korry LANCAR fica apertado 5 s, com os valores escolhidos na página SUBIDA; o
script manda o estado dele para a ponte por UDP (as linhas SUB de
docs/protocolo.md).

Uso:
    python scripts/subida.py                      # KSP neste computador, 80 km, 0°
    python scripts/subida.py --altitude 100000 --inclinacao 45
    python scripts/subida.py --plano-do-alvo      # órbita no plano do alvo escolhido
    python scripts/subida.py 192.168.1.10         # KSP em outro computador
    python scripts/subida.py --demo               # sem o KSP: uma nave simulada sobe de Kerbin

A nave tem de estar parada no chão, com o primeiro estágio ainda por acender: o
script dá a ignição e troca de estágio quando o motor apaga. A carenagem não é
aberta pelo script.
Ctrl+C corta o motor e devolve o controle ao piloto.

Sai com o código 0 em órbita, 1 se não chegou e 130 se foi interrompido.
"""

import math
from dataclasses import dataclass, replace

G0 = 9.80665
V_GIRO = 50.0
ALTURA_GIRO_AR = 100.0
ALTURA_GIRO_VACUO = 300.0
GIRO_AR = (0.5, 30.0)
GIRO_VACUO = (5.0, 85.0)
GIRO_PADRAO_AR = 5.0
GIRO_PADRAO_VACUO = 45.0
GIRO_MAX_S = 20.0
TOL_GIRO = 0.5
FRACAO_VACUO = 0.6
DESVIO_AR = 3.0
V_RUMO_MIN = 50.0
Q_MAX = 30_000.0
Q_FAIXA = 20_000.0
ACEL_Q_MIN = 0.4
ESCALA_CORTE = 5_000.0
ACEL_MIN = 0.02
TOL_AP = 100.0
TOL_COSTA = 300.0
ACEL_COSTA = 0.1
MARGEM_WARP = 30.0
ESPERA_TEMPO_REAL = 60.0
ERRO_APONTAR = 5.0
TEMPO_FINAL = 3.0
TOL_DV = 0.3
W_PROXIMO = 10.0
W_CRESCE = 0.5
ANGULO_PLANO = 0.05
TOL_INCLINACAO = 0.25
TOL_RAMO = 1e-3
ESPERA_ESTAGIO = 1.0
Q_MEDIR = 50.0
SUAVIZACAO = 0.2
DT_MAX_DV = 1.0
PASSO_SIM = 0.5
T_MAX_SIM = 1200.0
AMOSTRAS_GIRO = 12
ITERACOES_GIRO = 12
AMOSTRAS_JANELA = 720
ITERACOES_JANELA = 40
TWR_MIN = 1.05
ALTITUDE_MIN_AR = 5_000.0
ALTITUDE_MIN_VACUO = 10_000.0

PASSO_FISICA = 0.05
PASSO_WARP = 1.0
GIRO_NARIZ_MAX = 15.0

JANELA = "JANELA"
DECOLAGEM = "DECOLAGEM"
GIRO = "GIRO"
CURVA = "CURVA"
VACUO = "VACUO"
COSTA = "COSTA"
CIRCULARIZA = "CIRCULARIZA"
PLANO = "PLANO"
ORBITA = "ORBITA"
FALHA = "FALHA"

AVISO_EMPUXO = "EMPUXO"
AVISO_ALTITUDE = "ALTITUDE"
AVISO_INCLINACAO = "INCLINACAO"
AVISO_ALVO = "ALVO"
AVISO_COMBUSTIVEL = "COMBUSTIVEL"
FASES_DO_PLANO = (DECOLAGEM, GIRO, CURVA, VACUO, COSTA, CIRCULARIZA)
PRIORIDADE_AVISOS = (
    AVISO_COMBUSTIVEL,
    AVISO_ALVO,
    AVISO_ALTITUDE,
    AVISO_INCLINACAO,
    AVISO_EMPUXO,
)


def soma(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def esc(k, a):
    return (k * a[0], k * a[1], k * a[2])


def ponto(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cruz(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norma(a):
    return math.sqrt(ponto(a, a))


def unit(a):
    """Vetor de tamanho 1 na direção de a; o vetor nulo continua nulo."""
    n = norma(a)
    if n == 0.0:
        return (0.0, 0.0, 0.0)
    return esc(1.0 / n, a)


def limitar(x, baixo, alto):
    return max(baixo, min(alto, x))


def angulo(a, b):
    """Graus entre dois vetores (0 se algum for nulo)."""
    na, nb = norma(a), norma(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return math.degrees(math.acos(limitar(ponto(a, b) / (na * nb), -1.0, 1.0)))


def horizontal(v, cima):
    """A parte de v que fica no plano do horizonte."""
    return sub(v, esc(ponto(v, cima), cima))


def pitch_de(v, cima):
    """Graus acima do horizonte da direção de v."""
    return math.degrees(math.asin(limitar(ponto(unit(v), cima), -1.0, 1.0)))


def rumo_de(v, norte, leste):
    """Rumo de v em graus, de 0 a 360: 0 norte, 90 leste."""
    return math.degrees(math.atan2(ponto(v, leste), ponto(v, norte))) % 360.0


def rotacionar(a, eixo, radianos):
    """Gira a em volta do eixo (unitário) pela regra da mão direita."""
    c, s = math.cos(radianos), math.sin(radianos)
    return soma(
        soma(esc(c, a), esc(s, cruz(eixo, a))),
        esc(ponto(eixo, a) * (1.0 - c), eixo),
    )


def direcao_no_plano(n, r):
    """d(r): a direção do movimento, horizontal, no plano de normal n, em r."""
    return unit(cruz(n, unit(r)))


@dataclass
class Corpo:
    nome: str
    mu: float
    raio: float
    periodo: float
    topo: float
    densidade: object
    pressao: object
    polo: tuple

    @property
    def omega(self):
        return 2.0 * math.pi / self.periodo


@dataclass
class Estagio:
    """Um trecho de queima: começa com massa_inicial, queima combustivel e larga seca_solta no fim."""

    massa_inicial: float
    combustivel: float
    seca_solta: float
    empuxo_vacuo: float
    empuxo_mar: float
    isp_vacuo: float
    isp_mar: float


@dataclass
class Leitura:
    t: float
    r: tuple
    v: tuple
    v_sup: tuple
    norte: tuple
    leste: tuple
    nariz: tuple
    radar: float
    q: float
    pressao: float
    arrasto: float
    massa: float
    empuxo: float
    isp: float
    apagado: bool
    motor_abaixo: bool
    pousada: bool


@dataclass
class Comando:
    acelerador: float = 0.0
    pitch: float = 90.0
    rumo: float = 90.0
    estagiar: bool = False
    acelerar_ate: float | None = None


@dataclass
class EstadoSim:
    """Início da simulação do giro: raio, velocidade vertical e velocidade ao longo de d."""

    r: float
    v_r: float
    v_t: float


def empuxo_em(estagio, pressao):
    """Empuxo (N) na pressão dada (atm): reta entre o vácuo e 1 atm, nunca abaixo de 0."""
    f = estagio.empuxo_vacuo + (estagio.empuxo_mar - estagio.empuxo_vacuo) * pressao
    return max(0.0, f)


def isp_em(estagio, pressao):
    """Isp (s) na pressão dada (atm): reta entre o vácuo e 1 atm, nunca abaixo de 1 s."""
    isp = estagio.isp_vacuo + (estagio.isp_mar - estagio.isp_vacuo) * pressao
    return max(1.0, isp)


def acel_q(q):
    """Acelerador que respeita o limite da pressão dinâmica (Pa)."""
    if q <= Q_MAX:
        return 1.0
    return max(ACEL_Q_MIN, 1.0 - (q - Q_MAX) / Q_FAIXA)


def acel_corte(ap_alt, alvo_alt):
    """Acelerador que vai caindo quando o apoastro (altitude) chega perto do pedido; 0 se passou."""
    falta = alvo_alt - ap_alt
    if falta <= 0.0:
        return 0.0
    return min(1.0, max(ACEL_MIN, falta / ESCALA_CORTE))


def elementos(corpo, r, v):
    """(a, e, ra, rp) da órbita, em metros do centro, pela energia e pelo momento angular.

    ra é infinito numa trajetória de escape (energia >= 0), e a também. O
    periastro sai de h²/(mu·(1+e)), que não perde precisão perto de uma órbita
    circular. Apoastro e periastro em altitude: ra - raio, rp - raio.
    """
    dist = norma(r)
    energia = ponto(v, v) / 2.0 - corpo.mu / dist
    h = norma(cruz(r, v))
    e = math.sqrt(max(0.0, 1.0 + 2.0 * energia * h * h / (corpo.mu * corpo.mu)))
    rp = h * h / (corpo.mu * (1.0 + e))
    if energia < 0.0:
        a = -corpo.mu / (2.0 * energia)
        ra = a * (1.0 + e)
    else:
        a, ra = math.inf, math.inf
    return a, e, ra, rp


def tempo_de_queima(dv, massa, empuxo, isp):
    """Segundos para gastar dv (m/s) com empuxo constante, pela equação do foguete."""
    if empuxo <= 0.0 or isp <= 0.0:
        return math.inf
    ve = isp * G0
    m_fim = massa * math.exp(-dv / ve)
    return (massa - m_fim) * ve / empuxo


def tempo_ate_apoastro(corpo, r, v):
    """Segundos até o próximo apoastro, pela anomalia média (0 numa órbita circular).

    A anomalia excêntrica E sai de cos E = (a - r)/(a·e) e de
    sen E = (r · v)/(e·sqrt(mu·a)); a média é M = E - e·sen E, e o apoastro
    está em M = pi.
    """
    a, e, _, _ = elementos(corpo, r, v)
    if not math.isfinite(a) or e < 1e-9:
        return 0.0
    cos_e = limitar((1.0 - norma(r) / a) / e, -1.0, 1.0)
    sen_e = ponto(r, v) / (e * math.sqrt(corpo.mu * a))
    excentrica = math.atan2(sen_e, cos_e)
    media = excentrica - e * math.sin(excentrica)
    movimento = math.sqrt(corpo.mu / a**3)
    return ((math.pi - media) % (2.0 * math.pi)) / movimento


def _direcoes_do_plano(l, corpo, inclinacao):
    """(cima, d_norte, d_sul): as duas direções de saída do plano da inclinação pedida, a partir de r.

    O rumo inercial β vem de sen β = cos(i)/cos(φ), com φ a latitude. Se o
    quociente passa de 1, a inclinação pedida é menor que a latitude e não
    existe: usa-se o limite. Os dois ramos são β (cos β >= 0, para o norte) e
    180° - β (para o sul); a direção de saída é d0 = cos β·norte + sen β·leste.
    """
    cima = unit(l.r)
    latitude = math.asin(limitar(ponto(cima, corpo.polo), -1.0, 1.0))
    razao = math.cos(math.radians(inclinacao)) / max(math.cos(latitude), 1e-9)
    seno = limitar(razao, -1.0, 1.0)
    coseno = math.sqrt(max(0.0, 1.0 - seno * seno))
    d_norte = soma(esc(coseno, l.norte), esc(seno, l.leste))
    d_sul = soma(esc(-coseno, l.norte), esc(seno, l.leste))
    return cima, d_norte, d_sul


def _plano_da_direcao(cima, d0, corpo):
    n = unit(cruz(cima, d0))
    usada = math.degrees(math.acos(limitar(ponto(n, corpo.polo), -1.0, 1.0)))
    return n, usada


def plano_do_lancamento(l, corpo, inclinacao):
    """(n, inclinacao_usada): o plano que sai da base com a inclinação pedida, no ramo para o norte.

    O normal é unit(cima × d0). A inclinacao_usada é a pedida, ou a possível
    quando a pedida é menor que a latitude.
    """
    cima, d_norte, _ = _direcoes_do_plano(l, corpo, inclinacao)
    return _plano_da_direcao(cima, d_norte, corpo)


def plano_pela_posicao(l, corpo, inclinacao):
    """(n, inclinacao_usada): o plano que passa pela posição de agora com a inclinação pedida.

    É a conta do plano_do_lancamento refeita na latitude de agora, com os dois
    ramos (β e 180° - β). Vale o ramo cuja direção de saída está mais perto da
    velocidade horizontal inercial; no empate (no chão, onde ela é só a
    rotação do planeta, para leste, e os dois ramos fazem o mesmo ângulo com
    ela), o ramo para o norte. A folga TOL_RAMO impede que o ruído da
    velocidade troque de ramo no chão.
    """
    cima, d_norte, d_sul = _direcoes_do_plano(l, corpo, inclinacao)
    v_h = unit(horizontal(l.v, cima))
    if ponto(d_sul, v_h) > ponto(d_norte, v_h) + TOL_RAMO:
        return _plano_da_direcao(cima, d_sul, corpo)
    return _plano_da_direcao(cima, d_norte, corpo)


def rumo_do_plano(l, corpo, n, alvo_raio):
    """Rumo (graus, 0 norte, 90 leste) que leva a velocidade horizontal inercial à circular no plano n.

    A velocidade circular a alvo_raio, na direção d(r) do plano, menos a
    velocidade horizontal inercial de agora é o que falta; o rumo é o dessa
    diferença. No chão a velocidade horizontal é a rotação do planeta, então
    a conta já desconta a rotação (Kerbin, 80 km, 45°: 41,7°). Quando falta
    menos que 5% da circular, usa a direção d(r) mesmo.
    """
    cima = unit(l.r)
    v_orb = math.sqrt(corpo.mu / alvo_raio)
    d = direcao_no_plano(n, l.r)
    w = sub(esc(v_orb, d), horizontal(l.v, cima))
    if norma(w) < 0.05 * v_orb:
        w = d
    return rumo_de(w, l.norte, l.leste)


def proxima_janela(l, corpo, n_alvo):
    """UT em que a base passa pelo plano do alvo (normal n_alvo), ou None se nunca passa.

    A base gira em volta do polo: depois de dt, com alfa = omega·dt,
    r(dt) = r_par + r_perp·cos(alfa) + |r_perp|·leste·sen(alfa), usando o leste
    da leitura. Procura a primeira troca de sinal de n_alvo · unit(r(dt)) em
    uma volta, amostrando AMOSTRAS_JANELA pontos, e refina por bisseção. Um
    zero exato em dt = 0 é janela agora. Sem troca de sinal, a latitude da
    base é maior que a inclinação do alvo.
    """
    polo = corpo.polo
    r_par = esc(ponto(l.r, polo), polo)
    r_perp = sub(l.r, r_par)
    raio_perp = norma(r_perp)

    def f(dt):
        alfa = corpo.omega * dt
        r = soma(r_par, soma(esc(math.cos(alfa), r_perp), esc(raio_perp * math.sin(alfa), l.leste)))
        return ponto(n_alvo, unit(r))

    anterior_dt = 0.0
    anterior = f(0.0)
    if anterior == 0.0:
        return l.t
    for i in range(1, AMOSTRAS_JANELA + 1):
        atual_dt = corpo.periodo * i / AMOSTRAS_JANELA
        atual = f(atual_dt)
        if atual == 0.0:
            return l.t + atual_dt
        if anterior * atual < 0.0:
            baixo, alto, f_baixo = anterior_dt, atual_dt, anterior
            for _ in range(ITERACOES_JANELA):
                meio = (baixo + alto) / 2.0
                f_meio = f(meio)
                if f_baixo * f_meio <= 0.0:
                    alto = meio
                else:
                    baixo, f_baixo = meio, f_meio
            return l.t + (baixo + alto) / 2.0
        anterior_dt, anterior = atual_dt, atual
    return None


def no_relativo(corpo, r, v, n_alvo):
    """(dt, u): segundos até o nó entre a órbita de agora e o plano n_alvo, e a linha dos nós.

    Os dois planos se cruzam na linha u = unit(n_atual × n_alvo). Para cada
    sentido da linha (u e -u) mede-se o ângulo, no sentido do movimento, da
    posição até ele; vale o menor. O tempo é o ângulo dividido pelo movimento
    médio (órbita quase circular).
    """
    cima = unit(r)
    n_atual = unit(cruz(r, v))
    u = unit(cruz(n_atual, n_alvo))
    menor = math.inf
    for c in (u, esc(-1.0, u)):
        alfa = math.atan2(ponto(cruz(cima, c), n_atual), ponto(cima, c)) % (2.0 * math.pi)
        if alfa > 2.0 * math.pi - 1e-6:
            alfa -= 2.0 * math.pi
        menor = min(menor, alfa)
    a = elementos(corpo, r, v)[0]
    if not math.isfinite(a) or a <= 0.0:
        a = norma(r)
    return menor / math.sqrt(corpo.mu / a**3), u


def simular(corpo, estagios, estado, giro, alvo_alt, area, v_ar0):
    """(dv, duracao) de uma subida simulada com o giro dado; (inf, inf) se for inviável.

    Em 2D, no plano da subida, em coordenadas polares inerciais: r, v_r
    (subida) e v_t (horizontal, ao longo de d). O ar gira com o planeta, então
    a velocidade horizontal em relação ao ar é va_t = v_t - v_ar0·r/r0, e o
    arrasto é area·densidade·|va|², contra va (a área já inclui o coeficiente e
    o 1/2). As acelerações, com theta o ângulo do nariz acima do horizonte:

        a_r = (empuxo/m)·sen θ - arrasto_r - mu/r² + v_t²/r
        a_t = (empuxo/m)·cos θ - arrasto_t - v_r·v_t/r

    Os dois últimos termos de cada uma vêm das coordenadas polares (a força
    centrífuga e a conservação do momento angular). Euler semi-implícito em
    passos de PASSO_SIM. A atitude é a da guiagem: theta = 90 - giro até o
    movimento em relação ao ar alcançá-lo (ou passar GIRO_MAX_S), depois o
    movimento em relação ao ar abaixo de FRACAO_VACUO·topo, e o pró-grado
    inercial acima (ou sempre, sem ar). O acelerador é
    min(acel_q, acel_corte). Depois do corte (apoastro a TOL_AP do pedido) a
    nave sobe sem motor, com arrasto, e acende com ACEL_COSTA ao longo do
    pró-grado se o apoastro cair mais de TOL_COSTA; ao sair do ar soma-se a
    circularização, sqrt(mu/ra) - h/ra, com h = r·v_t.

    Inviável: bater no chão, descer abaixo da altitude do início do giro antes
    do corte, acabar o combustível antes do corte ou passar de T_MAX_SIM.
    Devolve o Δv total (somando empuxo/massa·dt, como a guiagem) e o tempo.
    """
    mu, raio, topo = corpo.mu, corpo.raio, corpo.topo
    r0 = estado.r
    alt0 = r0 - raio
    r, v_r, v_t = estado.r, estado.v_r, estado.v_t
    indice = 0
    massa = estagios[0].massa_inicial
    combustivel = estagios[0].combustivel
    t = 0.0
    dv = 0.0
    cortou = False
    alcancou = False
    costa = False
    dt = PASSO_SIM
    while t < T_MAX_SIM:
        alt = r - raio
        if r <= raio:
            return math.inf, math.inf
        ra = elementos(corpo, (r, 0.0, 0.0), (v_r, v_t, 0.0))[2]
        ap = ra - raio
        if not cortou and ap >= alvo_alt - TOL_AP:
            cortou = True
        if cortou and alt >= topo:
            if not math.isfinite(ra):
                return math.inf, math.inf
            return dv + math.sqrt(mu / ra) - r * v_t / ra, t
        if not cortou and alt < alt0:
            return math.inf, math.inf

        esgotado = False
        while True:
            e = estagios[indice]
            if combustivel > 0.0 and max(e.empuxo_vacuo, e.empuxo_mar) > 0.0:
                break
            if indice + 1 >= len(estagios):
                esgotado = True
                break
            massa -= e.seca_solta + max(combustivel, 0.0)
            indice += 1
            combustivel = estagios[indice].combustivel
        if esgotado and not cortou:
            return math.inf, math.inf

        rho = corpo.densidade(alt)
        p = corpo.pressao(alt)
        va_t = v_t - v_ar0 * r / r0
        va2 = v_r * v_r + va_t * va_t
        va = math.sqrt(va2)
        q = 0.5 * rho * va2

        if esgotado:
            acel = 0.0
        elif not cortou:
            acel = min(acel_q(q), acel_corte(ap, alvo_alt))
        else:
            if ap < alvo_alt - TOL_COSTA:
                costa = True
            elif ap >= alvo_alt - TOL_AP:
                costa = False
            acel = ACEL_COSTA if costa else 0.0

        if not alcancou:
            gama = math.degrees(math.atan2(v_r, va_t))
            if gama <= 90.0 - giro + TOL_GIRO or t >= GIRO_MAX_S:
                alcancou = True
        if not alcancou:
            theta = 90.0 - giro
        elif cortou or topo <= 0.0 or alt >= FRACAO_VACUO * topo:
            theta = math.degrees(math.atan2(v_r, v_t))
        else:
            theta = math.degrees(math.atan2(v_r, va_t))

        empuxo = 0.0
        dm = 0.0
        if acel > 0.0:
            e = estagios[indice]
            empuxo = acel * empuxo_em(e, p)
            dm = min(empuxo / (isp_em(e, p) * G0) * dt, combustivel)
        a_emp = empuxo / massa
        arrasto = area * rho * va2
        if va > 0.0:
            arrasto_r = arrasto * v_r / va / massa
            arrasto_t = arrasto * va_t / va / massa
        else:
            arrasto_r = arrasto_t = 0.0
        th = math.radians(theta)
        a_r = a_emp * math.sin(th) - arrasto_r - mu / (r * r) + v_t * v_t / r
        a_t = a_emp * math.cos(th) - arrasto_t - v_r * v_t / r
        v_r += a_r * dt
        v_t += a_t * dt
        r += v_r * dt
        dv += a_emp * dt
        massa -= dm
        combustivel -= dm
        t += dt
    return math.inf, math.inf


def escolher_giro(corpo, estagios, estado, alvo_alt, area, v_ar0):
    """(giro, achou): o giro de menor Δv total pela simulação.

    A faixa é GIRO_AR com ar e GIRO_VACUO sem. Testa AMOSTRAS_GIRO valores
    igualmente espaçados e refina por seção áurea entre os vizinhos do melhor,
    ITERACOES_GIRO vezes; o resultado nunca é pior que a melhor amostra. Se
    nenhum valor chega em órbita, devolve o giro padrão e achou = False.
    """
    com_ar = corpo.topo > 0.0
    baixo, alto = GIRO_AR if com_ar else GIRO_VACUO
    padrao = GIRO_PADRAO_AR if com_ar else GIRO_PADRAO_VACUO

    def custo(giro):
        return simular(corpo, estagios, estado, giro, alvo_alt, area, v_ar0)[0]

    passo = (alto - baixo) / (AMOSTRAS_GIRO - 1)
    giros = [baixo + i * passo for i in range(AMOSTRAS_GIRO)]
    custos = [custo(g) for g in giros]
    k = min(range(AMOSTRAS_GIRO), key=custos.__getitem__)
    if math.isinf(custos[k]):
        return padrao, False

    melhor_giro, melhor_custo = giros[k], custos[k]
    esquerda = giros[max(k - 1, 0)]
    direita = giros[min(k + 1, AMOSTRAS_GIRO - 1)]
    razao = (math.sqrt(5.0) - 1.0) / 2.0
    c = direita - razao * (direita - esquerda)
    d = esquerda + razao * (direita - esquerda)
    f_c, f_d = custo(c), custo(d)
    for _ in range(ITERACOES_GIRO):
        for giro, valor in ((c, f_c), (d, f_d)):
            if valor < melhor_custo:
                melhor_giro, melhor_custo = giro, valor
        if f_c <= f_d:
            direita, d, f_d = d, c, f_c
            c = direita - razao * (direita - esquerda)
            f_c = custo(c)
        else:
            esquerda, c, f_c = c, d, f_d
            d = esquerda + razao * (direita - esquerda)
            f_d = custo(d)
    for giro, valor in ((c, f_c), (d, f_d)):
        if valor < melhor_custo:
            melhor_giro, melhor_custo = giro, valor
    return melhor_giro, True


class Guiagem:
    """Decide o acelerador, a atitude e o estágio a cada leitura.

    Não conhece o kRPC: recebe uma Leitura e devolve um Comando, de modo que
    os testes usam esta mesma guiagem com a NaveSimulada.

    corpo, alvo_alt (m), inclinacao (graus) e, se for o caso, n_alvo (o normal
    do plano do alvo, no referencial da guiagem). ler_estagios() devolve a
    lista de Estagio a partir do trecho de agora; é chamada uma vez, no início
    do giro, e sem ela o giro é o padrão.

    Atributos para a tela: fase, aviso (ou None), giro (ou None), n (o plano),
    inclinacao_alvo, janela (UT ou None), dv (o Δv gasto, sem contar os passos
    de mais de DT_MAX_DV s, que são o time warp) e acelerador.
    """

    def __init__(self, corpo, alvo_alt, inclinacao, n_alvo=None, ler_estagios=None):
        self.corpo = corpo
        self.alvo_alt = alvo_alt
        self.inclinacao = inclinacao
        self._n_alvo = n_alvo
        self._ler_estagios = ler_estagios
        self.fase = DECOLAGEM
        self.giro = None
        self.n = None
        self.inclinacao_alvo = inclinacao
        self.janela = None
        self.dv = 0.0
        self.acelerador = 0.0
        self.area = 0.0
        self._avisos = set()
        self._iniciada = False
        self._t_anterior = None
        self._t_giro = 0.0
        self._ultimo_estagio = -math.inf
        self._costa_ligada = False
        self._queimando = False
        self._w_min = math.inf
        self._pitch = 90.0
        self._rumo = 90.0
        self._cima = (0.0, 0.0, 1.0)
        self._altitude = 0.0
        self._ap = 0.0
        self._fases = {
            JANELA: self._fase_janela,
            DECOLAGEM: self._fase_decolagem,
            GIRO: self._fase_giro,
            CURVA: self._fase_curva,
            VACUO: self._fase_vacuo,
            COSTA: self._fase_costa,
            CIRCULARIZA: self._fase_circulariza,
            PLANO: self._fase_plano,
            ORBITA: self._fase_parada,
            FALHA: self._fase_parada,
        }

    @property
    def aviso(self):
        """O aviso mais importante que vale agora, ou None."""
        for nome in PRIORIDADE_AVISOS:
            if nome in self._avisos:
                return nome
        return None

    def passo(self, l):
        """Devolve o Comando para esta leitura."""
        corpo = self.corpo
        self._cima = unit(l.r)
        self._altitude = norma(l.r) - corpo.raio
        self._ap = elementos(corpo, l.r, l.v)[2] - corpo.raio
        self._acumular(l)
        if not self._iniciada:
            self._iniciar(l)
        if self._n_alvo is None and self.fase in FASES_DO_PLANO:
            self._refazer_plano(l)
        comando = None
        for _ in range(len(self._fases) + 1):
            comando = self._fases[self.fase](l)
            if comando is not None:
                break
        if comando is None:
            comando = self._fase_parada(l)
        self._cuidar_do_motor(l, comando)
        if self.fase in (ORBITA, FALHA):
            comando.acelerador = 0.0
        self._pitch, self._rumo = comando.pitch, comando.rumo
        self.acelerador = comando.acelerador
        return comando

    def _avisar(self, nome):
        self._avisos.add(nome)

    def _acumular(self, l):
        """Soma o Δv gasto desde a leitura anterior e atualiza a área de arrasto."""
        if self._t_anterior is not None:
            dt = l.t - self._t_anterior
            if 0.0 < dt <= DT_MAX_DV and l.massa > 0.0:
                self.dv += self.acelerador * l.empuxo / l.massa * dt
        self._t_anterior = l.t
        if l.q > Q_MEDIR:
            densidade = self.corpo.densidade(self._altitude)
            v2 = ponto(l.v_sup, l.v_sup)
            if densidade * v2 > 0.0:
                medida = l.arrasto / (densidade * v2)
                if self.area == 0.0:
                    self.area = medida
                else:
                    self.area += SUAVIZACAO * (medida - self.area)

    def _iniciar(self, l):
        self._iniciada = True
        if self._n_alvo is None:
            self.fase = DECOLAGEM
            return
        polo = self.corpo.polo
        self.inclinacao_alvo = math.degrees(math.acos(limitar(ponto(self._n_alvo, polo), -1.0, 1.0)))
        self.janela = proxima_janela(l, self.corpo, self._n_alvo)
        if self.janela is None:
            self._avisar(AVISO_INCLINACAO)
            self.fase = FALHA
        else:
            self.fase = JANELA

    def _refazer_plano(self, l):
        """Sem alvo, o plano passa pela posição de agora; só o primeiro cálculo dá aviso e inclinacao_alvo.

        Depois do primeiro cálculo vale a inclinação possível dele: com a
        pedida menor que a latitude, refazer o plano com a pedida faria o
        limite andar junto com a latitude e a nave brigaria com a própria
        órbita.
        """
        primeiro = self.n is None
        inclinacao = self.inclinacao if primeiro else self.inclinacao_alvo
        self.n, usada = plano_pela_posicao(l, self.corpo, inclinacao)
        if primeiro:
            self.inclinacao_alvo = usada
            if abs(usada - self.inclinacao) > TOL_INCLINACAO:
                self._avisar(AVISO_INCLINACAO)

    def _cuidar_do_motor(self, l, comando):
        """Estágio quando o motor apagou; FALHA se não há mais motor para acender."""
        if self.fase in (JANELA, ORBITA, FALHA):
            return
        fora_do_ar = self._altitude >= self.corpo.topo
        quer = (
            comando.acelerador > 0.0
            or self.fase in (CIRCULARIZA, PLANO)
            or (self.fase == COSTA and fora_do_ar)
        )
        if not quer or not (l.apagado or l.empuxo <= 0.0):
            return
        if l.t - self._ultimo_estagio < ESPERA_ESTAGIO:
            return
        if l.motor_abaixo:
            comando.estagiar = True
            self._ultimo_estagio = l.t
        elif l.empuxo <= 0.0:
            self._avisar(AVISO_COMBUSTIVEL)
            self.fase = FALHA
            comando.acelerador = 0.0

    def _rumo_plano(self, l):
        return rumo_do_plano(l, self.corpo, self.n, self.corpo.raio + self.alvo_alt)

    def _fase_parada(self, l):
        return Comando(0.0, self._pitch, self._rumo)

    def _fase_janela(self, l):
        if l.t >= self.janela:
            self.n = self._n_alvo
            self.fase = DECOLAGEM
            return None
        comando = Comando(0.0, 90.0, 90.0)
        if self.janela - l.t > ESPERA_TEMPO_REAL:
            comando.acelerar_ate = self.janela - ESPERA_TEMPO_REAL
        return comando

    def _fase_decolagem(self, l):
        corpo = self.corpo
        if l.empuxo > 0.0:
            peso = l.massa * corpo.mu / corpo.raio**2
            if l.empuxo / peso < TWR_MIN:
                self._avisar(AVISO_EMPUXO)
            else:
                self._avisos.discard(AVISO_EMPUXO)
        altura_giro = ALTURA_GIRO_AR if corpo.topo > 0.0 else ALTURA_GIRO_VACUO
        if l.radar >= altura_giro and ponto(l.v_sup, self._cima) >= V_GIRO:
            self._iniciar_giro(l)
            self.fase = GIRO
            return None
        return Comando(acel_q(l.q), 90.0, self._rumo_plano(l))

    def _iniciar_giro(self, l):
        """Escolhe o giro por simulação, a partir do estado de agora."""
        self._t_giro = l.t
        estagios = self._ler_estagios() if self._ler_estagios is not None else None
        if not estagios:
            self.giro = GIRO_PADRAO_AR if self.corpo.topo > 0.0 else GIRO_PADRAO_VACUO
            return
        d = direcao_no_plano(self.n, l.r)
        estado = EstadoSim(norma(l.r), ponto(l.v, self._cima), ponto(l.v, d))
        v_ar0 = ponto(sub(l.v, l.v_sup), d)
        self.giro, achou = escolher_giro(self.corpo, estagios, estado, self.alvo_alt, self.area, v_ar0)
        if not achou:
            self._avisar(AVISO_COMBUSTIVEL)

    def _subir(self, l, pitch, rumo):
        """O motor das fases com a subida acesa; passa para COSTA ao chegar no apoastro pedido."""
        if self._ap >= self.alvo_alt - TOL_AP:
            self.fase = COSTA
            return None
        acelerador = min(acel_q(l.q), acel_corte(self._ap, self.alvo_alt))
        return Comando(acelerador, pitch, rumo)

    def _fase_giro(self, l):
        pitch_chao = pitch_de(l.v_sup, self._cima)
        if pitch_chao <= 90.0 - self.giro + TOL_GIRO or l.t - self._t_giro >= GIRO_MAX_S:
            self.fase = CURVA if self.corpo.topo > 0.0 else VACUO
            return None
        return self._subir(l, 90.0 - self.giro, self._rumo_plano(l))

    def _fase_curva(self, l):
        if self._altitude >= FRACAO_VACUO * self.corpo.topo:
            self.fase = VACUO
            return None
        pitch = pitch_de(l.v_sup, self._cima)
        rumo = self._rumo_plano(l)
        if norma(horizontal(l.v_sup, self._cima)) > V_RUMO_MIN:
            rumo_chao = rumo_de(l.v_sup, l.norte, l.leste)
            desvio = (rumo - rumo_chao + 180.0) % 360.0 - 180.0
            rumo = (rumo_chao + limitar(desvio, -DESVIO_AR, DESVIO_AR)) % 360.0
        return self._subir(l, pitch, rumo)

    def _fase_vacuo(self, l):
        return self._subir(l, pitch_de(l.v, self._cima), self._rumo_plano(l))

    def _w_circular(self, l):
        """O que falta de velocidade para a circular de agora, no plano n."""
        v_circ = math.sqrt(self.corpo.mu / norma(l.r))
        return sub(esc(v_circ, direcao_no_plano(self.n, l.r)), l.v)

    def _w_plano(self, l):
        """O que falta para a velocidade horizontal virar a do plano do alvo, sem mudar de tamanho."""
        v_h = horizontal(l.v, self._cima)
        alvo = esc(norma(v_h), direcao_no_plano(self._n_alvo, l.r))
        return sub(soma(esc(ponto(l.v, self._cima), self._cima), alvo), l.v)

    def _aguardar(self, l, restante, w):
        """Comando de espera antes de uma queima: warp longe, nariz no pró-grado e depois na queima."""
        alvo = w if restante <= MARGEM_WARP else l.v
        comando = Comando(0.0, pitch_de(alvo, self._cima), rumo_de(alvo, l.norte, l.leste))
        if restante > MARGEM_WARP + 5.0:
            comando.acelerar_ate = l.t + restante - MARGEM_WARP
        return comando

    def _fase_costa(self, l):
        corpo = self.corpo
        pitch = pitch_de(l.v, self._cima)
        rumo = rumo_de(l.v, l.norte, l.leste)
        if self._altitude < corpo.topo:
            if self._ap < self.alvo_alt - TOL_COSTA:
                self._costa_ligada = True
            elif self._ap >= self.alvo_alt - TOL_AP:
                self._costa_ligada = False
            return Comando(ACEL_COSTA if self._costa_ligada else 0.0, pitch, rumo)
        self._costa_ligada = False
        a, _, ra, _ = elementos(corpo, l.r, l.v)
        if not math.isfinite(ra) or l.empuxo <= 0.0 or l.isp <= 0.0:
            return Comando(0.0, pitch, rumo)
        v_ap = math.sqrt(corpo.mu * (2.0 / ra - 1.0 / a))
        dv = math.sqrt(corpo.mu / ra) - v_ap
        duracao = tempo_de_queima(dv, l.massa, l.empuxo, l.isp)
        restante = tempo_ate_apoastro(corpo, l.r, l.v) - duracao / 2.0
        if restante <= 0.0:
            self._w_min = math.inf
            self.fase = CIRCULARIZA
            return None
        return self._aguardar(l, restante, self._w_circular(l))

    def _queimar(self, l, w):
        """Comando da queima em malha fechada para o vetor w, ou None quando terminou."""
        tamanho = norma(w)
        if tamanho < TOL_DV:
            return None
        self._w_min = min(self._w_min, tamanho)
        if self._w_min < W_PROXIMO and tamanho > self._w_min + W_CRESCE:
            return None
        pitch = pitch_de(w, self._cima)
        rumo = rumo_de(w, l.norte, l.leste)
        if l.empuxo <= 0.0 or angulo(l.nariz, w) > ERRO_APONTAR:
            acelerador = 0.0
        else:
            acelerador = min(1.0, max(ACEL_MIN, tamanho * l.massa / (l.empuxo * TEMPO_FINAL)))
        return Comando(acelerador, pitch, rumo)

    def _depois_da_circularizacao(self, l):
        if self._n_alvo is not None:
            n_atual = unit(cruz(l.r, l.v))
            if angulo(n_atual, self._n_alvo) > ANGULO_PLANO:
                self._queimando = False
                self._w_min = math.inf
                self.fase = PLANO
                return
        self.fase = ORBITA

    def _fase_circulariza(self, l):
        comando = self._queimar(l, self._w_circular(l))
        if comando is None:
            self._depois_da_circularizacao(l)
        return comando

    def _fase_plano(self, l):
        if not self._queimando:
            if l.empuxo <= 0.0 or l.isp <= 0.0:
                return Comando(0.0, self._pitch, self._rumo)
            n_atual = unit(cruz(l.r, l.v))
            espera, _ = no_relativo(self.corpo, l.r, l.v, self._n_alvo)
            teta = math.radians(angulo(n_atual, self._n_alvo))
            dv = 2.0 * norma(horizontal(l.v, self._cima)) * math.sin(teta / 2.0)
            duracao = tempo_de_queima(dv, l.massa, l.empuxo, l.isp)
            restante = espera - duracao / 2.0
            if restante > 0.0:
                return self._aguardar(l, restante, self._w_plano(l))
            self._queimando = True
            self._w_min = math.inf
        comando = self._queimar(l, self._w_plano(l))
        if comando is None:
            self.fase = ORBITA
        return comando


def _sem_ar(altitude):
    return 0.0


def _densidade_kerbin(altitude):
    if altitude >= 70_000.0:
        return 0.0
    return 1.225 * math.exp(-max(altitude, 0.0) / 5600.0)


def _pressao_kerbin(altitude):
    if altitude >= 70_000.0:
        return 0.0
    return math.exp(-max(altitude, 0.0) / 5600.0)


KERBIN = Corpo(
    nome="Kerbin",
    mu=3.5316e12,
    raio=600_000.0,
    periodo=21_549.425,
    topo=70_000.0,
    densidade=_densidade_kerbin,
    pressao=_pressao_kerbin,
    polo=(0.0, 1.0, 0.0),
)

MUN = Corpo(
    nome="Mun",
    mu=6.5138398e10,
    raio=200_000.0,
    periodo=138_984.38,
    topo=0.0,
    densidade=_sem_ar,
    pressao=_sem_ar,
    polo=(0.0, 1.0, 0.0),
)

FOGUETE_KERBIN = (
    Estagio(
        massa_inicial=20_000.0,
        combustivel=13_000.0,
        seca_solta=2_000.0,
        empuxo_vacuo=330_000.0,
        empuxo_mar=300_000.0,
        isp_vacuo=310.0,
        isp_mar=280.0,
    ),
    Estagio(
        massa_inicial=5_000.0,
        combustivel=3_800.0,
        seca_solta=1_200.0,
        empuxo_vacuo=60_000.0,
        empuxo_mar=60_000.0 * 85.0 / 345.0,
        isp_vacuo=345.0,
        isp_mar=85.0,
    ),
)

FOGUETE_MUN = (
    Estagio(
        massa_inicial=3_000.0,
        combustivel=1_800.0,
        seca_solta=1_200.0,
        empuxo_vacuo=20_000.0,
        empuxo_mar=20_000.0,
        isp_vacuo=320.0,
        isp_mar=320.0,
    ),
)

AREA_FOGUETE_KERBIN = 1.0
AREA_FOGUETE_MUN = 1.0
LATITUDE_KSC = -0.0972
LONGITUDE_KSC = -74.5575


class NaveSimulada:
    """Uma nave de mentira no referencial inercial destro do planeta, que gira por baixo dela.

    Serve aos testes e ao --demo: a mesma Guiagem comanda esta nave no lugar
    do kRPC. Física em subpassos de PASSO_FISICA s: gravidade, empuxo ao
    longo do nariz (com empuxo e Isp que mudam com a pressão), arrasto
    area·densidade·|v_sup|² contra a velocidade em relação ao ar (que gira com
    o planeta) e a massa caindo. O nariz gira para a direção pedida (pitch e
    rumo no horizonte local) a no máximo GIRO_NARIZ_MAX graus por segundo.

    A nave começa parada no chão (pousada) na latitude e longitude da base, e
    fica presa a ele, girando com o planeta, até o empuxo para cima vencer o
    peso. O motor do primeiro estágio só acende no primeiro estagiar, como no
    jogo (aceso=True começa com ele aceso). Cada estagiar seguinte larga a seca
    (e o que sobrou de combustível) do estágio de baixo e acende o próximo.

    Uso: l = nave.leitura(); nave.executar(guiagem.passo(l)); nave.avancar(dt).
    """

    def __init__(self, corpo, estagios, area, latitude, longitude, aceso=False):
        self.corpo = corpo
        self._estagios = [replace(e) for e in estagios]
        self.area = area
        self.t = 0.0
        self.indice = 0
        self.massa = self._estagios[0].massa_inicial
        self.combustivel = self._estagios[0].combustivel
        self.aceso = aceso
        self.pousada = True
        self._acelerador = 0.0
        self._pitch = 90.0
        self._rumo = 90.0

        polo = corpo.polo
        referencia = (0.0, 0.0, 1.0) if abs(polo[2]) < 0.9 else (1.0, 0.0, 0.0)
        x0 = unit(cruz(polo, referencia))
        y0 = cruz(polo, x0)
        lat, lon = math.radians(latitude), math.radians(longitude)
        direcao = soma(
            esc(math.cos(lat) * math.cos(lon), x0),
            soma(esc(math.cos(lat) * math.sin(lon), y0), esc(math.sin(lat), polo)),
        )
        self.r = esc(corpo.raio, direcao)
        self.v = esc(corpo.omega, cruz(polo, self.r))
        self.nariz = unit(self.r)

    @classmethod
    def kerbin(cls, latitude=LATITUDE_KSC, longitude=LONGITUDE_KSC, aceso=False):
        """O foguete de dois estágios no KSC."""
        return cls(KERBIN, FOGUETE_KERBIN, AREA_FOGUETE_KERBIN, latitude, longitude, aceso)

    @classmethod
    def mun(cls, latitude=0.0, longitude=0.0, aceso=False):
        """O foguete de um estágio na Mun."""
        return cls(MUN, FOGUETE_MUN, AREA_FOGUETE_MUN, latitude, longitude, aceso)

    def _base_local(self):
        cima = unit(self.r)
        leste = unit(cruz(self.corpo.polo, self.r))
        norte = cruz(cima, leste)
        return cima, norte, leste

    def _v_sup(self):
        return sub(self.v, esc(self.corpo.omega, cruz(self.corpo.polo, self.r)))

    def _direcao(self, pitch, rumo):
        """O vetor do pitch e rumo pedidos, no horizonte local de agora."""
        cima, norte, leste = self._base_local()
        p, b = math.radians(pitch), math.radians(rumo)
        plano = soma(esc(math.cos(b), norte), esc(math.sin(b), leste))
        return soma(esc(math.cos(p), plano), esc(math.sin(p), cima))

    def _apontar(self, dt):
        alvo = self._direcao(self._pitch, self._rumo)
        c = limitar(ponto(self.nariz, alvo), -1.0, 1.0)
        passo = math.radians(GIRO_NARIZ_MAX) * dt
        if math.acos(c) <= passo:
            self.nariz = alvo
            return
        perp = sub(alvo, esc(c, self.nariz))
        if norma(perp) < 1e-9:
            perp = cruz(self.nariz, (1.0, 0.0, 0.0))
            if norma(perp) < 1e-9:
                perp = cruz(self.nariz, (0.0, 1.0, 0.0))
        perp = unit(perp)
        self.nariz = soma(esc(math.cos(passo), self.nariz), esc(math.sin(passo), perp))

    def executar(self, comando):
        """Aplica o Comando: acelerador, atitude, estágio e time warp."""
        self._acelerador = limitar(comando.acelerador, 0.0, 1.0)
        self._pitch, self._rumo = comando.pitch, comando.rumo
        if comando.estagiar:
            self._estagiar()
        if comando.acelerar_ate is not None and comando.acelerar_ate > self.t:
            self._acelerar_ate(comando.acelerar_ate)

    def _estagiar(self):
        if not self.aceso:
            self.aceso = True
        elif self.indice + 1 < len(self._estagios):
            atual = self._estagios[self.indice]
            self.massa -= atual.seca_solta + max(self.combustivel, 0.0)
            self.indice += 1
            self.combustivel = self._estagios[self.indice].combustivel
            self.aceso = True

    def _acelerar_ate(self, t_fim):
        """Avança sem motor e sem ar, em passos de PASSO_WARP s, até o tempo pedido."""
        corpo = self.corpo
        self._acelerador = 0.0
        if self.pousada:
            self.r = rotacionar(self.r, corpo.polo, corpo.omega * (t_fim - self.t))
            self.v = esc(corpo.omega, cruz(corpo.polo, self.r))
            self.t = t_fim
        else:
            while self.t < t_fim:
                dt = min(PASSO_WARP, t_fim - self.t)
                a0 = esc(-corpo.mu / norma(self.r) ** 3, self.r)
                v_meio = soma(self.v, esc(dt / 2.0, a0))
                self.r = soma(self.r, esc(dt, v_meio))
                a1 = esc(-corpo.mu / norma(self.r) ** 3, self.r)
                self.v = soma(v_meio, esc(dt / 2.0, a1))
                self.t += dt
        self.nariz = self._direcao(self._pitch, self._rumo)

    def avancar(self, dt):
        """Anda dt segundos de física em subpassos de PASSO_FISICA."""
        while dt > 1e-12:
            passo = min(PASSO_FISICA, dt)
            self._subpasso(passo)
            dt -= passo

    def _subpasso(self, dt):
        corpo = self.corpo
        self._apontar(dt)
        estagio = self._estagios[self.indice]
        dist = norma(self.r)
        cima = esc(1.0 / dist, self.r)
        altura = dist - corpo.raio
        p = corpo.pressao(altura)
        acesa = self.aceso and self.combustivel > 0.0
        empuxo = self._acelerador * empuxo_em(estagio, p) if acesa else 0.0
        dm = 0.0
        if empuxo > 0.0:
            dm = min(empuxo / (isp_em(estagio, p) * G0) * dt, self.combustivel)

        if self.pousada:
            peso = self.massa * corpo.mu / dist**2
            if empuxo * ponto(self.nariz, cima) > peso:
                self.pousada = False
            else:
                self.r = rotacionar(self.r, corpo.polo, corpo.omega * dt)
                self.v = esc(corpo.omega, cruz(corpo.polo, self.r))
                self._gastar(dm, dt)
                return

        v_sup = self._v_sup()
        arrasto = esc(-self.area * corpo.densidade(altura) * norma(v_sup), v_sup)
        gravidade = esc(-corpo.mu / dist**3, self.r)
        aceleracao = soma(gravidade, esc(1.0 / self.massa, soma(esc(empuxo, self.nariz), arrasto)))
        self.v = soma(self.v, esc(dt, aceleracao))
        self.r = soma(self.r, esc(dt, self.v))
        self._gastar(dm, dt)
        if norma(self.r) <= corpo.raio:
            self.r = esc(corpo.raio, unit(self.r))
            self.v = esc(corpo.omega, cruz(corpo.polo, self.r))
            self.pousada = True

    def _gastar(self, dm, dt):
        self.massa -= dm
        self.combustivel -= dm
        self.t += dt

    def leitura(self):
        """A Leitura do estado de agora, como a NaveKrpc entregaria."""
        corpo = self.corpo
        cima, norte, leste = self._base_local()
        altura = norma(self.r) - corpo.raio
        v_sup = self._v_sup()
        densidade = corpo.densidade(altura)
        p = corpo.pressao(altura)
        estagio = self._estagios[self.indice]
        acesa = self.aceso and self.combustivel > 0.0
        v2 = ponto(v_sup, v_sup)
        return Leitura(
            t=self.t,
            r=self.r,
            v=self.v,
            v_sup=v_sup,
            norte=norte,
            leste=leste,
            nariz=self.nariz,
            radar=altura,
            q=0.5 * densidade * v2,
            pressao=p,
            arrasto=self.area * densidade * v2,
            massa=self.massa,
            empuxo=empuxo_em(estagio, p) if acesa else 0.0,
            isp=isp_em(estagio, p) if acesa else 0.0,
            apagado=self.aceso and self.combustivel <= 0.0,
            motor_abaixo=(not self.aceso) or self.indice + 1 < len(self._estagios),
            pousada=self.pousada,
        )

    def estagios(self):
        """Os trechos de verdade a partir do de agora, como a NaveKrpc.estagios() entregaria."""
        saida = []
        massa = self.massa
        for k in range(self.indice, len(self._estagios)):
            e = self._estagios[k]
            combustivel = self.combustivel if k == self.indice else e.combustivel
            saida.append(replace(e, massa_inicial=massa, combustivel=combustivel))
            massa -= combustivel + e.seca_solta
        return saida
