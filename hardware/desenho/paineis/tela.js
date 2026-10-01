"use strict";
var fs = require("fs");
var path = require("path");
var P = require("../pecas");

module.exports = function () {
  var t = P.t, L = 125, W = 2 * L, s = "", x0 = (W - 164.9) / 2, y0 = L / 2 - 42.96;
  var img = "data:image/png;base64," + fs.readFileSync(path.join(__dirname, "..", "..", "..", "docs", "img", "mfd_simulador.png")).toString("base64");
  s += '<rect x="' + x0 + '" y="9" width="164.9" height="106.96" rx="2" fill="#121518" stroke="#3a4046" stroke-width=".4"/>';
  s += '<rect x="' + (W / 2 - 77.1) + '" y="' + y0 + '" width="154.21" height="85.92" fill="#050607"/>';
  s += '<image x="' + (W / 2 - 57.25) + '" y="' + y0 + '" width="114.5" height="85.92" preserveAspectRatio="none" href="' + img + '"/>';
  s += P.group(10, 17, 28, 66, "PAGINA") + P.metalButton(24, 34, "VOO") + P.metalButton(24, 62, "ORBITA");
  s += P.group(212, 17, 28, 66, "PAGINA") + P.metalButton(226, 34, "DELTA-V") + P.metalButton(226, 62, "SUBIDA");
  s += P.group(10, 89, 28, 30, "AVISOS") + P.grade(24, 104);
  s += P.group(212, 89, 28, 30, "") + P.metalButton(226, 101, "") + t(226, 115.5, "SILENCIAR", 2.4);
  return { w: W, h: L, corpo: P.panel(W, L, "", s),
    rotulo: "Tela multifuncao, 250 por 125 mm: tela de 7 polegadas no meio, dois botoes de pagina de cada lado, o alto-falante dos avisos e SILENCIAR" };
};
