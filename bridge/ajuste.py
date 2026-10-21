"""O encoder AJUSTE, num Uno à parte, e a regra de para onde o giro e o aperto vão.

O Uno (firmware/encoder/encoder.ino) manda ENC AJUSTE <cliques> e BTN AJUSTE
<0|1>. A ponte da tela traduz essas linhas para as da página aberta: na SUBIDA
o encoder é o do menu da subida (SUB), em qualquer outra página é o do piloto
automático (AP).
"""

import time

import serial

from ponte import Painel

REABRIR = 5.0


def destino(pagina):
    """O encoder da página: "SUB" na SUBIDA, "AP" em qualquer outra."""
    return "SUB" if pagina == "SUBIDA" else "AP"


class Ajuste:
    """Traduz as linhas do Uno (ENC AJUSTE, BTN AJUSTE) para as da página aberta."""

    def __init__(self):
        self._aperto = None

    def traduzir(self, linha, pagina):
        """A linha para o painel de sistemas, ou None se não for do AJUSTE.

        O aperto e a soltura vão para o mesmo destino, mesmo que a página
        mude entre os dois (o aperto longo do piloto dura 1 s).
        """
        partes = linha.split()
        if len(partes) != 3 or partes[1] != "AJUSTE":
            return None
        tipo, _, valor = partes
        if tipo == "ENC":
            try:
                cliques = int(valor)
            except ValueError:
                return None
            return f"ENC {destino(pagina)} {cliques}"
        if tipo == "BTN" and valor == "1":
            self._aperto = destino(pagina)
            return f"BTN {self._aperto} 1"
        if tipo == "BTN" and valor == "0":
            alvo = self._aperto or destino(pagina)
            self._aperto = None
            return f"BTN {alvo} 0"
        return None


class EncoderSerial:
    """O Uno do encoder numa porta serial.

    Se a porta cair ou não abrir, tenta de novo a cada REABRIR s, sem parar a
    ponte.
    """

    def __init__(self, porta, abrir=None, relogio=time.monotonic):
        self._porta_nome = porta
        self._abrir_porta = abrir or Painel
        self._relogio = relogio
        self._porta = None
        self._proxima = 0.0
        self._avisou = False
        self._abrir()

    def _abrir(self):
        try:
            self._porta = self._abrir_porta(self._porta_nome)
        except (serial.SerialException, OSError) as e:
            self._porta = None
            self._proxima = self._relogio() + REABRIR
            if not self._avisou:
                print(
                    f"Não foi possível abrir o encoder em {self._porta_nome}: {e}. "
                    f"Tentando de novo a cada {REABRIR:g} s."
                )
                self._avisou = True
            return
        self._avisou = False
        print(f"Encoder AJUSTE em {self._porta_nome}.")

    def linhas(self):
        """As linhas que chegaram do Uno; vazio se a porta não está aberta."""
        if self._porta is None:
            if self._relogio() >= self._proxima:
                self._abrir()
            if self._porta is None:
                return []
        try:
            return self._porta.linhas()
        except (serial.SerialException, OSError):
            print(f"O encoder foi desconectado. Tentando de novo a cada {REABRIR:g} s.")
            self._fechar_porta()
            self._proxima = self._relogio() + REABRIR
            self._avisou = True
            return []

    def _fechar_porta(self):
        porta, self._porta = self._porta, None
        if porta is not None:
            try:
                porta.fechar()
            except (serial.SerialException, OSError):
                pass

    def fechar(self):
        self._proxima = float("inf")
        self._fechar_porta()
