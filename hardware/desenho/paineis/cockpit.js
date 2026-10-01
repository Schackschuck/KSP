"use strict";
var P = require("../pecas");

var L = 125, F = 8;
var lugar = {
  action_groups: [0, 0], recursos_eva: [0, 1], acelerador: [0, 2],
  navegacao: [1, 0], tela: [2, 0], editor_manobras: [4, 0],
  acao_executiva: [1, 1], voo: [2, 1], tempo: [4, 1], camera: [5, 1], sidestick: [5, 2]
};

module.exports = function () {
  var W = 6 * L + 2 * F, H = 3 * L + 2 * F, x0 = 2 * F + L, x1 = 5 * L, yb = 2 * F + 2 * L, s = "";
  s += '<polygon points="0,0 ' + W + ',0 ' + W + ',' + H + ' ' + x1 + ',' + H + ' ' + x1 + ',' + yb + ' ' + x0 + ',' + yb + ' ' + x0 + ',' + H + ' 0,' + H +
    '" fill="#1e2226" stroke="#0d0f11" stroke-width="1.2" stroke-linejoin="round"/>';
  Object.keys(lugar).forEach(function (nome) {
    var p = require("./" + nome)();
    s += '<g transform="translate(' + (F + lugar[nome][0] * L) + " " + (F + lugar[nome][1] * L) + ')">' + p.corpo + "</g>";
  });
  s += '<text class="dimtext" x="' + ((x0 + x1) / 2) + '" y="' + (yb + (H - yb) / 2) + '" text-anchor="middle" style="font-size:6px">ABERTO · ' + (x1 - x0) + " MM</text>";
  return { w: W, h: H, corpo: s, rotulo: "Cockpit completo, 766 por 391 mm, em U: a tela e o voo no meio, o acelerador embaixo a esquerda e o sidestick embaixo a direita" };
};
