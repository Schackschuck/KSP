"""Editor de nós de manobra, com os botões numa página do celular ou do PC.

É o editor da fase 4 do roteiro antes do hardware: as chaves e os botões
ainda não existem, então viram botões numa página web, e o LCD vira uma
tabela com os números do nó. A página manda as mesmas linhas que o painel
vai mandar (docs/protocolo.md#editor-de-nós-de-manobra), e toda a lógica fica
aqui. Quando o hardware chegar, a ponte lê as mesmas linhas da serial.

Controles:
- PRO, NRM, RAD e TEMPO (no painel, chaves de alavanca com mola para o
  centro): + e - mexem no Δv pró-grado, normal e radial e movem o nó ao
  longo da órbita. Segurando, repete.
- PASSO: um só para os quatro, troca o passo de todos juntos:
  0.1 / 1 / 10 / 100 m/s no Δv e 1 s / 10 s / 1 min / 10 min no tempo.
- NOVO: nó novo no próximo apoastro, depois do último nó.
- APAGAR: apaga o nó escolhido.
- CIRC: acerta o nó escolhido para deixar a órbita circular ali onde ele
  está (leve o nó ao ponto pelo TEMPO). A conta é fechada (vis-viva) e
  depois conferida com a órbita que o jogo prevê, corrigindo até sobrar
  menos de 1 mm/s.
- ANT e PROX: trocam o nó escolhido, quando há mais de um.
- MAPA (no painel, fica na seção da câmera): liga e desliga o mapa do jogo,
  para ver o nó sendo criado.
- CAM_*: giram, aproximam e trocam o foco da câmera do mapa.
  TEMPORÁRIO: no cockpit a câmera vai ser mexida pelo joystick, no modo
  CÂMERA, e estes botões saem. Ver "Câmera do mapa" em docs/manobras.md.

Uso:
    python bridge/manobras.py                  # KSP neste computador
    python bridge/manobras.py 192.168.1.10     # KSP em outro computador
    python bridge/manobras.py --porta 8001     # outra porta de rede

Depois, abra no navegador o endereço que aparece (no celular, pelo mesmo
Wi-Fi). Documentação em docs/manobras.md.
"""

import argparse
import http.server
import json
import math
import pathlib
import queue
import sys
import threading
import time

PAGINA = pathlib.Path(__file__).with_name("celular") / "manobras.html"
MAX_CORPO = 64          # bytes: uma linha do protocolo tem no máximo 31 caracteres
INTERVALO = 0.25        # s: leitura do jogo e atualização da página, 4 vezes por segundo
G0 = 9.80665            # m/s²: a gravidade que define o Isp

# ---- ajustes: PRO, NRM, RAD e TEMPO ----
PASSOS = {
    "PRO": (0.1, 1.0, 10.0, 100.0),     # m/s por clique
    "NRM": (0.1, 1.0, 10.0, 100.0),
    "RAD": (0.1, 1.0, 10.0, 100.0),
    "TEMPO": (1.0, 10.0, 60.0, 600.0),  # s por clique
}
PASSO_INICIAL = 1       # índice em PASSOS, o mesmo para os quatro: 1 m/s e 10 s
TEMPO_MINIMO = 5.0      # s: o TEMPO não leva o nó para antes disso a partir de agora

# ---- circularização ----
CIRC_TOLERANCIA = 0.001  # m/s: para de corrigir quando a correção fica menor que isso
CIRC_VOLTAS = 5          # correções no máximo, depois da conta fechada

# ---- câmera do mapa (TEMPORÁRIO: vai para o joystick) ----
CAM_GIRO = 15.0          # graus por toque, no rumo
CAM_INCLINACAO = 10.0    # graus por toque, na inclinação
CAM_ZOOM = 1.5           # fator por toque na distância

AVISO_DURA = 6.0         # s: quanto tempo a última mensagem fica na página


# ---------------------------------------------------------------------------
# Contas de órbita, sem o kRPC (testadas em tests/test_manobras.py)
# ---------------------------------------------------------------------------

def angulo_de_voo(e, anomalia):
    """Ângulo entre a velocidade e o horizonte local, em radianos.

    Positivo subindo (do periastro para o apoastro), negativo descendo."""
    return math.atan2(e * math.sin(anomalia), 1 + e * math.cos(anomalia))


def velocidade(mu, r, a):
    """Vis-viva: a velocidade a uma distância r do centro, numa órbita de
    semieixo maior a (negativo numa hipérbole)."""
    return math.sqrt(max(mu * (2 / r - 1 / a), 0.0))


def falta_para_circular(mu, r, a, e, anomalia):
    """O que falta na velocidade para a órbita ficar circular neste ponto.

    Devolve (horizontal, radial): a componente ao longo do horizonte local,
    no sentido do movimento, e a componente para fora do planeta."""
    v = velocidade(mu, r, a)
    gama = angulo_de_voo(e, anomalia)
    v_circular = math.sqrt(mu / r)
    return v_circular - v * math.cos(gama), -v * math.sin(gama)


def para_o_no(horizontal, radial, gama):
    """Passa um Δv de (horizontal, radial) para (pró-grado, radial) do nó.

    O pró-grado do nó é a velocidade de antes da queima, gama acima do
    horizonte; o radial do nó é perpendicular a ele, no plano da órbita,
    para fora do planeta."""
    c, s = math.cos(gama), math.sin(gama)
    return horizontal * c + radial * s, -horizontal * s + radial * c


def anomalia_media(e, anomalia):
    """Anomalia média a partir da verdadeira (elipse ou hipérbole)."""
    if e < 1:
        excentrica = 2 * math.atan2(
            math.sqrt(1 - e) * math.sin(anomalia / 2), math.sqrt(1 + e) * math.cos(anomalia / 2)
        )
        return excentrica - e * math.sin(excentrica)
    hiperbolica = 2 * math.atanh(math.sqrt((e - 1) / (e + 1)) * math.tan(anomalia / 2))
    return e * math.sinh(hiperbolica) - hiperbolica


def tempo_ate_anomalia(mu, a, e, de, para):
    """Segundos até a nave ir da anomalia verdadeira `de` até `para`.

    Na elipse é sempre a próxima passagem (de 0 a um período). Na hipérbole
    devolve None se o ponto já passou ou não existe (o apoastro, por exemplo)."""
    if abs(e - 1) < 1e-9:
        return None  # parábola: não acontece no jogo na prática
    if e < 1:
        n = math.sqrt(mu / a ** 3)
        return ((anomalia_media(e, para) - anomalia_media(e, de)) % (2 * math.pi)) / n
    # Na hipérbole, a anomalia vai de -limite a +limite, passando pelo periastro (0).
    de = math.atan2(math.sin(de), math.cos(de))
    para = math.atan2(math.sin(para), math.cos(para))
    limite = math.acos(-1 / e)
    if abs(para) >= limite or abs(de) >= limite:
        return None
    n = math.sqrt(mu / (-a) ** 3)
    dt = (anomalia_media(e, para) - anomalia_media(e, de)) / n
    return dt if dt >= 0 else None


def duracao_queima(dv, empuxo, isp, massa):
    """Segundos de queima para um Δv, pela equação do foguete. None sem motor."""
    if empuxo <= 0 or isp <= 0 or massa <= 0:
        return None
    ve = isp * G0
    massa_final = massa * math.exp(-dv / ve)
    return (massa - massa_final) * ve / empuxo


# ---------------------------------------------------------------------------
# Textos da página (ASCII, como no LCD)
# ---------------------------------------------------------------------------

def finito(valor):
    return valor is not None and math.isfinite(valor)


def txt_distancia(m):
    if not finito(m):
        return "--"
    if abs(m) < 10_000:
        return f"{m:,.0f} m".replace(",", " ")
    if abs(m) < 100_000_000:
        return f"{m / 1000:,.1f} km".replace(",", " ")
    return f"{m / 1e6:,.1f} Mm".replace(",", " ")


def txt_vel(v, sinal=False):
    if not finito(v):
        return "--"
    if abs(v) < 0.05:
        v = 0.0   # sem "-0.0"
    return f"{v:+.1f} m/s" if sinal else f"{v:.1f} m/s"


def txt_tempo(s):
    if not finito(s):
        return "--"
    sinal = "-" if s < 0 else ""
    s = abs(s)
    if s < 60:
        return f"{sinal}{s:.1f} s"
    s = int(round(s))
    h, resto = divmod(s, 3600)
    m, s = divmod(resto, 60)
    if h:
        return f"{sinal}{h}h {m:02d}m {s:02d}s"
    return f"{sinal}{m}m {s:02d}s"


def txt_graus(rad):
    return "--" if not finito(rad) else f"{math.degrees(rad):.2f} graus"


def txt_passo(nome, valor):
    if nome == "TEMPO":
        return txt_tempo(valor).replace(".0 s", " s")
    return f"{valor:g} m/s"


def diferenca(antes, depois, formato):
    if not (finito(antes) and finito(depois)):
        return ""
    d = depois - antes
    return ("+" if d >= 0 else "-") + formato(abs(d))


# ---------------------------------------------------------------------------
# O editor, pelo kRPC
# ---------------------------------------------------------------------------

class Editor:
    """Recebe as linhas dos controles, mexe nos nós do jogo e monta o estado
    que a página mostra. Só é usado pela volta principal (uma thread só)."""

    def __init__(self, conn):
        self._sc = conn.space_center
        self._passo = PASSO_INICIAL  # um passo só para PRO, NRM, RAD e TEMPO
        self._escolhido = None       # o nó que os ajustes mexem
        self._aviso = ""
        self._aviso_ate = 0.0
        self._foco = "NAVE"          # câmera do mapa: NAVE, NO ou PLANETA

    # ---- mensagens ----

    def avisar(self, texto):
        print(texto)
        self._aviso = texto
        self._aviso_ate = time.monotonic() + AVISO_DURA

    def comando(self, linha):
        """Uma linha dos controles: INC <nome> <passos> ou BTN <nome> 1."""
        partes = linha.split(" ")
        if len(partes) == 3 and partes[0] == "INC" and partes[1] in PASSOS:
            try:
                passos = int(partes[2])
            except ValueError:
                passos = None
            acao = None if passos is None else (lambda: self._ajustar(partes[1], passos))
        elif len(partes) == 3 and partes[0] == "BTN" and partes[2] in ("0", "1"):
            # Soltar o botão (BTN <nome> 0) não faz nada.
            acao = (lambda: self._apertar(partes[1])) if partes[2] == "1" else (lambda: None)
        else:
            acao = None
        if acao is None:
            self.avisar(f"ERR {linha}")
            return
        try:
            acao()
        except (ValueError, RuntimeError) as e:
            # Erro do kRPC: fora da cena de voo, nó apagado no jogo, etc.
            self.avisar(f"Nao deu: {e}")

    # ---- nós ----

    def _nos(self):
        return list(self._sc.active_vessel.control.nodes)

    def _escolher(self, nos):
        """Índice do nó escolhido. Se ele sumiu (apagado no jogo), fica o primeiro."""
        if self._escolhido in nos:
            return nos.index(self._escolhido)
        self._escolhido = nos[0] if nos else None
        return 0 if nos else None

    def _antes_do_no(self, nave, nos, i):
        """A órbita em que o nó i está, e desde quando: a do nó anterior, depois
        da queima dele, ou a da nave agora."""
        if i > 0:
            return nos[i - 1].orbit, nos[i - 1].ut
        return nave.orbit, self._sc.ut

    def _quando(self, orbita, desde, anomalia):
        """UT da próxima passagem pela anomalia verdadeira, ou None."""
        mu = orbita.body.gravitational_parameter
        e = orbita.eccentricity
        dt = tempo_ate_anomalia(mu, orbita.semi_major_axis, e, orbita.true_anomaly_at_ut(desde), anomalia)
        if dt is None:
            return None
        if dt < 1 and e < 1:
            dt += orbita.period   # já está em cima do ponto: vai para a próxima volta
        ut = desde + dt
        troca = orbita.time_to_soi_change
        if finito(troca) and ut > self._sc.ut + troca:
            return None           # a nave sai da esfera de influência antes
        return ut

    def _novo(self, ponto=math.pi):
        """Cria um nó depois do último, no apoastro (ou no periastro)."""
        nave = self._sc.active_vessel
        nos = self._nos()
        orbita, desde = self._antes_do_no(nave, nos, len(nos))
        ut, onde = self._quando(orbita, desde, ponto), "AP" if ponto == math.pi else "PE"
        if ut is None and ponto == math.pi:
            ut, onde = self._quando(orbita, desde, 0.0), "PE"
        if ut is None:
            ut, onde = max(desde, self._sc.ut) + 120, "daqui a 2 min"
        self._escolhido = nave.control.add_node(ut)
        self.avisar(f"No novo: {onde}")
        return self._escolhido

    def _no_escolhido(self, criar=False):
        """(nave, nós, índice) do nó escolhido; cria um se não houver e criar=True."""
        nos = self._nos()
        i = self._escolher(nos)
        if i is None:
            if not criar:
                self.avisar("Sem no: aperte NOVO")
                return None
            self._novo()
            nos = self._nos()
            i = self._escolher(nos)
        return self._sc.active_vessel, nos, i

    def _ajustar(self, nome, passos):
        achado = self._no_escolhido()
        if achado is None:
            return
        no = self._escolhido
        passo = PASSOS[nome][self._passo]
        if nome == "PRO":
            no.prograde += passos * passo
        elif nome == "NRM":
            no.normal += passos * passo
        elif nome == "RAD":
            no.radial += passos * passo
        else:
            no.ut = max(no.ut + passos * passo, self._sc.ut + TEMPO_MINIMO)

    def _apertar(self, nome):
        if nome == "PASSO":
            self._passo = (self._passo + 1) % len(PASSOS["PRO"])
            self.avisar(f"Passo: {self._txt_passo('PRO')} / {self._txt_passo('TEMPO')}")
        elif nome == "NOVO":
            self._novo()
        elif nome == "APAGAR":
            self._apagar()
        elif nome == "CIRC":
            self._circularizar()
        elif nome in ("ANT", "PROX"):
            self._trocar(-1 if nome == "ANT" else 1)
        elif nome == "MAPA":
            self._mapa()
        elif nome.startswith("CAM_"):
            self._camera(nome[4:])
        else:
            self.avisar(f"ERR BTN {nome}")

    def _apagar(self):
        achado = self._no_escolhido()
        if achado is None:
            return
        _, nos, i = achado
        nos[i].remove()
        restam = nos[:i] + nos[i + 1:]
        # Fica o que estava depois; se era o último, o de antes.
        self._escolhido = restam[min(i, len(restam) - 1)] if restam else None
        self.avisar(f"No {i + 1} apagado")

    def _trocar(self, sentido):
        nos = self._nos()
        i = self._escolher(nos)
        if i is None:
            self.avisar("Sem no: aperte NOVO")
            return
        self._escolhido = nos[(i + sentido) % len(nos)]

    def _circularizar(self):
        """Acerta o nó para a órbita ficar circular no ponto onde ele está."""
        nave, nos, i = self._no_escolhido(criar=True)
        no = self._escolhido
        orbita, _ = self._antes_do_no(nave, nos, i)
        ut = no.ut
        troca = orbita.time_to_soi_change
        if finito(troca) and ut > self._sc.ut + troca:
            self.avisar("O no esta depois da troca de SOI: sem CIRC")
            return
        corpo = orbita.body
        mu = corpo.gravitational_parameter
        e = orbita.eccentricity
        anomalia = orbita.true_anomaly_at_ut(ut)
        r = orbita.radius_at(ut)
        gama = angulo_de_voo(e, anomalia)

        # 1) Conta fechada, a partir da órbita de antes da queima.
        pro, rad = para_o_no(*falta_para_circular(mu, r, orbita.semi_major_axis, e, anomalia), gama)
        no.normal = 0.0
        no.prograde = pro
        no.radial = rad

        # 2) Confere com a órbita que o jogo prevê depois da queima e corrige o
        #    que sobrar (arredondamentos, diferenças do jogo). A correção está no
        #    horizonte local; o gama de antes a passa para o quadro do nó.
        for _ in range(CIRC_VOLTAS):
            depois = no.orbit
            falta = falta_para_circular(
                mu, depois.radius_at(ut), depois.semi_major_axis,
                depois.eccentricity, depois.true_anomaly_at_ut(ut),
            )
            d_pro, d_rad = para_o_no(*falta, gama)
            if math.hypot(d_pro, d_rad) < CIRC_TOLERANCIA:
                break
            no.prograde += d_pro
            no.radial += d_rad

        depois = no.orbit
        altitude = r - corpo.equatorial_radius
        aviso = ""
        if altitude < 0:
            aviso = " (ABAIXO DO CHAO)"
        elif corpo.has_atmosphere and altitude < corpo.atmosphere_depth:
            aviso = " (DENTRO DA ATMOSFERA)"
        self.avisar(
            f"CIRC no {i + 1}: {txt_vel(no.delta_v)}, "
            f"Ap-Pe {txt_distancia(depois.apoapsis - depois.periapsis)}{aviso}"
        )

    # ---- câmera do mapa (TEMPORÁRIO: vai para o joystick) ----

    def _mapa(self):
        cam = self._sc.camera
        if cam.mode == self._sc.CameraMode.map:
            cam.mode = self._sc.CameraMode.automatic
            self.avisar("Mapa desligado")
        else:
            cam.mode = self._sc.CameraMode.map
            self.avisar("Mapa ligado")

    def _camera(self, acao):
        cam = self._sc.camera
        if cam.mode != self._sc.CameraMode.map:
            self.avisar("Ligue o MAPA antes")
            return
        if acao in ("ESQ", "DIR"):
            cam.heading = (cam.heading + (CAM_GIRO if acao == "DIR" else -CAM_GIRO)) % 360
        elif acao in ("CIMA", "BAIXO"):
            pitch = cam.pitch + (CAM_INCLINACAO if acao == "CIMA" else -CAM_INCLINACAO)
            cam.pitch = min(max(pitch, cam.min_pitch), cam.max_pitch)
        elif acao in ("PERTO", "LONGE"):
            dist = cam.distance / CAM_ZOOM if acao == "PERTO" else cam.distance * CAM_ZOOM
            cam.distance = min(max(dist, cam.min_distance), cam.max_distance)
        elif acao == "FOCO":
            self._trocar_foco(cam)
        else:
            self.avisar(f"ERR BTN CAM_{acao}")

    def _trocar_foco(self, cam):
        """NAVE -> NO -> PLANETA -> NAVE. Pula o NO se não houver nó."""
        nave = self._sc.active_vessel
        ordem = ["NAVE", "NO", "PLANETA"]
        foco = ordem[(ordem.index(self._foco) + 1) % 3]
        if foco == "NO" and self._escolhido not in self._nos():
            foco = "PLANETA"
        if foco == "NAVE":
            cam.focussed_vessel = nave
        elif foco == "NO":
            cam.focussed_node = self._escolhido
        else:
            cam.focussed_body = nave.orbit.body
        self._foco = foco
        self.avisar(f"Foco da camera: {foco}")

    # ---- o que a página mostra ----

    def _txt_passo(self, nome):
        return txt_passo(nome, PASSOS[nome][self._passo])

    def estado(self):
        aviso = self._aviso if time.monotonic() < self._aviso_ate else ""
        passos = {nome: self._txt_passo(nome) for nome in PASSOS}
        try:
            secoes = self._secoes()
        except (ValueError, RuntimeError) as e:
            secoes = [{"titulo": "SEM NAVE", "linhas": [["Fora da cena de voo, ou o jogo nao respondeu", str(e)]]}]
        return {"passos": passos, "aviso": aviso, "secoes": secoes}

    def _secoes(self):
        sc = self._sc
        nave = sc.active_vessel
        agora = sc.ut
        nos = list(nave.control.nodes)
        i = self._escolher(nos)
        secoes = []

        if i is None:
            secoes.append({"titulo": "NO DE MANOBRA", "linhas": [["Nenhum no", "aperte NOVO ou CIRC"]]})
            orbita_antes, orbita_depois, no = nave.orbit, None, None
        else:
            no = nos[i]
            orbita_antes, _ = self._antes_do_no(nave, nos, i)
            orbita_depois = no.orbit
            secoes.append(self._secao_no(nave, no, i, len(nos), orbita_antes, agora))

        secoes.append(self._secao_orbitas(orbita_antes, orbita_depois))
        avisos = self._avisos(nave, no, orbita_depois, agora)
        if avisos:
            secoes.append({"titulo": "AVISOS", "linhas": [[a] for a in avisos]})
        secoes.append(self._secao_camera())
        return secoes

    def _secao_no(self, nave, no, i, total, orbita, agora):
        dv = no.delta_v
        empuxo = nave.available_thrust
        isp = nave.specific_impulse
        massa = nave.mass
        queima = duracao_queima(dv, empuxo, isp, massa)
        ate_no = no.ut - agora
        inicio = ate_no - queima / 2 if queima is not None else None
        anomalia = orbita.true_anomaly_at_ut(no.ut)
        graus = math.degrees(anomalia) % 360
        onde = ""
        if orbita.eccentricity > 1e-4:   # numa órbita circular AP e PE não querem dizer nada
            if min(graus, 360 - graus) < 1:
                onde = " (no PE)"
            elif abs(graus - 180) < 1:
                onde = " (no AP)"
        altitude = orbita.radius_at(no.ut) - orbita.body.equatorial_radius
        passo = {n: self._txt_passo(n) for n in PASSOS}
        linhas = [
            ["No", f"{i + 1} de {total}"],
            ["Pro-grado", txt_vel(no.prograde, True), f"passo {passo['PRO']}"],
            ["Normal", txt_vel(no.normal, True), f"passo {passo['NRM']}"],
            ["Radial", txt_vel(no.radial, True), f"passo {passo['RAD']}"],
            ["Dv total", txt_vel(dv)],
            ["Dv restante", txt_vel(no.remaining_delta_v)],
            ["No em", "T- " + txt_tempo(ate_no), f"passo {passo['TEMPO']}"],
            ["Inicio da queima", "T- " + txt_tempo(inicio), "metade da queima antes do no"],
            ["Duracao da queima", txt_tempo(queima)],
            ["Posicao", f"anomalia {graus:.1f} graus{onde}"],
            ["Altitude no no", txt_distancia(altitude)],
            ["Empuxo disponivel", f"{empuxo / 1000:.1f} kN"],
            ["Isp", f"{isp:.0f} s"],
            ["Massa", f"{massa / 1000:.2f} t"],
            ["Aceleracao", f"{empuxo / massa:.2f} m/s2" if massa > 0 else "--"],
        ]
        return {"titulo": "NO DE MANOBRA", "linhas": linhas}

    def _secao_orbitas(self, antes, depois):
        def dados(o):
            if o is None:
                return None
            escape = o.eccentricity >= 1
            troca = o.time_to_soi_change
            proxima = o.next_orbit if finito(troca) else None
            return {
                "corpo": o.body.name,
                "ap": None if escape else o.apoapsis_altitude,
                "pe": o.periapsis_altitude,
                "ap_pe": None if escape else o.apoapsis - o.periapsis,
                "e": o.eccentricity,
                "inc": o.inclination,
                "periodo": None if escape else o.period,
                "troca": troca,
                "proxima": proxima,
            }

        a, d = dados(antes), dados(depois)

        def linha(rotulo, chave, formato, com_diferenca=True):
            va = formato(a[chave])
            if d is None:
                return [rotulo, va]
            vd = formato(d[chave])
            dif = diferenca(a[chave], d[chave], formato) if com_diferenca else ""
            return [rotulo, va, vd, dif]

        linhas = [
            ["", "ANTES", "DEPOIS", "DIFERENCA"] if d else ["", "AGORA"],
            linha("Corpo", "corpo", str, False),
            linha("Apoastro", "ap", txt_distancia),
            linha("Periastro", "pe", txt_distancia),
            linha("Ap - Pe", "ap_pe", txt_distancia),
            linha("Excentricidade", "e", lambda v: "--" if not finito(v) else f"{v:.5f}"),
            linha("Inclinacao", "inc", txt_graus),
            linha("Periodo", "periodo", txt_tempo),
        ]

        def soi(x):
            if x is None or x["proxima"] is None:
                return "nao"
            p = x["proxima"]
            return f"{p.body.name} em T- {txt_tempo(x['troca'])}, Pe {txt_distancia(p.periapsis_altitude)}"

        linhas.append(["Troca de SOI", soi(a)] + ([soi(d), ""] if d else []))
        return {"titulo": "ORBITA", "linhas": linhas}

    def _avisos(self, nave, no, depois, agora):
        avisos = []
        if no is not None:
            if no.ut < agora:
                avisos.append("O no ja passou")
            if nave.available_thrust <= 0:
                avisos.append("Sem empuxo: nenhum motor ativo (a duracao da queima fica --)")
        o = depois if depois is not None else nave.orbit
        corpo = o.body
        if o.periapsis_altitude < 0:
            avisos.append(f"Periastro abaixo do chao de {corpo.name}")
        elif corpo.has_atmosphere and o.periapsis_altitude < corpo.atmosphere_depth:
            avisos.append(
                f"Periastro dentro da atmosfera de {corpo.name} ({txt_distancia(corpo.atmosphere_depth)})"
            )
        return avisos

    def _secao_camera(self):
        """TEMPORÁRIO: a câmera do mapa vai para o joystick."""
        try:
            cam = self._sc.camera
            no_mapa = cam.mode == self._sc.CameraMode.map
            linhas = [
                ["Vista", "MAPA" if no_mapa else "VOO"],
                ["Foco", self._foco if no_mapa else "--"],
                ["Distancia", txt_distancia(cam.distance) if no_mapa else "--"],
                ["Rumo / inclinacao", f"{cam.heading:.0f} / {cam.pitch:.0f} graus" if no_mapa else "--"],
            ]
        except (ValueError, RuntimeError):
            linhas = [["Vista", "camera indisponivel"]]
        return {"titulo": "CAMERA DO MAPA (temporario: vai para o joystick, modo CAMERA)", "linhas": linhas}


# ---------------------------------------------------------------------------
# Servidor da página
# ---------------------------------------------------------------------------

class Servidor:
    """Serve a página, recebe as linhas dos botões e entrega o último estado.

    O kRPC só é usado pela volta principal: as linhas esperam numa fila."""

    def __init__(self, porta):
        self.linhas = queue.Queue()
        self._estado = b"{}"
        self._trava = threading.Lock()
        self._http = http.server.ThreadingHTTPServer(("0.0.0.0", porta), _Pedido)
        self._http.daemon_threads = True
        self._http.servidor = self
        threading.Thread(target=self._http.serve_forever, daemon=True).start()

    @property
    def estado(self):
        with self._trava:
            return self._estado

    @estado.setter
    def estado(self, valor):
        corpo = json.dumps(valor).encode()
        with self._trava:
            self._estado = corpo

    def fechar(self):
        self._http.shutdown()
        self._http.server_close()


class _Pedido(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self._responder(PAGINA.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/estado":
            self._responder(self.server.servidor.estado, "application/json")
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/linha":
            self.send_error(404)
            return
        tamanho = int(self.headers.get("Content-Length", 0))
        if tamanho > MAX_CORPO:
            self.send_error(413)
            return
        linha = self.rfile.read(tamanho).decode("ascii", "replace").strip()
        if linha:
            self.server.servidor.linhas.put(linha)
        self._responder(b"", "text/plain")

    def _responder(self, corpo, tipo):
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *args):
        pass  # sem uma linha no terminal a cada atualização da página


def rodar(editor, servidor):
    """Volta principal: executa as linhas que chegaram e atualiza o estado."""
    while True:
        inicio = time.monotonic()
        while True:
            try:
                linha = servidor.linhas.get_nowait()
            except queue.Empty:
                break
            editor.comando(linha)
        servidor.estado = editor.estado()
        time.sleep(max(0.0, INTERVALO - (time.monotonic() - inicio)))


def main():
    parser = argparse.ArgumentParser(description="Editor de nos de manobra com botoes no navegador.")
    parser.add_argument(
        "address",
        nargs="?",
        default="127.0.0.1",
        help="IP do computador onde o KSP está rodando (padrão: este computador)",
    )
    parser.add_argument(
        "--porta",
        type=int,
        default=8001,
        help="porta de rede da página (padrão: 8001; a tela multifunção usa a 8000)",
    )
    args = parser.parse_args()

    # Importados aqui para os testes usarem as contas sem o kRPC e o pyserial.
    from mfd_celular import endereco_local
    from ponte import conectar_krpc

    conn = conectar_krpc(args.address)
    try:
        servidor = Servidor(args.porta)
    except OSError as e:
        sys.exit(f"Não foi possível abrir a porta {args.porta}: {e}")
    print(f"Abra no navegador: http://{endereco_local()}:{args.porta}")
    print("(no celular, pelo mesmo Wi-Fi que este computador)")
    try:
        rodar(Editor(conn), servidor)
    except KeyboardInterrupt:
        print()
    finally:
        servidor.fechar()
        conn.close()


if __name__ == "__main__":
    main()
