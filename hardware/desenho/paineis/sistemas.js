// Painel de sistemas de controle, 150 x 150 mm.
// Em cima os modos do SAS; embaixo os sistemas e o encoder do piloto automático, que é mexido pela tela multifunção.
// Os korry de modo acendem em azul enquanto a nave vira para o marcador e em verde quando o SAS segura nele.

"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, K = 22.5, s = "", apoio = "#b9bfc5";

  // ATITUDE: os 10 modos do SAS em pares: o modo em cima, o oposto embaixo
  s += P.group(10, 18, 130, 58, "ATITUDE");
  var cima = ["ESTAB", "PRO", "NRM", "RFORA", "ALVO"], baixo = ["MAN", "RETRO", "ANRM", "RDENTRO", "AALVO"];
  for (var i = 0; i < 5; i++) {
    var x = 12.75 + i * 25.5;
    s += P.korrySas(x, 24.5, cima[i], cima[i] === "PRO" ? C.green : null);
    s += P.korrySas(x, 50, baixo[i], null);
  }

  // SISTEMAS: a nave em cima (SAS, RCS), o avião embaixo (FBW, trava de altitude)
  s += P.group(10, 82, 53.5, 58, "SISTEMAS");
  s += P.korry(12.75, 88.5, K, K, "SAS", "SEM EC", C.green, null);
  s += P.korry(38.25, 88.5, K, K, "RCS", "SEM MP", null, null);
  s += P.korry(12.75, 114, K, K, "FBW", "DIRETA", C.green, null);
  s += P.korry(38.25, 114, K, K, "TRAVA ALT", null, C.unlit);

  // PILOTO AUTO: um encoder só, mexido pelo menu da tela; uma luz por modo
  s += P.group(69.5, 82, 70.5, 58, "PILOTO AUTO");
  s += P.encoderArc(94, 109, 18.5) + P.encoder(94, 109, 15);
  s += t(94, 131, "APERTAR: ESCOLHE", 1.9, "middle", apoio);
  s += t(94, 135, "SEGURAR: LIGA", 1.9, "middle", apoio);
  [["HDG", C.green], ["ALT", null], ["V/S", C.green]].forEach(function (m, j) {
    var y = 99 + j * 10;
    s += t(128.5, y + .9, m[0], 2.4, "end") + P.led(133, y, !!m[1], m[1] || C.green);
  });

  return P.svg(150, 150, P.panel(150, 150, "SISTEMAS DE CONTROLE", s),
    "Painel de sistemas de controle, 150 por 150 mm: dez korry de modo do SAS com o PRO aceso em verde, " +
    "korry SAS, RCS, FBW e TRAVA ALT, e o encoder do piloto automatico com as luzes HDG, ALT e V/S");
};
