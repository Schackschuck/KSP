"use strict";
var fs = require("fs");
var P = 2.54, S = 12, cor = { GND: "#3d4650", BTN: "#e5a50a", LC: "#e5484d", LB: "#2f7de1" };
function X(x, esp) { return (esp ? -x : x); }
function vista(ox, titulo, verso) {
  var s = '<g transform="translate(' + ox + ' 0)">';
  s += '<text x="0" y="-15.5" text-anchor="middle" class="t">' + titulo + '</text>';
  s += '<rect x="-12.7" y="-12.7" width="25.4" height="25.4" rx=".6" fill="#2f7a3b" stroke="#1d4d25" stroke-width=".3"/>';
  for (var i = 0; i < 10; i++) for (var j = 0; j < 10; j++) {
    var x = -11.43 + i * P, y = -11.43 + j * P;
    s += '<circle cx="' + x + '" cy="' + y + '" r=".85" fill="#c9a35a"/><circle cx="' + x + '" cy="' + y + '" r=".45" fill="#1b2a1e"/>';
  }
  function pt(x, y) { return [X(x, verso), -y]; }
  function pad(x, y, c) { var p = pt(x, y); return '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="1" fill="' + c + '"/>'; }
  if (!verso) {
    var a = pt(0, -1.27);
    s += '<rect x="' + (a[0] - 3) + '" y="' + (a[1] - 3) + '" width="6" height="6" rx=".5" fill="#2b2f33" stroke="#9aa1a8" stroke-width=".25"/><circle cx="' + a[0] + '" cy="' + a[1] + '" r="1.75" fill="#111"/>';
    [[3.81, 1.27], [-3.81, 1.27], [3.81, -3.81], [-3.81, -3.81]].forEach(function (q) { s += pad(q[0], q[1], "#9aa1a8"); });
    [[6.35, "LC"], [-6.35, "LB"]].forEach(function (l) {
      var c = pt(0, l[0]);
      s += '<circle cx="' + c[0] + '" cy="' + c[1] + '" r="1.5" fill="#f4f7ff" stroke="#9aa1a8" stroke-width=".25"/>';
      s += '<line x1="' + (c[0] + 1.25) + '" y1="' + (c[1] - .9) + '" x2="' + (c[0] + 1.25) + '" y2="' + (c[1] + .9) + '" stroke="#9aa1a8" stroke-width=".3"/>';
      s += '<line x1="' + (c[0] - 1.6) + '" y1="' + c[1] + '" x2="-13.4" y2="' + c[1] + '" stroke="#56606a" stroke-width=".15"/>';
      s += '<text x="-13.8" y="' + (c[1] + .55) + '" class="p" text-anchor="end">' + (l[1] === "LC" ? "LED CIMA" : "LED BAIXO") + '</text>';
    });
    s += '<line x1="' + (a[0] - 3) + '" y1="' + a[1] + '" x2="-13.4" y2="' + a[1] + '" stroke="#56606a" stroke-width=".15"/>';
    s += '<text x="-13.8" y="' + (a[1] + .55) + '" class="p" text-anchor="end">BOTAO 6 X 6</text>';
    s += '<rect x="6.6" y="-5.6" width="4.6" height="11.2" rx=".4" fill="none" stroke="#9aa1a8" stroke-width=".25" stroke-dasharray=".8 .5"/>';
    s += '<text x="13.6" y=".55" class="p">CONECTOR</text><text x="13.6" y="2.4" class="p">NO VERSO</text>';
  } else {
    var fios = [
      ["GND", [8.89, 3.81], [1.27, 6.35]], ["GND", [1.27, 6.35], [-3.81, 1.27]], ["GND", [-3.81, 1.27], [1.27, -6.35]],
      ["BTN", [8.89, 1.27], [3.81, -3.81]],
      ["LC", [8.89, -1.27], [-1.27, 6.35]],
      ["LB", [8.89, -3.81], [-1.27, -6.35]]
    ];
    fios.forEach(function (f) {
      var a = pt(f[1][0], f[1][1]), b = pt(f[2][0], f[2][1]);
      s += '<line x1="' + a[0] + '" y1="' + a[1] + '" x2="' + b[0] + '" y2="' + b[1] + '" stroke="' + cor[f[0]] + '" stroke-width=".7" stroke-linecap="round"/>';
    });
    [[3.81, 1.27, "#9aa1a8"], [-3.81, 1.27, cor.GND], [3.81, -3.81, cor.BTN], [-3.81, -3.81, "#9aa1a8"],
     [-1.27, 6.35, cor.LC], [1.27, 6.35, cor.GND], [-1.27, -6.35, cor.LB], [1.27, -6.35, cor.GND]].forEach(function (q) { s += pad(q[0], q[1], q[2]); });
    var nomes = ["1 GND", "2 BTN", "3 LC", "4 LB"], ys = [3.81, 1.27, -1.27, -3.81], ks = ["GND", "BTN", "LC", "LB"];
    var j0 = pt(8.89, 5.2);
    s += '<rect x="' + (j0[0] - 2.9) + '" y="' + j0[1] + '" width="5.8" height="10.4" rx=".4" fill="none" stroke="#f1efe6" stroke-width=".35"/>';
    ys.forEach(function (y, k) { s += pad(8.89, y, cor[ks[k]]); var p = pt(8.89, y); s += '<line x1="' + (p[0] - 1) + '" y1="' + p[1] + '" x2="-13.4" y2="' + p[1] + '" stroke="#56606a" stroke-width=".15" stroke-dasharray=".4 .3"/><text x="-13.8" y="' + (p[1] + .55) + '" class="p" text-anchor="end">' + nomes[k] + '</text>'; });
  }
  return s + "</g>";
}
var svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-30 -21 108 37" role="img" aria-label="Plaquinha do korry em placa perfurada">' +
  '<style>.t{font:700 2.6px "B612",Arial,sans-serif;fill:var(--fg,#1a1e22)}.p{font:700 1.5px "B612",Arial,sans-serif;fill:var(--fg,#1a1e22)}</style>' +
  vista(0, "FRENTE: OS COMPONENTES", false) + vista(62, "VERSO: OS FIOS", true) + "</svg>";
fs.writeFileSync(require("path").join(__dirname, "placa_perfurada.svg"), svg);
console.log("hardware/korry/placa_perfurada.svg");
