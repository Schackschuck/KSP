"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, K = 22.5, L = 125, s = "", apoio = "#b9bfc5";
  s += P.group(10, 17, 105, 40, "TRAJE");
  s += P.korry(38.5, 25, K, K, "JATO", null, C.green) + P.korry(64, 25, K, K, "LUZ", null, C.unlit);
  s += P.group(10, 63, 105, 56, "KERBAL");
  ["SAIR", "EMBARCAR", "AGARRAR", "SOLTAR"].forEach(function (n, i) { s += P.botao(25 + i * 25, 84, n); });
  s += t(62.5, 111.5, "ANDAR E VOAR: PELO SIDESTICK", 1.8, "middle", apoio);
  return { w: L, h: L, corpo: P.panel(L, L, "EVA", s),
    rotulo: "EVA, 125 por 125 mm: korry JATO e LUZ e os botoes SAIR, EMBARCAR, AGARRAR e SOLTAR" };
};
