// Painel do editor de manobras (modelo B), 150 x 150 mm.
// Descrição e peças em hardware/construcao.md#painel-do-editor-de-manobras.

"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, w = 150, h = 150, s = "", K = 22.5;

  // DELTA-V: três korry de eixo + encoder
  s += P.group(10, 18, 86, 79, "DELTA-V");
  s += P.korry(15.5, 24, K, K, "PRO", null, C.pro);
  s += P.korry(15.5, 48, K, K, "NRM", null, null);
  s += P.korry(15.5, 72, K, K, "RAD", null, null);
  s += P.encoderArc(70, 57, 20.5) + P.encoder(70, 57, 15);
  s += t(70, 89, "AJUSTE", 2.8);

  // PERCURSO: tempo pela órbita e troca de nó
  s += P.group(102, 18, 38, 79, "PERCURSO");
  s += t(115.5, 30, "ANTES", 2.4) + t(126.5, 30, "DEPOIS", 2.4);
  s += P.rockerReal(121, 40.5) + t(121, 55, "TEMPO", 2.8);
  s += P.metalButton(112, 74, "ANT", "left") + P.metalButton(130, 74, "PROX", "right");

  // PASSO: chave rotativa com a legenda gravada
  s += P.group(10, 103, 46, 40, "PASSO");
  s += P.rotaryReal(33, 126, ["0.1|1S", "1|10S", "10|1M", "100|10M"], 2);
  s += t(33, 141, "M/S  ·  TEMPO", 1.9, "middle", "#b9bfc5");

  // NO
  s += P.group(62, 103, 78, 40, "NO");
  s += P.korry(64.5, 112, K, K, "NOVO", null, null) +
    P.korry(89.75, 112, K, K, "APAGAR", null, null) +
    P.korry(115, 112, K, K, "CIRC", null, null);

  return P.svg(w, h, P.panel(w, h, "EDITOR DE MANOBRAS", s),
    "Painel do editor de manobras, 150 por 150 mm: korry PRO, NRM e RAD com PRO aceso, encoder de ajuste, " +
    "grupo PERCURSO com TEMPO, ANT e PROX, chave rotativa de passo e korry NOVO, APAGAR e CIRC");
};
