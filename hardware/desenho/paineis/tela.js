"use strict";
var fs = require("fs");
var path = require("path");
var P = require("../pecas");

module.exports = function () {
  var L = 125, W = 2 * L, s = "", tw = 180.9, th = 113.1, iw = th * 4 / 3, bw = 212.8, bh = 125.6;
  var img = "data:image/png;base64," + fs.readFileSync(path.join(__dirname, "..", "..", "..", "docs", "img", "mfd_celular.png")).toString("base64");
  s += '<rect x="' + (W - bw) / 2 + '" y="' + (L - bh) / 2 + '" width="' + bw + '" height="' + bh + '" rx="6" fill="none" stroke="#5b6168" stroke-width=".3" stroke-dasharray="1.5 1.2"/>';
  s += '<rect x="' + ((W - tw) / 2 - .8) + '" y="' + ((L - th) / 2 - .8) + '" width="' + (tw + 1.6) + '" height="' + (th + 1.6) + '" rx="1.2" fill="#0b0d0f" stroke="#3a4046" stroke-width=".4"/>';
  s += '<rect x="' + (W - tw) / 2 + '" y="' + (L - th) / 2 + '" width="' + tw + '" height="' + th + '" fill="#050607"/>';
  s += '<image x="' + (W - iw) / 2 + '" y="' + (L - th) / 2 + '" width="' + iw + '" height="' + th + '" preserveAspectRatio="none" href="' + img + '"/>';
  return { w: W, h: L, corpo: P.panel(W, L, "", s),
    rotulo: "Tela multifuncao, 250 por 125 mm: o tablet Galaxy Tab S 8.4 atras de uma janela de 181 por 113 mm, com o contorno do tablet tracejado" };
};
