"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, L = 125, s = "", apoio = "#b9bfc5";
  s += P.manche(62.5, 54, 20);
  s += P.group(14, 94, 97, 25, "MODO");
  [["VOO", true], ["CAMERA", false], ["TRANSL", false]].forEach(function (m, i) {
    var x = 33 + i * 29.5;
    s += P.led(x, 102, m[1], C.white) + t(x, 110, m[0], 2.4);
  });
  s += t(62.5, 116, "O BOTAO DO MANCHE TROCA O MODO", 1.8, "middle", apoio);
  return { w: L, h: L, corpo: P.panel(L, L, "SIDESTICK", s),
    rotulo: "Sidestick, 125 por 125 mm: joystick de 3 eixos com botao e as luzes dos modos VOO, CAMERA e TRANSL" };
};
