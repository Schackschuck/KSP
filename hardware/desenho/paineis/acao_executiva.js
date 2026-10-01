"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, K = 22.5, L = 125, s = "", apoio = "#b9bfc5";
  s += '<rect x="10" y="17" width="48" height="47" rx="1.5" fill="url(#zebra)"/>';
  s += '<rect x="14" y="21" width="40" height="39" rx="1" fill="' + C.panel + '"/>';
  s += P.botaoGrande(34, 42, 9.5, C.red) + P.capa(17, 22.5, 34, 37, C.red);
  s += t(34, 68.5, "ABORT", 2.8);
  s += P.group(10, 73, 48, 46, "STAGE");
  s += P.botaoGrande(34, 97, 9.5, "#d9dde0") + P.capa(17, 78.5, 34, 37, "#dfe6ee");
  s += P.group(63, 17, 52, 102, "SCRIPTS");
  s += P.vago(65.5, 24, "LANCAR") + P.vago(91, 24, "");
  s += P.vago(65.5, 50.5, "EXEC") + P.vago(91, 50.5, "ENCONTRO");
  s += P.korry(65.5, 77, K, K, "POUSO", null, C.green) + P.vago(91, 77, "PRECISAO");
  s += t(89, 107, "SEGURAR 5 S: LIGA", 1.8, "middle", apoio) + t(89, 111, "DE NOVO: ABORTA", 1.8, "middle", apoio);
  return { w: L, h: L, corpo: P.panel(L, L, "ACAO EXECUTIVA", s),
    rotulo: "Acao executiva, 125 por 125 mm: ABORT na faixa zebrada e STAGE, os dois com capa, e os seis korry dos scripts com o POUSO aceso" };
};
