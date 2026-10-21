"""Rendezvous automático: leva a nave até perto de outra nave, em órbita do mesmo planeta.

Tem as contas puras (a previsão das órbitas por Kepler, com as funções f e g, a
menor distância entre duas naves, o tiro que acerta uma queima para a nave
passar na mira e a busca da queima de transferência), a Guiagem, que decide o
acelerador e a direção do nariz a cada leitura, e a NaveOrbital, a nave de
mentira dos testes. Tudo no referencial inercial e destro da subida (veja
subida.py).

Fases
-----
 PLANO          só se o plano da nave difere do plano do alvo: queima no nó
 TRANSFERENCIA  queima planejada que põe a nave na mira, 300 m acima do alvo
 CORRECAO       refaz o tiro em frações de volta antes do encontro
 VELOCIDADE     anula a velocidade relativa no ponto de menor distância
 APROXIMA       chega perto do alvo com o motor principal, em tempo real
 ENCONTRO       fim bom
 FALHA          fim ruim, com um aviso
"""

import math
from dataclasses import dataclass

from subida import (
    ACEL_MIN,
    AVISO_ALVO,
    AVISO_COMBUSTIVEL,
    ERRO_APONTAR,
    ERRO_VIRAR,
    FALHA,
    G0,
    PLANO,
    TEMPO_FINAL,
    W_CRESCE,
    W_PROXIMO,
    acelerador_de_virada,
    angulo,
    cruz,
    direcao_no_plano,
    elementos,
    esc,
    horizontal,
    limitar,
    no_relativo,
    norma,
    ponto,
    rotacionar,
    soma,
    sub,
    tempo_de_queima,
    unit,
)

D_MIRA = 300.0
AMOSTRAS_T1 = 24
AMOSTRAS_T1_VOLTA = 4
JANELA_MAX_VOLTAS = 15
AMOSTRAS_VOLTA = 32
ESPERA_MIN = 120.0
FOLGA_AR = 5_000.0
FOLGA_CHAO = 10_000.0
D_PERTO = 3_000.0
VOLTAS_MAX = 6
TOL_PLANO = 0.05
TOL_DV = 0.1
TOL_CORRECAO = 0.3
FRACOES_CORRECAO = (0.3, 0.1)
TOL_VREL = 0.1
V_APROX_MAX = 5.0
TEMPO_APROX = 60.0
TOL_APROX = 0.3
TOL_APROX_RELATIVA = 0.1
TEMPO_MAX_APROX = 1_200.0
MARGEM_WARP = 60.0
MARGEM_COMBUSTIVEL = 0.9
RESERVA_DV = 20.0
FOLGA_ENCONTRO = 20.0
V_ENCONTRO = 0.2
FRACAO_BUSCA = 0.25
GIRO_MAX = 5.0
ERRO_GIRANDO = 20.0
GIRO_MIN = 0.1
PESO_GIRO = 0.2
FOLGA_GIRO = 10.0
PASSO_FISICA = 0.05

TRANSFERENCIA = "TRANSFERENCIA"
CORRECAO = "CORRECAO"
VELOCIDADE = "VELOCIDADE"
APROXIMA = "APROXIMA"
ENCONTRO = "ENCONTRO"

AVISO_ORBITA = "ORBITA"
AVISO_TRANSFERENCIA = "TRANSFERENCIA"
PRIORIDADE_AVISOS = (AVISO_COMBUSTIVEL, AVISO_ALVO, AVISO_ORBITA, AVISO_TRANSFERENCIA)

ITERACOES_AUREA = 30
ITERACOES_REFINO = 15
PASSADAS_REFINO = 2
ITERACOES_KEPLER = 50
ITERACOES_TIRO = 25
H_JACOBIANO = 0.01
PASSO_MAX_TIRO = 30.0
TOL_MIRA = 0.5
VOLTAS_MIN = 0.3
INTEIROS_POR_PAR = (-1, 0, 1, 2)
PASSOS_TOF_POR_VOLTA = 8
RAZAO_AUREA = (math.sqrt(5.0) - 1.0) / 2.0


@dataclass
class Estado:
    """Posição e velocidade inerciais no instante t (UT, em segundos)."""

    t: float
    r: tuple
    v: tuple


@dataclass
class Leitura:
    """O que a guiagem lê da nave em t: posição, velocidade, nariz, massa, empuxo e Isp disponíveis, combustível e o alvo (Estado em t)."""

    t: float
    r: tuple
    v: tuple
    nariz: tuple
    massa: float
    empuxo: float
    isp: float
    combustivel: float
    alvo: Estado | None


@dataclass
class Comando:
    """acelerador (0 a 1), direcao (vetor inercial para o nariz, ou None), acelerar_ate (UT ou None) e o nó a mostrar no jogo.

    no é (t, dv) (dv em vetor inercial) ou None; no_mudou é verdade no
    primeiro comando depois de o nó mudar (ou sumir).
    """

    acelerador: float = 0.0
    direcao: tuple | None = None
    acelerar_ate: float | None = None
    no: tuple | None = None
    no_mudou: bool = False


@dataclass
class Planeta:
    nome: str
    mu: float
    raio: float
    topo: float
    soi: float


@dataclass
class Transferencia:
    """A queima de transferência: dv1 (vetor) em t1, o encontro em tm com a velocidade relativa v_rel."""

    t1: float
    dv1: tuple
    tm: float
    v_rel: float
    dv_total: float
    voltas: float


def _energia_inversa(mu, r, v):
    """1/a da órbita; levanta ValueError se não é uma órbita fechada."""
    inv_a = 2.0 / norma(r) - ponto(v, v) / mu
    if inv_a <= 1e-15:
        raise ValueError("a órbita não é fechada")
    return inv_a


def propagar(mu, r, v, dt):
    """(r, v) depois de dt segundos (pode ser negativo), por Kepler, com as funções f e g.

    Resolve a equação de Kepler na anomalia excêntrica em diferença (ΔE), com
    o n·dt reduzido a menos de 2π; as voltas inteiras voltam somadas no g.
    Levanta ValueError se a órbita não é fechada (a <= 0, escape).
    """
    r0 = norma(r)
    a = 1.0 / _energia_inversa(mu, r, v)
    n = math.sqrt(mu / a**3)
    sigma0 = ponto(r, v) / math.sqrt(mu)
    raiz_a = math.sqrt(a)
    total = n * dt
    m = math.fmod(total, 2.0 * math.pi)
    voltas = total - m
    de = m
    for _ in range(ITERACOES_KEPLER):
        s, c = math.sin(de), math.cos(de)
        f = de - (1.0 - r0 / a) * s + sigma0 / raiz_a * (1.0 - c) - m
        df = 1.0 - (1.0 - r0 / a) * c + sigma0 / raiz_a * s
        passo = f / df
        de -= passo
        if abs(passo) < 1e-13:
            break
    de_total = de + voltas
    s, c = math.sin(de), math.cos(de)
    f = 1.0 - a / r0 * (1.0 - c)
    g = dt + math.sqrt(a**3 / mu) * (s - de_total)
    r_novo = soma(esc(f, r), esc(g, v))
    rn = norma(r_novo)
    fd = -math.sqrt(mu * a) / (rn * r0) * s
    gd = 1.0 - a / rn * (1.0 - c)
    v_novo = soma(esc(fd, r), esc(gd, v))
    return r_novo, v_novo


def periodo(mu, r, v):
    """Período da órbita em segundos; ValueError se não é fechada."""
    a = 1.0 / _energia_inversa(mu, r, v)
    return 2.0 * math.pi * math.sqrt(a**3 / mu)


def _aurea(f, esq, dir_, iteracoes):
    """Mínimo de f entre esq e dir_ por seção áurea; devolve o x do menor valor visto."""
    c = dir_ - RAZAO_AUREA * (dir_ - esq)
    d = esq + RAZAO_AUREA * (dir_ - esq)
    fc, fd = f(c), f(d)
    for _ in range(iteracoes):
        if fc < fd:
            dir_, d, fd = d, c, fc
            c = dir_ - RAZAO_AUREA * (dir_ - esq)
            fc = f(c)
        else:
            esq, c, fc = c, d, fd
            d = esq + RAZAO_AUREA * (dir_ - esq)
            fd = f(d)
    return (c + d) / 2.0


def menor_distancia(mu, nave, alvo, t_ini, t_fim):
    """(d, t, v_rel): a menor distância entre as duas naves em [t_ini, t_fim].

    nave e alvo são Estado, cada um no seu instante. Amostra AMOSTRAS_VOLTA
    pontos por volta da nave e refina a melhor amostra por seção áurea entre as
    vizinhas. v_rel é o módulo da velocidade relativa em t.
    """
    passo_max = periodo(mu, nave.r, nave.v) / AMOSTRAS_VOLTA
    n = max(2, math.ceil((t_fim - t_ini) / passo_max))
    h = (t_fim - t_ini) / n

    def posicoes(t):
        rn, vn = propagar(mu, nave.r, nave.v, t - nave.t)
        ra, va = propagar(mu, alvo.r, alvo.v, t - alvo.t)
        return rn, vn, ra, va

    def dist(t):
        rn, _, ra, _ = posicoes(t)
        return norma(sub(rn, ra))

    melhor_i, melhor_d = 0, math.inf
    for i in range(n + 1):
        d = dist(t_ini + i * h)
        if d < melhor_d:
            melhor_i, melhor_d = i, d
    esq = t_ini + max(melhor_i - 1, 0) * h
    dir_ = t_ini + min(melhor_i + 1, n) * h
    t = _aurea(dist, esq, dir_, ITERACOES_AUREA)
    t = min(max(t, t_ini), t_fim)
    rn, vn, ra, va = posicoes(t)
    return norma(sub(rn, ra)), t, norma(sub(vn, va))


def _resolver3(m, b):
    """Sistema 3x3 por Cramer; None se o determinante é nulo."""

    def det(a):
        return (
            a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
            - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
            + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
        )

    d = det(m)
    if abs(d) < 1e-30:
        return None
    x = []
    for j in range(3):
        mj = [[b[i] if k == j else m[i][k] for k in range(3)] for i in range(3)]
        x.append(det(mj) / d)
    return tuple(x)


def _tiro(mu, nave, t1, alvo, tm, dv0, folga):
    """(dv, v_rel) do tiro de interceptar, ou None; v_rel é o módulo em tm."""
    dt = tm - t1
    if dt <= 0.0:
        return None
    try:
        r1, v1 = propagar(mu, nave.r, nave.v, t1 - nave.t)
        r_alvo, v_alvo = propagar(mu, alvo.r, alvo.v, tm - alvo.t)
        mira = soma(r_alvo, esc(folga, unit(r_alvo)))
        dv = dv0
        for it in range(ITERACOES_TIRO + 1):
            r, v = propagar(mu, r1, soma(v1, dv), dt)
            erro = sub(r, mira)
            if norma(erro) < TOL_MIRA:
                return dv, norma(sub(v, v_alvo))
            if it == ITERACOES_TIRO:
                break
            colunas = []
            for k in range(3):
                delta = [0.0, 0.0, 0.0]
                delta[k] = H_JACOBIANO
                rk, _ = propagar(mu, r1, soma(v1, soma(dv, tuple(delta))), dt)
                colunas.append(esc(1.0 / H_JACOBIANO, sub(rk, r)))
            jacobiano = [[colunas[k][i] for k in range(3)] for i in range(3)]
            passo = _resolver3(jacobiano, esc(-1.0, erro))
            if passo is None:
                return None
            if norma(passo) > PASSO_MAX_TIRO:
                passo = esc(PASSO_MAX_TIRO / norma(passo), passo)
            dv = soma(dv, passo)
    except (ValueError, ArithmeticError):
        return None
    return None


def interceptar(mu, nave, t1, alvo, tm, dv0, folga=D_MIRA):
    """O Δv (vetor) aplicado em t1 para a nave passar em tm na mira, ou None.

    A mira é r_alvo(tm) + folga·unit(r_alvo(tm)). Newton em dv (3D), com
    jacobiano numérico (passo de 0,01 m/s) e o passo limitado a 30 m/s, até
    0,5 m da mira, em no máximo 25 iterações. dv0 é o palpite inicial. Devolve
    None se não converge, se o determinante zera ou se cai em escape.
    """
    resultado = _tiro(mu, nave, t1, alvo, tm, dv0, folga)
    return None if resultado is None else resultado[0]


def chute_tangencial(mu, r1, v1, fase, tof, voltas):
    """O Δv tangencial (vetor) que dá o período certo para alcançar o alvo, ou None.

    fase é o ângulo do alvo à frente da nave em t1, no sentido do movimento,
    em voltas. voltas são as voltas do alvo em tof mais um inteiro (tof/T_alvo
    + k): a nave precisa dar voltas + fase voltas em tof. Daí sai o período
    T_tr = tof/(voltas + fase), o semieixo e a velocidade em r1. None se não
    há solução (menos de VOLTAS_MIN voltas, ou r1 fora da órbita).
    """
    total = voltas + fase
    if total <= VOLTAS_MIN:
        return None
    t_tr = tof / total
    a_tr = (mu * (t_tr / (2.0 * math.pi)) ** 2) ** (1.0 / 3.0)
    arg = 2.0 / norma(r1) - 1.0 / a_tr
    if arg <= 0.0:
        return None
    return esc(math.sqrt(mu * arg) - norma(v1), unit(v1))


def _fase_em_voltas(r_nave, v_nave, r_alvo):
    """Ângulo do alvo à frente da nave, no sentido do movimento, em voltas (-0,5 a 0,5)."""
    h = unit(cruz(r_nave, v_nave))
    angulo = math.atan2(ponto(cruz(r_nave, r_alvo), h), ponto(r_nave, r_alvo))
    return angulo / (2.0 * math.pi)


def _periastro_minimo(planeta):
    folga = FOLGA_AR if planeta.topo > 0.0 else FOLGA_CHAO
    return planeta.raio + max(planeta.topo, 0.0) + folga


def _orbita_valida(planeta, r1, v_depois):
    """A órbita de transferência passa acima do ar e do chão e cabe na esfera de influência."""
    _, _, ra, rp = elementos(planeta, r1, v_depois)
    return rp > _periastro_minimo(planeta) and ra < planeta.soi


def planejar_transferencia(planeta, nave, alvo, agora, voltas_max):
    """A melhor Transferencia da nave até a mira sobre o alvo, ou None.

    Procura o instante da queima t1 e o tempo de voo tof; para cada par, o
    chute tangencial e o tiro dão a queima, e o custo é |dv1| + v_rel no
    encontro. O t1 cobre o período sinódico, com AMOSTRAS_T1_VOLTA amostras
    por volta; se ele passa de JANELA_MAX_VOLTAS voltas da nave, a fase quase
    não muda esperando, e o t1 cobre uma volta só. O tof vai de meia volta
    a voltas_max voltas, pulando os múltiplos inteiros do período da nave. Respeita o periastro (acima do ar mais
    FOLGA_AR, ou do chão mais FOLGA_CHAO) e a esfera de influência. O melhor
    par é refinado por seção áurea, alternando t1 e tof. ValueError se a nave
    ou o alvo não estão em órbita fechada.
    """
    mu = planeta.mu
    t_nave = periodo(mu, nave.r, nave.v)
    t_alvo = periodo(mu, alvo.r, alvo.v)
    dif = abs(1.0 / t_nave - 1.0 / t_alvo)
    sinodico = 1.0 / dif if dif > 0.0 else math.inf
    janela = sinodico if sinodico <= JANELA_MAX_VOLTAS * t_nave else t_nave
    amostras_t1 = max(AMOSTRAS_T1, math.ceil(AMOSTRAS_T1_VOLTA * janela / t_nave))
    passo_t1 = janela / amostras_t1
    t1_min = agora + ESPERA_MIN
    passo_tof = t_nave / PASSOS_TOF_POR_VOLTA
    melhor = {"custo": math.inf}

    def avaliar(t1, tof, dv0, r1, v1):
        resultado = _tiro(mu, nave, t1, alvo, t1 + tof, dv0, D_MIRA)
        if resultado is None:
            return math.inf
        dv, v_rel = resultado
        if not _orbita_valida(planeta, r1, soma(v1, dv)):
            return math.inf
        custo = norma(dv) + v_rel
        if custo < melhor["custo"]:
            melhor.update(custo=custo, t1=t1, tof=tof, dv=dv, v_rel=v_rel)
        return custo

    for i in range(amostras_t1):
        t1 = t1_min + i * passo_t1
        r1, v1 = propagar(mu, nave.r, nave.v, t1 - nave.t)
        r_alvo1, _ = propagar(mu, alvo.r, alvo.v, t1 - alvo.t)
        fase = _fase_em_voltas(r1, v1, r_alvo1)
        for j in range(PASSOS_TOF_POR_VOLTA // 2, PASSOS_TOF_POR_VOLTA * voltas_max + 1):
            if j % PASSOS_TOF_POR_VOLTA == 0:
                continue
            tof = j * passo_tof
            for k in INTEIROS_POR_PAR:
                dv0 = chute_tangencial(mu, r1, v1, fase, tof, tof / t_alvo + k)
                if dv0 is not None:
                    avaliar(t1, tof, dv0, r1, v1)

    if melhor["custo"] == math.inf:
        return None

    for _ in range(PASSADAS_REFINO):
        def custo_em_t1(t1):
            r1, v1 = propagar(mu, nave.r, nave.v, t1 - nave.t)
            return avaliar(t1, melhor["tof"], melhor["dv"], r1, v1)

        t1_ref = melhor["t1"]
        _aurea(custo_em_t1, max(t1_ref - passo_t1, t1_min), t1_ref + passo_t1, ITERACOES_REFINO)

        def custo_em_tof(tof):
            r1, v1 = propagar(mu, nave.r, nave.v, melhor["t1"] - nave.t)
            return avaliar(melhor["t1"], tof, melhor["dv"], r1, v1)

        tof_ref = melhor["tof"]
        _aurea(custo_em_tof, tof_ref - passo_tof, tof_ref + passo_tof, ITERACOES_REFINO)

    r1, v1 = propagar(mu, nave.r, nave.v, melhor["t1"] - nave.t)
    t_transferencia = periodo(mu, r1, soma(v1, melhor["dv"]))
    return Transferencia(
        t1=melhor["t1"],
        dv1=melhor["dv"],
        tm=melhor["t1"] + melhor["tof"],
        v_rel=melhor["v_rel"],
        dv_total=melhor["custo"],
        voltas=melhor["tof"] / t_transferencia,
    )


def w_no(mu, estado, t_no, v_depois):
    """O Δv que ainda falta, como o "remaining burn vector" do KSP.

    v_depois é a velocidade planejada logo depois da queima, em t_no. Vale
    antes, durante e depois de t_no: v_depois - velocidade que a nave teria em
    t_no, seguindo a órbita do estado.
    """
    _, v = propagar(mu, estado.r, estado.v, t_no - estado.t)
    return sub(v_depois, v)


def dv_disponivel(massa, combustivel, isp):
    """Δv (m/s) pela equação do foguete, gastando combustivel (mesma unidade de massa)."""
    return isp * G0 * math.log(massa / (massa - combustivel))


def _plano_do_alvo(alvo):
    return unit(cruz(alvo.r, alvo.v))


def _w_plano(r, v, n_alvo):
    """O que falta para a velocidade horizontal virar a do plano n_alvo, sem mudar de tamanho."""
    cima = unit(r)
    nova = esc(norma(horizontal(v, cima)), direcao_no_plano(n_alvo, r))
    return sub(soma(esc(ponto(v, cima), cima), nova), v)


def _dv_do_plano(r, v, teta):
    """O Δv impulsivo que gira a velocidade horizontal de teta radianos."""
    return 2.0 * norma(horizontal(v, unit(r))) * math.sin(teta / 2.0)


class Guiagem:
    """Decide o acelerador e a direção do nariz a cada leitura, do plano até o encontro.

    Não conhece o kRPC: recebe uma Leitura e devolve um Comando, de modo que os
    testes usam esta mesma guiagem com a NaveOrbital. As queimas seguem as da
    subida: a regra do acelerador, o fim por tolerância ou por |w| voltando a
    crescer, o warp até MARGEM_WARP antes, e o nariz no pró-grado até lá.

    O nariz pode virar devagar: a guiagem mede o giro de verdade e, se virar
    180° leva mais que MARGEM_WARP, para o warp mais cedo antes de cada queima e
    aproxima mais devagar, para ter tempo de virar e frear.

    Diferença da subida: nenhuma queima começa antes de o nariz estar a menos de
    ERRO_APONTAR graus da direção dela, e o motor fica em 0 enquanto o nariz
    está a mais de ERRO_VIRAR graus. Sem isso, um nariz lento queimava para o
    lado errado (a subida acende com ACEL_VIRAR, porque o gimbal só vira a nave
    com empuxo; aqui o nariz vira sozinho).

    planeta, d_final (m, a distância em que o encontro termina) e voltas_max
    (limite do tempo de voo da transferência).

    Atributos para o terminal: fase, aviso (ou None), transferencia (ou None),
    dv (o Δv gasto, sem contar os passos de mais de 1 s, que são o time warp),
    proxima_queima (UT do nó, ou None) e dv_proxima (m/s do nó, 0 sem nó).
    """

    def __init__(self, planeta, d_final, voltas_max=VOLTAS_MAX):
        self.planeta = planeta
        self.d_final = d_final
        self.voltas_max = voltas_max
        self.fase = None
        self.transferencia = None
        self.dv = 0.0
        self.acelerador = 0.0
        self.proxima_queima = None
        self.dv_proxima = 0.0
        self._avisos = set()
        self._iniciada = False
        self._t_anterior = None
        self._direcao = None
        self._giro = GIRO_MAX
        self._nariz_anterior = None
        self._no = None
        self._no_enviado = None
        self._queimando = False
        self._w_min = math.inf
        self._t_no = 0.0
        self._v_depois = (0.0, 0.0, 0.0)
        self._w_espera = (0.0, 0.0, 0.0)
        self._correcoes = None
        self._velocidade_pronta = False
        self._t_aproxima = None
        self._fases = {
            PLANO: self._fase_plano,
            TRANSFERENCIA: self._fase_transferencia,
            CORRECAO: self._fase_correcao,
            VELOCIDADE: self._fase_velocidade,
            APROXIMA: self._fase_aproxima,
            ENCONTRO: self._fase_parada,
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
        self._acumular(l)
        self._medir_giro(l)
        if not self._iniciada:
            self._iniciar(l)
        self._conferir(l)
        comando = None
        for _ in range(len(self._fases) + 1):
            comando = self._fases[self.fase](l)
            if comando is not None:
                break
        if comando is None:
            comando = self._fase_parada(l)
        if self.fase in (ENCONTRO, FALHA):
            comando.acelerador = 0.0
            self._fim_do_no()
        if comando.direcao is not None and norma(comando.direcao) > 0.0:
            self._direcao = comando.direcao
        comando.no = self._no
        comando.no_mudou = self._no != self._no_enviado
        self._no_enviado = self._no
        self.acelerador = comando.acelerador
        return comando

    def _falhar(self, aviso=None):
        if aviso is not None:
            self._avisos.add(aviso)
        self.fase = FALHA

    def _acumular(self, l):
        """Soma o Δv gasto desde a leitura anterior."""
        if self._t_anterior is not None:
            dt = l.t - self._t_anterior
            if 0.0 < dt <= 1.0 and l.massa > 0.0:
                self.dv += self.acelerador * l.empuxo / l.massa * dt
        self._t_anterior = l.t

    def _medir_giro(self, l):
        """Mede quantos graus por segundo o nariz vira de verdade, enquanto ele está longe da direção pedida."""
        anterior = self._nariz_anterior
        self._nariz_anterior = (l.t, l.nariz)
        if anterior is None or self._direcao is None:
            return
        dt = l.t - anterior[0]
        if not 0.0 < dt <= 1.0 or angulo(anterior[1], self._direcao) < ERRO_GIRANDO:
            return
        giro = angulo(anterior[1], l.nariz) / dt
        self._giro = max(GIRO_MIN, (1.0 - PESO_GIRO) * self._giro + PESO_GIRO * giro)

    def _margem(self):
        """Quanto antes da queima o warp para e o nariz começa a virar: MARGEM_WARP, ou o tempo de virar 180° com o giro medido."""
        return max(MARGEM_WARP, 180.0 / self._giro + FOLGA_GIRO)

    def _orbita_boa(self, r, v):
        """Órbita fechada, com o periastro fora do ar."""
        planeta = self.planeta
        try:
            _, _, ra, rp = elementos(planeta, r, v)
        except (ValueError, ArithmeticError):
            return False
        return math.isfinite(ra) and rp - planeta.raio > planeta.topo

    def _combustivel_basta(self, l, dv):
        """O Δv previsto mais a reserva cabe em MARGEM_COMBUSTIVEL do que sobra."""
        if l.empuxo <= 0.0 or l.isp <= 0.0 or l.combustivel <= 0.0 or l.combustivel >= l.massa:
            return False
        disponivel = dv_disponivel(l.massa, l.combustivel, l.isp)
        return dv + RESERVA_DV <= MARGEM_COMBUSTIVEL * disponivel

    def _iniciar(self, l):
        self._iniciada = True
        if l.alvo is None:
            return self._falhar(AVISO_ALVO)
        if not (self._orbita_boa(l.r, l.v) and self._orbita_boa(l.alvo.r, l.alvo.v)):
            return self._falhar(AVISO_ORBITA)
        if l.empuxo <= 0.0 or l.isp <= 0.0:
            return self._falhar(AVISO_COMBUSTIVEL)
        if norma(sub(l.alvo.r, l.r)) < D_PERTO:
            if not self._combustivel_basta(l, norma(sub(l.alvo.v, l.v))):
                return self._falhar(AVISO_COMBUSTIVEL)
            self._velocidade_pronta = True
            self._t_no = l.t
            self._w_espera = sub(l.alvo.v, l.v)
            self.fase = VELOCIDADE
            return None
        n_alvo = _plano_do_alvo(l.alvo)
        teta = math.radians(angulo(unit(cruz(l.r, l.v)), n_alvo))
        if math.degrees(teta) > TOL_PLANO:
            if not self._combustivel_basta(l, _dv_do_plano(l.r, l.v, teta)):
                return self._falhar(AVISO_COMBUSTIVEL)
            self._mostrar_no_do_plano(l, n_alvo)
            self.fase = PLANO
            return None
        return self._planejar(l)

    def _conferir(self, l):
        """Sem alvo ou sem motor no meio do voo, é FALHA."""
        if self.fase in (ENCONTRO, FALHA):
            return
        if l.alvo is None:
            self._falhar(AVISO_ALVO)
        elif l.empuxo <= 0.0 or l.isp <= 0.0:
            self._falhar(AVISO_COMBUSTIVEL)

    def _planejar(self, l):
        """Planeja a transferência a partir do estado de agora e vai para TRANSFERENCIA, ou FALHA."""
        try:
            tr = planejar_transferencia(self.planeta, Estado(l.t, l.r, l.v), l.alvo, l.t, self.voltas_max)
        except ValueError:
            return self._falhar(AVISO_ORBITA)
        if tr is None:
            return self._falhar(AVISO_TRANSFERENCIA)
        if not self._combustivel_basta(l, tr.dv_total):
            return self._falhar(AVISO_COMBUSTIVEL)
        self.transferencia = tr
        _, v1 = propagar(self.planeta.mu, l.r, l.v, tr.t1 - l.t)
        self._definir_no(tr.t1, tr.dv1, soma(v1, tr.dv1))
        self.fase = TRANSFERENCIA
        return None

    def _definir_no(self, t, dv, v_depois):
        self._t_no = t
        self._v_depois = v_depois
        self._queimando = False
        self._no = (t, dv)
        self.proxima_queima = t
        self.dv_proxima = norma(dv)

    def _fim_do_no(self):
        self._no = None
        self.proxima_queima = None
        self.dv_proxima = 0.0
        self._queimando = False

    def _comecar_a_queimar(self):
        self._queimando = True
        self._w_min = math.inf

    def _aguardar(self, l, restante, w):
        """Comando de espera antes de uma queima: warp longe, nariz no pró-grado e depois na queima."""
        margem = self._margem()
        alvo = w if restante <= margem else l.v
        comando = Comando(0.0, alvo)
        if restante > margem + 5.0:
            comando.acelerar_ate = l.t + restante - margem
        return comando

    def _esperar_ou_comecar(self, l, restante, w):
        """O Comando de espera, ou None quando a queima pode começar: chegou a hora e o nariz está apontado."""
        if restante > 0.0:
            return self._aguardar(l, restante, w)
        if angulo(l.nariz, w) > ERRO_APONTAR:
            return Comando(0.0, w)
        self._comecar_a_queimar()
        return None

    def _queimar(self, l, w, tolerancia):
        """Comando da queima em malha fechada para o vetor w, ou None quando terminou."""
        tamanho = norma(w)
        if tamanho < tolerancia:
            return None
        self._w_min = min(self._w_min, tamanho)
        if self._w_min < W_PROXIMO and tamanho > self._w_min + W_CRESCE:
            return None
        erro = angulo(l.nariz, w)
        if erro > ERRO_VIRAR:
            return Comando(0.0, w)
        pedido = tamanho * l.massa / (l.empuxo * TEMPO_FINAL)
        acelerador = min(acelerador_de_virada(erro), max(ACEL_MIN, pedido))
        return Comando(acelerador, w)

    def _fase_parada(self, l):
        return Comando(0.0, self._direcao)

    def _mostrar_no_do_plano(self, l, n_alvo):
        """O nó do plano, só para mostrar: o instante do nó relativo e o Δv de lá."""
        espera, _ = no_relativo(self.planeta, l.r, l.v, n_alvo)
        r_no, v_no = propagar(self.planeta.mu, l.r, l.v, espera)
        self._definir_no(l.t + espera, _w_plano(r_no, v_no, n_alvo), v_no)

    def _fase_plano(self, l):
        n_alvo = _plano_do_alvo(l.alvo)
        if not self._queimando:
            espera, _ = no_relativo(self.planeta, l.r, l.v, n_alvo)
            teta = math.radians(angulo(unit(cruz(l.r, l.v)), n_alvo))
            duracao = tempo_de_queima(_dv_do_plano(l.r, l.v, teta), l.massa, l.empuxo, l.isp)
            espera_ou_comeca = self._esperar_ou_comecar(l, espera - duracao / 2.0, _w_plano(l.r, l.v, n_alvo))
            if espera_ou_comeca is not None:
                return espera_ou_comeca
        comando = self._queimar(l, _w_plano(l.r, l.v, n_alvo), TOL_DV)
        if comando is None:
            self._fim_do_no()
            return self._planejar(l)
        return comando

    def _queimar_no(self, l):
        """Queima "como um nó do KSP": começa metade da duração antes de _t_no e segue o que falta até _v_depois.

        Devolve o Comando, ou None quando a queima terminou.
        """
        w = w_no(self.planeta.mu, Estado(l.t, l.r, l.v), self._t_no, self._v_depois)
        if not self._queimando:
            duracao = tempo_de_queima(norma(w), l.massa, l.empuxo, l.isp)
            espera = self._esperar_ou_comecar(l, self._t_no - l.t - duracao / 2.0, w)
            if espera is not None:
                return espera
        return self._queimar(l, w, TOL_DV)

    def _fase_transferencia(self, l):
        comando = self._queimar_no(l)
        if comando is None:
            self._fim_do_no()
            self.fase = CORRECAO
        return comando

    def _planejar_correcao(self, l, tc, tolerancia):
        """O nó da correção em tc: o tiro até a mira em tm, a partir do estado de agora. False se não vale a pena."""
        mu = self.planeta.mu
        dv0 = self._no[1] if self._no is not None else (0.0, 0.0, 0.0)
        dv = interceptar(mu, Estado(l.t, l.r, l.v), tc, l.alvo, self.transferencia.tm, dv0)
        if dv is None or norma(dv) <= tolerancia:
            return False
        _, v_c = propagar(mu, l.r, l.v, tc - l.t)
        self._definir_no(tc, dv, soma(v_c, dv))
        return True

    def _instantes_de_correcao(self, l):
        """Os instantes das correções: as de FRACOES_CORRECAO e, antes delas, uma logo depois da transferência.

        A primeira fica FRACOES_CORRECAO[0] mais voltas inteiras do alvo antes do
        encontro, onde o tiro é bem condicionado, e queima a partir de TOL_DV: o
        erro da transferência custa pouco agora e muito perto do encontro. Uma
        correção que começa atrasada (o nariz ainda virando) é refeita a partir
        do estado de agora.
        """
        tm = self.transferencia.tm
        t_alvo = periodo(self.planeta.mu, l.alvo.r, l.alvo.v)
        primeira = FRACOES_CORRECAO[0]
        voltas = math.floor((tm - l.t - self._margem()) / t_alvo - primeira)
        fracoes = ([voltas + primeira] if voltas >= 1 else []) + list(FRACOES_CORRECAO)
        return [tm - f * t_alvo for f in fracoes if tm - f * t_alvo > l.t]

    def _fase_correcao(self, l):
        if self._no is None:
            if self._correcoes is None:
                self._correcoes = self._instantes_de_correcao(l)
            while self._correcoes and self._correcoes[0] <= l.t:
                self._correcoes.pop(0)
            if not self._correcoes:
                self.fase = VELOCIDADE
                return None
            tc = self._correcoes[0]
            if tc - l.t > self._margem() + 5.0:
                return Comando(0.0, l.v, acelerar_ate=tc - self._margem())
            tolerancia = TOL_DV if len(self._correcoes) > len(FRACOES_CORRECAO) else TOL_CORRECAO
            if not self._planejar_correcao(l, tc, tolerancia):
                self._correcoes.pop(0)
                return None
        elif not self._queimando and l.t > self._t_no and not self._planejar_correcao(l, l.t, TOL_CORRECAO):
            self._fim_do_no()
            self._correcoes.pop(0)
            return None
        comando = self._queimar_no(l)
        if comando is None:
            self._fim_do_no()
            self._correcoes.pop(0)
        return comando

    def _preparar_velocidade(self, l):
        """Acha o ponto de menor distância a partir do estado de agora e o Δv de lá."""
        mu = self.planeta.mu
        estado = Estado(l.t, l.r, l.v)
        t_nave = periodo(mu, l.r, l.v)
        t_fim = max(self.transferencia.tm, l.t) + FRACAO_BUSCA * t_nave
        _, t_ma, _ = menor_distancia(mu, estado, l.alvo, l.t, t_fim)
        _, v_nave = propagar(mu, l.r, l.v, t_ma - l.t)
        _, v_alvo = propagar(mu, l.alvo.r, l.alvo.v, t_ma - l.alvo.t)
        w = sub(v_alvo, v_nave)
        self._definir_no(t_ma, w, v_alvo)
        self._w_espera = w

    def _fase_velocidade(self, l):
        if not self._velocidade_pronta:
            self._velocidade_pronta = True
            self._preparar_velocidade(l)
        if not self._queimando:
            duracao = tempo_de_queima(norma(self._w_espera), l.massa, l.empuxo, l.isp)
            espera = self._esperar_ou_comecar(l, self._t_no - l.t - duracao / 2.0, self._w_espera)
            if espera is not None:
                return espera
        comando = self._queimar(l, sub(l.alvo.v, l.v), TOL_VREL)
        if comando is None:
            self._fim_do_no()
            self.fase = APROXIMA
        return comando

    def _fase_aproxima(self, l):
        if self._t_aproxima is None:
            self._t_aproxima = l.t
        if l.t - self._t_aproxima > TEMPO_MAX_APROX:
            self._falhar()
            return None
        para_o_alvo = sub(l.alvo.r, l.r)
        distancia = norma(para_o_alvo)
        v_rel = sub(l.v, l.alvo.v)
        if distancia < self.d_final + FOLGA_ENCONTRO and norma(v_rel) < V_ENCONTRO:
            self.fase = ENCONTRO
            return None
        tempo = max(TEMPO_APROX, 1.5 * 180.0 / self._giro)
        v_des = limitar((distancia - self.d_final) / tempo, 0.0, V_APROX_MAX)
        w = sub(esc(v_des, unit(para_o_alvo)), v_rel)
        if not self._queimando:
            if norma(w) <= TOL_APROX + TOL_APROX_RELATIVA * v_des:
                return Comando(0.0, esc(-1.0, para_o_alvo))
            if angulo(l.nariz, w) > ERRO_APONTAR:
                return Comando(0.0, w)
            self._comecar_a_queimar()
        comando = self._queimar(l, w, TOL_VREL)
        if comando is None:
            self._queimando = False
            return Comando(0.0, w)
        return comando


class NaveOrbital:
    """Uma nave de mentira em órbita, no referencial inercial destro, com um alvo que anda por Kepler.

    Serve aos testes e ao --demo: a mesma Guiagem comanda esta nave no lugar do
    kRPC. A física anda em subpassos de PASSO_FISICA s (gravidade e empuxo ao
    longo do nariz, leapfrog), com a massa caindo pelo Isp. O nariz gira até a
    direção pedida a no máximo giro_max graus por segundo (GIRO_MAX, se ninguém
    mudar). fator_empuxo e fator_isp multiplicam o empuxo e o Isp de verdade, mas
    não o que a leitura entrega: simulam uma nave diferente do que a guiagem
    acha.

    O acelerar_ate pula o tempo com propagar, que é exato fora das queimas,
    como o warp nos trilhos, para a nave e para o alvo.

    Uso: l = nave.leitura(); nave.executar(guiagem.passo(l)); nave.avancar(dt).
    """

    def __init__(self, planeta, nave, alvo, massa, combustivel, empuxo, isp):
        self.planeta = planeta
        self.t = nave.t
        self.r = nave.r
        self.v = nave.v
        self.massa = massa
        self.combustivel = combustivel
        self.empuxo = empuxo
        self.isp = isp
        self.giro_max = GIRO_MAX
        self.fator_empuxo = 1.0
        self.fator_isp = 1.0
        self.nariz = unit(nave.v)
        self._alvo = alvo
        self._acelerador = 0.0
        self._direcao = self.nariz

    def alvo(self):
        """O Estado do alvo no instante de agora."""
        r, v = propagar(self.planeta.mu, self._alvo.r, self._alvo.v, self.t - self._alvo.t)
        return Estado(self.t, r, v)

    def leitura(self):
        """A Leitura do estado de agora, como a NaveKrpc entregaria."""
        com_motor = self.combustivel > 0.0
        return Leitura(
            t=self.t,
            r=self.r,
            v=self.v,
            nariz=self.nariz,
            massa=self.massa,
            empuxo=self.empuxo if com_motor else 0.0,
            isp=self.isp if com_motor else 0.0,
            combustivel=self.combustivel,
            alvo=self.alvo(),
        )

    def executar(self, comando):
        """Aplica o Comando: acelerador, direção do nariz e time warp."""
        self._acelerador = limitar(comando.acelerador, 0.0, 1.0)
        if comando.direcao is not None and norma(comando.direcao) > 0.0:
            self._direcao = comando.direcao
        if comando.acelerar_ate is not None and comando.acelerar_ate > self.t:
            self._acelerar_ate(comando.acelerar_ate)

    def _acelerar_ate(self, t_fim):
        """Avança sem motor, de uma vez, até o tempo pedido."""
        self._acelerador = 0.0
        self.r, self.v = propagar(self.planeta.mu, self.r, self.v, t_fim - self.t)
        self.t = t_fim
        self.nariz = unit(self._direcao)

    def avancar(self, dt):
        """Anda dt segundos de física em subpassos de PASSO_FISICA."""
        while dt > 1e-12:
            passo = min(PASSO_FISICA, dt)
            self._subpasso(passo)
            dt -= passo

    def _apontar(self, dt):
        alvo = unit(self._direcao)
        c = limitar(ponto(self.nariz, alvo), -1.0, 1.0)
        passo = math.radians(self.giro_max) * dt
        if math.acos(c) <= passo:
            self.nariz = alvo
            return
        eixo = unit(cruz(self.nariz, alvo))
        if norma(eixo) < 1e-9:
            eixo = unit(cruz(self.nariz, (1.0, 0.0, 0.0)))
            if norma(eixo) < 1e-9:
                eixo = unit(cruz(self.nariz, (0.0, 1.0, 0.0)))
        self.nariz = rotacionar(self.nariz, eixo, passo)

    def _gravidade(self, r):
        return esc(-self.planeta.mu / norma(r) ** 3, r)

    def _subpasso(self, dt):
        self._apontar(dt)
        empuxo = 0.0
        dm = 0.0
        if self._acelerador > 0.0 and self.combustivel > 0.0:
            empuxo = self._acelerador * self.empuxo * self.fator_empuxo
            dm = min(empuxo / (self.isp * self.fator_isp * G0) * dt, self.combustivel)
        a_empuxo = esc(empuxo / self.massa, self.nariz)
        v_meio = soma(self.v, esc(dt / 2.0, soma(self._gravidade(self.r), a_empuxo)))
        self.r = soma(self.r, esc(dt, v_meio))
        self.v = soma(v_meio, esc(dt / 2.0, soma(self._gravidade(self.r), a_empuxo)))
        self.massa -= dm
        self.combustivel -= dm
        self.t += dt
