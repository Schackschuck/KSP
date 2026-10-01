"use strict";
var P = require("../pecas");

module.exports = function () {
  var t = P.t, L = 125, s = "", apoio = "#b9bfc5";
  s += P.group(10, 17, 105, 52, "ALVO");
  s += P.encoderArc(42, 44, 20.5) + P.encoder(42, 44, 15);
  s += t(42, 65, "GIRAR: PROCURA  ·  APERTAR: ESCOLHE", 1.8, "middle", apoio);
  s += P.metalButton(94, 39, "LIMPAR") + t(94, 56, "TIRA O ALVO", 1.8, "middle", apoio);
  s += P.group(10, 75, 54, 44, "REFERENCIA");
  s += P.rotaryReal(37, 104, ["AUTO|", "SUP|", "ORB|", "ALVO|"], 0);
  s += P.group(70, 75, 45, 44, "NAVES");
  s += P.metalButton(82, 93, "ANT", "left") + P.metalButton(103, 93, "PROX", "right");
  s += t(92.5, 114, "TROCA A NAVE", 1.8, "middle", apoio);
  return { w: L, h: L, corpo: P.panel(L, L, "NAVEGACAO", s),
    rotulo: "Navegacao, 125 por 125 mm: encoder do alvo, LIMPAR, chave rotativa da referencia da navball e ANT e PROX para trocar de nave" };
};
