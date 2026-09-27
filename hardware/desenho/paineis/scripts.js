// Painel de scripts, 150 x 150 mm: os scripts de voo em faixas, na ordem do voo.
// Descrição e peças em hardware/construcao.md#painel-de-scripts.

"use strict";
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, K = 22.5, s = "", apoio = "#b9bfc5", fantasma = "#3d444b";

  // Vago: tampa lisa; em cinza bem escuro, o script que o roteiro prevê ali.
  function vago(x, y, nome) {
    return P.korry(x, y, K, K, " ", null, C.unlit) + t(x + K / 2, y + K / 2 + 1, nome, 2.3, "middle", fantasma);
  }
  function faixa(y, nome, legenda) {
    return P.group(10, y, 130, 36, nome) + t(129, y + 12, legenda, 2.2, "end", apoio);
  }

  // De cima para baixo, como a nave: subida, órbita, descida. Os korry à
  // esquerda, perto da mão; à direita, o que a faixa faz.
  s += faixa(18, "SUBIDA", "DO CHAO ATE A ORBITA");
  s += vago(16, 24.75, "LANCAR") + vago(41.5, 24.75, "");
  s += faixa(60, "ORBITA", "NOS DE MANOBRA E ENCONTRO");
  s += vago(16, 66.75, "EXEC") + vago(41.5, 66.75, "ENCONTRO");
  s += faixa(102, "DESCIDA", "DA ORBITA ATE O CHAO");
  s += P.korry(16, 108.75, K, K, "POUSO", null, C.green) + vago(41.5, 108.75, "PRECISAO");
  s += t(129, 128, "SEGURAR 5 S: LIGA", 1.9, "end", apoio) + t(129, 132, "DE NOVO: ABORTA", 1.9, "end", apoio);

  return P.svg(150, 150, P.panel(150, 150, "SCRIPTS", s),
    "Painel de scripts: tres faixas na ordem do voo, subida, orbita e descida, com o korry POUSO aceso embaixo e cinco korry vagos");
};
