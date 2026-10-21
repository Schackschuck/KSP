"use strict";
var fs = require("fs");
var path = require("path");
var P = require("../pecas");

module.exports = function () {
  var C = P.C, t = P.t, L = 125, W = 2 * L, s = "", apoio = "#b9bfc5", tw = 57.6, th = 43.2, cy = 68;
  var img = "data:image/png;base64," + fs.readFileSync(path.join(__dirname, "..", "..", "..", "docs", "img", "mfd_simulador.png")).toString("base64");
  s += P.group(10, 17, 70, 46, "PILOTO AUTO");
  [["HDG", C.green], ["ALT", null], ["V/S", C.green]].forEach(function (m, i) {
    var x = 24 + i * 21;
    s += P.led5(x, 35, !!m[1], m[1] || C.green) + t(x, 46.5, m[0], 2.4);
  });
  s += t(45, 57, "LIGADO: SEGURAR O AJUSTE", 1.8, "middle", apoio);
  s += P.group(10, 69, 70, 50, "AVISOS");
  s += P.led5(20, 90, false, C.red) + t(20, 101.5, "ESTOL", 2.4, "middle", C.red);
  s += P.grade(41, 92) + P.botao(65, 90, "SILENCIAR");
  s += '<rect x="' + (W / 2 - 37) + '" y="' + (cy - 28) + '" width="74" height="56" rx="2.5" fill="#121518" stroke="#3a4046" stroke-width=".4"/>';
  s += '<rect x="' + (W / 2 - tw / 2 - .6) + '" y="' + (cy - th / 2 - .6) + '" width="' + (tw + 1.2) + '" height="' + (th + 1.2) + '" fill="#050607"/>';
  s += '<image x="' + (W / 2 - tw / 2) + '" y="' + (cy - th / 2) + '" width="' + tw + '" height="' + th + '" preserveAspectRatio="none" href="' + img + '"/>';
  s += P.group(170, 17, 70, 102, "AJUSTE");
  s += P.encoderArc(205, 56, 20.5) + P.encoder(205, 56, 15);
  s += t(205, 88, "MEXE NA PAGINA ABERTA", 2.2);
  s += t(205, 96, "GIRAR: MUDA O VALOR", 1.8, "middle", apoio) + t(205, 100.5, "APERTAR: ESCOLHE A LINHA", 1.8, "middle", apoio);
  s += t(205, 105, "SEGURAR: LIGA O MODO", 1.8, "middle", apoio);
  return { w: W, h: L, corpo: P.panel(W, L, "TELA", s),
    rotulo: "Tela multifuncao, 250 por 125 mm: a mikromedia de 2,8 polegadas no meio, as luzes do piloto automatico, o ESTOL, o alto-falante, SILENCIAR e o encoder de ajuste" };
};
