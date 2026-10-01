"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, K = 22.5, L = 125, s = "", nomes = ["LIQ", "OXI", "MONO", "ELET"], niveis = [7, 7, 4, 9];
  s += P.group(10, 17, 105, 49, "RESTANTE");
  nomes.forEach(function (n, i) {
    var x = 23 + i * 26;
    s += P.barra(x - 5.05, 25, niveis[i]) + t(x, 59, n, 2.3);
  });
  s += P.group(10, 72, 105, 47, "EVA");
  s += P.korry(13, 81, K, K, "JATO", null, C.green) + P.korry(38.5, 81, K, K, "LUZ", null, C.unlit);
  s += P.metalButton(76, 83, "SAIR") + P.metalButton(100, 83, "EMBARCAR");
  s += P.metalButton(76, 104, "AGARRAR") + P.metalButton(100, 104, "SOLTAR");
  return { w: L, h: L, corpo: P.panel(L, L, "RECURSOS E EVA", s),
    rotulo: "Recursos e EVA, 125 por 125 mm: quatro barras de 10 LEDs e os controles do kerbal fora da nave" };
};
