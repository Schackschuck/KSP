"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, K = 22.5, L = 125, s = "", apoio = "#b9bfc5";
  s += P.group(10, 17, 105, 45, "VISTA");
  s += P.korry(14, 26, K, K, "MAPA", null, C.unlit) + P.korryComCapa(45, 26, "IVA");
  s += P.botao(94, 36, "MODO CAM") + t(94, 55.5, "AUTO, LIVRE, ORBITAL...", 1.8, "middle", apoio);
  s += P.group(10, 68, 105, 51, "IMAGEM");
  s += P.botao(40, 88, "FOTO") + P.botao(85, 88, "ESCONDER");
  s += t(85, 108, "A INTERFACE DO JOGO", 1.8, "middle", apoio);
  return { w: L, h: L, corpo: P.panel(L, L, "CAMERA", s),
    rotulo: "Camera, 125 por 125 mm: korry MAPA, korry IVA com capa, MODO CAM, FOTO e ESCONDER" };
};
