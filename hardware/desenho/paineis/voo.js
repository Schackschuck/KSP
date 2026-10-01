"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, K = 22.5, L = 125, W = 2 * L, s = "", apoio = "#b9bfc5";
  s += P.group(10, 17, 130, 58, "MODOS DO SAS");
  var cima = ["ESTAB", "PRO", "NRM", "RFORA", "ALVO"], baixo = ["MAN", "RETRO", "ANRM", "RDENTRO", "AALVO"];
  for (var i = 0; i < 5; i++) {
    var x = 12.75 + i * 25.5;
    s += P.korrySas(x, 23.5, cima[i], cima[i] === "PRO" ? C.green : null) + P.korrySas(x, 49, baixo[i], null);
  }
  s += P.group(10, 81, 130, 38, "SISTEMAS");
  s += P.korry(14.5, 88, K, K, "SAS", "SEM EC", C.green, null) + P.korry(40.5, 88, K, K, "RCS", "SEM MP", null, null);
  s += P.korry(66.5, 88, K, K, "FBW", "DIRETA", C.green, null) + P.korry(92.5, 88, K, K, "TRAVA ALT", null, C.unlit);
  s += P.group(146, 17, 94, 102, "PILOTO AUTO");
  s += P.encoderArc(182, 64, 20.5) + P.encoder(182, 64, 15);
  s += t(182, 92, "APERTAR: ESCOLHE", 1.9, "middle", apoio) + t(182, 96, "SEGURAR: LIGA", 1.9, "middle", apoio);
  [["HDG", C.green], ["ALT", null], ["V/S", C.green]].forEach(function (m, j) {
    var y = 44 + j * 10;
    s += t(229, y + .9, m[0], 2.4, "end") + P.led(234, y, !!m[1], m[1] || C.green);
  });
  s += '<line x1="218" y1="78" x2="238" y2="78" stroke="' + apoio + '" stroke-width=".25"/>';
  s += t(229, 85.4, "ESTOL", 2.4, "end", C.red) + P.led(234, 84.5, false, C.red);
  s += t(193, 112, "VALORES NA PAGINA PILOTO DA TELA", 1.9, "middle", apoio);
  return { w: W, h: L, corpo: P.panel(W, L, "VOO", s),
    rotulo: "Voo, 250 por 125 mm: os dez modos do SAS com o PRO aceso, korry SAS, RCS, FBW e TRAVA ALT, e o encoder do piloto automatico com as luzes HDG, ALT, V/S e ESTOL" };
};
