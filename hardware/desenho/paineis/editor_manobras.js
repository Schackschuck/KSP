"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, K = 22.5, L = 125, W = 2 * L, s = "", apoio = "#b9bfc5";
  s += P.group(10, 17, 86, 102, "DELTA-V");
  s += P.korry(15.5, 30, K, K, "PRO", null, C.pro) + P.korry(15.5, 55.5, K, K, "NRM", null, null) + P.korry(15.5, 81, K, K, "RAD", null, null);
  s += P.encoderArc(70, 64, 20.5) + P.encoder(70, 64, 15) + t(70, 96, "AJUSTE", 2.8);
  s += P.group(102, 17, 38, 102, "PERCURSO");
  s += t(115.5, 38, "ANTES", 2.4) + t(126.5, 38, "DEPOIS", 2.4);
  s += P.rockerReal(121, 49) + t(121, 64, "TEMPO", 2.8);
  s += P.metalButton(112, 86, "ANT", "left") + P.metalButton(130, 86, "PROX", "right");
  s += P.group(146, 17, 94, 47, "PASSO");
  s += P.rotaryReal(193, 45, ["0.1|1S", "1|10S", "10|1M", "100|10M"], 2);
  s += t(193, 61, "M/S  ·  TEMPO", 1.9, "middle", apoio);
  s += P.group(146, 70, 94, 49, "NO");
  s += P.metalButton(167, 89, "NOVO") + P.metalButton(193, 89, "APAGAR") + P.metalButton(219, 89, "CIRC");
  return { w: W, h: L, corpo: P.panel(W, L, "EDITOR DE MANOBRAS", s),
    rotulo: "Editor de manobras, 250 por 125 mm: korry PRO, NRM e RAD com o PRO aceso, encoder de ajuste, grupo PERCURSO, chave rotativa do passo e botoes NOVO, APAGAR e CIRC" };
};
