"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, K = 22.5, L = 125, s = "", apoio = "#b9bfc5";
  s += P.group(10, 17, 54, 102, "EMPUXO");
  s += P.alavanca(42, 30, 74, .7);
  s += P.group(70, 17, 45, 102, "RODAS E LUZES");
  s += P.korry(81.25, 26, K, K, "TREM", null, C.unlit) + P.korry(81.25, 53, K, K, "FREIOS", null, C.unlit) + P.korry(81.25, 80, K, K, "LUZES", null, C.green);
  s += t(92.5, 113, "TECLAS G, B E U", 1.8, "middle", apoio);
  return { w: L, h: L, corpo: P.panel(L, L, "ACELERADOR", s),
    rotulo: "Acelerador, 125 por 125 mm: alavanca deslizante com 60 mm de curso e os korry TREM, FREIOS e LUZES" };
};
