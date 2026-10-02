"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, K = 22.5, L = 125, s = "", nomes = ["LIQ", "OXI", "MONO", "ELET"], niveis = [7, 7, 4, 9];
  s += P.group(10, 17, 105, 37, "RESTANTE");
  nomes.forEach(function (n, i) {
    var x = 23 + i * 26;
    s += P.barra(x - 5.05, 22, niveis[i]) + t(x, 51.5, n, 2.3);
  });
  s += P.group(10, 60, 105, 59, "EVA");
  s += P.korry(38.5, 66, K, K, "JATO", null, C.green) + P.korry(64, 66, K, K, "LUZ", null, C.unlit);
  ["SAIR", "EMBARCAR", "AGARRAR", "SOLTAR"].forEach(function (n, i) { s += P.botao(25 + i * 25, 101.5, n); });
  return { w: L, h: L, corpo: P.panel(L, L, "RECURSOS E EVA", s),
    rotulo: "Recursos e EVA, 125 por 125 mm: quatro barras de 10 LEDs e os controles do kerbal fora da nave" };
};
