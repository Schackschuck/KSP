"""O mapa da órbita na tela do tablet: os dados e as linhas MAP do protocolo.

A ponte (bridge/mfd.py) lê o jogo e monta um dicionário com o planeta, a
órbita da nave, as luas, o alvo e o primeiro nó de manobra. Aqui ele vira as
linhas MAP (docs/protocolo.md#mapa), que a página do tablet desenha em 3D.
Sem o kRPC, para testar sem o jogo; o MapaDemo faz o papel do jogo no --demo.
"""

import math
import time
import unicodedata
from collections import namedtuple

Orbita = namedtuple("Orbita", "a e inc lan arg anom")
"""Elementos de uma órbita: semieixo maior em m (negativo na hipérbole),
excentricidade, e inclinação, longitude do nó ascendente, argumento do
periastro e anomalia verdadeira em graus."""

LUAS_MAX = 4
NOME_MAX = 16
LINHA_MAX = 31


def nome_curto(texto):
    """O nome para a tela: sem acento, em maiúsculas, com _ no lugar do espaço, até 16."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    nome = "".join(c if c.isalnum() else "_" for c in sem_acento.upper().strip())
    return nome[:NOME_MAX] or "SEM_NOME"


def _decimos(graus):
    return round(graus * 10) % 3600


def _inteiro(valor):
    return "OFF" if valor is None or not math.isfinite(valor) else str(round(valor))


def _linhas_da_orbita(obj, orbita):
    return [
        f"MAP {obj} A {round(orbita.a)}",
        f"MAP {obj} E {round(orbita.e * 1_000_000)}",
        f"MAP {obj} INC {round(orbita.inc * 10)}",
        f"MAP {obj} LAN {_decimos(orbita.lan)}",
        f"MAP {obj} ARG {_decimos(orbita.arg)}",
        f"MAP {obj} ANOM {_decimos(orbita.anom)}",
    ]


def linhas_do_mapa(dados):
    """As linhas MAP de um dicionário com corpo, nave, luas, alvo e no.

    corpo: nome, raio, topo, soi (None no Sol), mu (m³/s²) e giro (graus).
    nave: Orbita. luas: lista de (nome, raio, Orbita).
    alvo: None ou nome, orbita, dmin, tmin, nmin e amin (None quando não há).
    no: None ou orbita, nanom (graus), t (s) e dv (m/s).
    """
    corpo = dados["corpo"]
    linhas = [
        f"MAP CORPO {nome_curto(corpo['nome'])}",
        f"MAP RAIO {round(corpo['raio'])}",
        f"MAP TOPO {round(corpo['topo'])}",
        f"MAP SOI {_inteiro(corpo['soi'])}",
        f"MAP MU {round(corpo['mu'] / 1e9)}",
        f"MAP GIRO {_decimos(corpo['giro'])}",
    ]
    linhas += _linhas_da_orbita("NAVE", dados["nave"])

    luas = dados["luas"][:LUAS_MAX]
    for i in range(LUAS_MAX):
        obj = f"L{i + 1}"
        if i >= len(luas):
            linhas.append(f"MAP {obj} OFF")
            continue
        nome, raio, orbita = luas[i]
        linhas += [f"MAP {obj} NOME {nome_curto(nome)}", f"MAP {obj} RAIO {round(raio)}"]
        linhas += _linhas_da_orbita(obj, orbita)

    alvo = dados["alvo"]
    if alvo is None:
        linhas.append("MAP ALVO OFF")
    else:
        linhas.append(f"MAP ALVO NOME {nome_curto(alvo['nome'])}")
        linhas += _linhas_da_orbita("ALVO", alvo["orbita"])
        linhas += [f"MAP ALVO DMIN {_inteiro(alvo['dmin'])}", f"MAP ALVO TMIN {_inteiro(alvo['tmin'])}"]
        for campo in ("nmin", "amin"):
            valor = alvo[campo]
            linhas.append(f"MAP ALVO {campo.upper()} {'OFF' if valor is None else _decimos(valor)}")

    no = dados["no"]
    if no is None:
        linhas.append("MAP NO OFF")
    else:
        linhas += _linhas_da_orbita("NO", no["orbita"])
        linhas += [
            f"MAP NO NANOM {_decimos(no['nanom'])}",
            f"MAP NO T {_inteiro(no['t'])}",
            f"MAP NO DV {_inteiro(no['dv'] * 10)}",
        ]
    return linhas


CAMPOS_ORBITA = ("A", "E", "INC", "LAN", "ARG", "ANOM")
OBJETOS = ("NAVE", "ALVO", "NO", *(f"L{i + 1}" for i in range(LUAS_MAX)))
CAMPOS_EXTRA = {
    "ALVO": {"NOME": "nome", "DMIN": "off", "TMIN": "off", "NMIN": "off", "AMIN": "off"},
    "NO": {"NANOM": "int", "T": "off", "DV": "off"},
    **{f"L{i + 1}": {"NOME": "nome", "RAIO": "int"} for i in range(LUAS_MAX)},
}
CAMPOS_CORPO = {"CORPO": "nome", "RAIO": "int", "TOPO": "int", "SOI": "off", "MU": "int", "GIRO": "int"}


def _valor_valido(tipo, valor):
    if tipo == "nome":
        return 0 < len(valor) <= NOME_MAX and all(c.isascii() and (c.isupper() or c.isdigit() or c == "_") for c in valor)
    if tipo == "off" and valor == "OFF":
        return True
    return valor.lstrip("+-").isdigit() and valor.isascii()


def linha_valida(linha):
    """Confere uma linha MAP do protocolo (a mesma conferência da página do tablet)."""
    partes = linha.split(" ")
    if len(linha) > LINHA_MAX or partes[0] != "MAP" or len(partes) not in (3, 4):
        return False
    if len(partes) == 3:
        if partes[1] in CAMPOS_CORPO:
            return _valor_valido(CAMPOS_CORPO[partes[1]], partes[2])
        return partes[1] in OBJETOS and partes[2] == "OFF"
    _, obj, campo, valor = partes
    if obj not in OBJETOS:
        return False
    if campo in CAMPOS_ORBITA:
        return _valor_valido("int", valor)
    tipo = CAMPOS_EXTRA.get(obj, {}).get(campo)
    return tipo is not None and _valor_valido(tipo, valor)


def anomalia_de(e, media):
    """A anomalia verdadeira (rad) a partir da média (rad), na elipse ou na hipérbole."""
    if e < 1:
        excentrica = media if e < 0.8 else math.pi
        for _ in range(50):
            passo = (excentrica - e * math.sin(excentrica) - media) / (1 - e * math.cos(excentrica))
            excentrica -= passo
            if abs(passo) < 1e-12:
                break
        return 2 * math.atan2(math.sqrt(1 + e) * math.sin(excentrica / 2), math.sqrt(1 - e) * math.cos(excentrica / 2))
    hiperbolica = math.asinh(media / e)
    for _ in range(50):
        passo = (e * math.sinh(hiperbolica) - hiperbolica - media) / (e * math.cosh(hiperbolica) - 1)
        hiperbolica -= passo
        if abs(passo) < 1e-12:
            break
    return 2 * math.atan2(math.sqrt(e + 1) * math.sinh(hiperbolica / 2), math.sqrt(e - 1) * math.cosh(hiperbolica / 2))


def media_de(e, verdadeira):
    """A anomalia média (rad) a partir da verdadeira (rad), na elipse ou na hipérbole."""
    if e < 1:
        excentrica = 2 * math.atan2(math.sqrt(1 - e) * math.sin(verdadeira / 2), math.sqrt(1 + e) * math.cos(verdadeira / 2))
        return excentrica - e * math.sin(excentrica)
    hiperbolica = 2 * math.atanh(math.sqrt((e - 1) / (e + 1)) * math.tan(verdadeira / 2))
    return e * math.sinh(hiperbolica) - hiperbolica


class MapaDemo:
    """Kerbin, a nave, a Mun, Minmus, uma estação como alvo e, a cada 90 s, um nó por 30 s."""

    RAIO = 600_000
    MU = 3.5316e12
    DIA = 21_549.425

    def __init__(self, inicio=None):
        self._inicio = time.monotonic() if inicio is None else inicio

    def _orbita(self, a, e, inc, lan, arg, media0, t):
        n = math.sqrt(self.MU / abs(a) ** 3)
        media = (media0 + n * t) % (2 * math.pi)
        return Orbita(a, e, inc, lan, arg, math.degrees(anomalia_de(e, media)) % 360)

    def dados(self, agora=None):
        t = (time.monotonic() if agora is None else agora) - self._inicio
        nave = self._orbita(690_000, 10_000 / 690_000, 5.0, 30.0, 60.0, 0.0, t)
        estacao = self._orbita(760_000, 9_500 / 760_000, 0.2, 10.0, 200.0, 2.0, t)
        luas = [
            ("Mun", 200_000, self._orbita(12_000_000, 0.0, 0.0, 0.0, 0.0, 1.7, t)),
            ("Minmus", 60_000, self._orbita(47_000_000, 0.0, 6.0, 78.0, 38.0, 0.9, t)),
        ]
        alvo = {
            "nome": "Estação um",
            "orbita": estacao,
            "dmin": 3_500 + 2_000 * math.sin(t / 20),
            "tmin": 900 - t % 900,
            "nmin": (nave.anom + 140) % 360,
            "amin": (estacao.anom + 120) % 360,
        }
        no = None
        if t % 90 >= 60:
            periodo = 2 * math.pi * math.sqrt(690_000 ** 3 / self.MU)
            no = {
                "orbita": Orbita(840_000, 320_000 / 1_680_000, 5.0, 30.0, 60.0, 0.0),
                "nanom": 0.0,
                "t": (360 - nave.anom) / 360 * periodo,
                "dv": 123.4,
            }
        corpo = {"nome": "Kerbin", "raio": self.RAIO, "topo": 70_000, "soi": 84_159_286, "mu": self.MU,
                 "giro": (100 + t * 360 / self.DIA) % 360}
        return {"corpo": corpo, "nave": nave, "luas": luas, "alvo": alvo, "no": no}
