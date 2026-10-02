"use strict";
var P = require("../pecas");

module.exports = function () {
  var t = P.t, K = 22.5, L = 125, s = "";
  s += P.group(10, 17, 105, 40, "ACELERAR");
  s += t(21.5, 27, "MENOS", 2.4) + t(32.5, 27, "MAIS", 2.4);
  s += P.rockerReal(27, 37) + t(27, 51, "WARP", 2.8);
  s += P.botao(50.5, 36, "PARAR");
  s += P.korry(63.5, 24.75, K, K, "FISICO", null, null);
  s += P.botao(99, 36, "ATE O NO");
  s += P.group(10, 63, 105, 56, "JOGO");
  s += P.botao(24, 83, "PAUSA") + P.botao(47, 83, "SALVAR");
  s += P.botao(72, 83, "") + P.capaMissil(72, 69) + P.botao(99, 83, "") + P.capaMissil(99, 69);
  s += t(72, 114.5, "CARREGAR", 2.2) + t(99, 114.5, "REVERTER", 2.2);
  return { w: L, h: L, corpo: P.panel(L, L, "TEMPO", s),
    rotulo: "Tempo, 125 por 125 mm: tecla do WARP, PARAR, korry FISICO, ATE O NO, PAUSA, SALVAR, e CARREGAR e REVERTER com capa" };
};
