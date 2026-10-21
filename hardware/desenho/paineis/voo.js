"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, K = 22.5, L = 125, W = 2 * L, s = "";
  s += P.group(10, 17, 130, 58, "MODOS DO SAS");
  var cima = ["ESTAB", "PRO", "NRM", "RFORA", "ALVO"], baixo = ["MAN", "RETRO", "ANRM", "RDENTRO", "AALVO"];
  for (var i = 0; i < 5; i++) {
    var x = 12.75 + i * 25.5;
    s += P.korrySas(x, 23.5, cima[i], cima[i] === "PRO" ? C.green : null) + P.korrySas(x, 49, baixo[i], null);
  }
  s += P.group(10, 81, 130, 38, "SISTEMAS");
  s += P.korry(14.5, 88, K, K, "SAS", "SEM EC", C.green, null) + P.korry(40.5, 88, K, K, "RCS", "SEM MP", null, null);
  s += P.korry(66.5, 88, K, K, "FBW", "DIRETA", C.green, null) + P.korry(92.5, 88, K, K, "TRAVA ALT", null, C.unlit);
  return { w: W, h: L, corpo: P.panel(W, L, "VOO", s),
    rotulo: "Voo, 250 por 125 mm: os dez modos do SAS com o PRO aceso, korry SAS, RCS, FBW e TRAVA ALT" };
};
