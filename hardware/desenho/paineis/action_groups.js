"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, K = 22.5, L = 125, s = "", xs = [21, 41.75, 62.5, 83.25, 104];
  s += P.group(10, 17, 105, 56, "GRUPOS");
  for (var i = 0; i < 10; i++) s += P.metalButton(xs[i % 5], 30 + Math.floor(i / 5) * 24, String(i + 1));
  s += P.group(10, 79, 105, 40, "PECAS");
  s += P.korry(13, 87, K, K, " ", null, C.unlit) + t(24.25, 99.2, "PARAQUEDAS", 2.2, "middle", C.unlit);
  s += P.korry(38.5, 87, K, K, "SOLAR", null, C.green) + P.korry(64, 87, K, K, "ANTENAS", null, C.green) + P.korry(89.5, 87, K, K, "CARGA", null, C.unlit);
  return { w: L, h: L, corpo: P.panel(L, L, "ACTION GROUPS", s),
    rotulo: "Action groups, 125 por 125 mm: dez botoes de metal e os korry PARAQUEDAS, SOLAR, ANTENAS e CARGA" };
};
