"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, K = 22.5, L = 125, s = "", xs = [25, 50, 75, 100];
  s += P.group(10, 17, 105, 59, "GRUPOS");
  for (var i = 0; i < 8; i++) s += P.botao(xs[i % 4], 30 + Math.floor(i / 4) * 27.5, String(i + 1));
  s += P.group(10, 82, 105, 37, "PECAS");
  s += P.korry(13, 89, K, K, " ", null, C.unlit) + t(24.25, 101.2, "PARAQUEDAS", 2.2, "middle", C.unlit);
  s += P.korry(38.5, 89, K, K, "SOLAR", null, C.green) + P.korry(64, 89, K, K, "ANTENAS", null, C.green) + P.korry(89.5, 89, K, K, "CARGA", null, C.unlit);
  return { w: L, h: L, corpo: P.panel(L, L, "ACTION GROUPS", s),
    rotulo: "Action groups, 125 por 125 mm: oito botoes e os korry PARAQUEDAS, SOLAR, ANTENAS e CARGA" };
};
