"""Rendezvous automático: leva a nave até perto de outra nave, em órbita do mesmo planeta.

Esta parte tem as contas puras: a previsão das órbitas por Kepler (funções f e
g), a menor distância entre duas naves, o tiro que acerta uma queima para a nave
passar na mira, e a busca da queima de transferência. Tudo no referencial
inercial e destro da subida (veja subida.py).
"""

import math
from dataclasses import dataclass

from subida import G0, cruz, elementos, esc, norma, ponto, soma, sub, unit

D_MIRA = 300.0
AMOSTRAS_T1 = 24
AMOSTRAS_T1_VOLTA = 4
JANELA_MAX_VOLTAS = 15
AMOSTRAS_VOLTA = 32
ESPERA_MIN = 120.0
FOLGA_AR = 5_000.0
FOLGA_CHAO = 10_000.0

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
