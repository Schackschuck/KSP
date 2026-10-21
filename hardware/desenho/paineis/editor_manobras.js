"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, K = 22.5, L = 125, W = 2 * L, s = "", apoio = "#b9bfc5";
  s += P.group(10, 17, 33.5, 102, "DELTA-V");
  s += P.korry(15.5, 30, K, K, "PRO", null, C.pro) + P.korry(15.5, 55.5, K, K, "NRM", null, null) + P.korry(15.5, 81, K, K, "RAD", null, null);
  s += P.group(49.5, 17, 62, 102, "PERCURSO");
  s += t(75, 38, "ANTES", 2.4) + t(86, 38, "DEPOIS", 2.4);
  s += P.rockerReal(80.5, 49) + t(80.5, 64, "TEMPO", 2.8);
  s += P.botao(69, 86, "ANT", "left") + P.botao(92, 86, "PROX", "right");
  s += P.group(117.5, 17, 122.5, 47, "PASSO");
  s += P.rotaryReal(178.75, 45, ["0.1|1S", "1|10S", "10|1M", "100|10M"], 2);
  s += t(178.75, 61, "M/S  ·  TEMPO", 1.9, "middle", apoio);
  s += P.group(117.5, 70, 122.5, 49, "NO");
  s += P.botao(148.75, 88, "NOVO") + P.botao(178.75, 88, "APAGAR") + P.botao(208.75, 88, "CIRC");
  return { w: W, h: L, corpo: P.panel(W, L, "EDITOR DE MANOBRAS", s),
    rotulo: "Editor de manobras, 250 por 125 mm: korry PRO, NRM e RAD com o PRO aceso, grupo PERCURSO, chave rotativa do passo e botoes NOVO, APAGAR e CIRC" };
};
