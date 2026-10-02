"use strict";
var fs = require("fs");
var cor = { GND: "#3d4650", BTN: "#e5a50a", LC: "#e5484d", LB: "#2f7de1" };
var SUP = "#2b2f33", CINZA = "#9aa1a8", LADO = 12.65;
var LED_Y = 7.2, PE = 1.27, PASSO = 2.5, FILEIRA = 2.7;

function vista(ox, titulo, verso) {
  var s = '<g transform="translate(' + ox + ' 0)">';
  function pt(x, y) { return [verso ? x : -x, -y]; }
  function tx(x, y, t, cls, ancora) {
    return '<text x="' + x + '" y="' + y + '" class="' + cls + '"' + (ancora ? ' text-anchor="' + ancora + '"' : "") + ">" + t + "</text>";
  }
  function guia(x0, y0, x1) {
    return '<line x1="' + x0 + '" y1="' + y0 + '" x2="' + x1 + '" y2="' + y0 + '" stroke="#56606a" stroke-width=".15"/>';
  }
  s += tx(0, -15.5, titulo, "t", "middle");
  s += '<rect x="' + -LADO + '" y="' + -LADO + '" width="' + 2 * LADO + '" height="' + 2 * LADO + '" rx=".6" fill="' + SUP + '" stroke="#12161a" stroke-width=".3"/>';

  if (!verso) {
    [-1, 1].forEach(function (m) {
      s += '<rect x="' + (m < 0 ? -10 : 4.6) + '" y="-1.7" width="5.4" height=".8" fill="#6b747c" stroke="' + CINZA + '" stroke-width=".15"/>';
    });
    s += '<rect x="-4.25" y="-4.25" width="8.5" height="8.5" rx=".5" fill="#aab1b8" stroke="#e6e9ec" stroke-width=".25"/>';
    s += '<rect x="-1" y="-1.5" width="2" height="3" rx=".3" fill="#111" stroke="#e6e9ec" stroke-width=".15"/>';
    [-LED_Y, LED_Y].forEach(function (y) {
      var c = pt(0, y), d = 1.0, h = Math.sqrt(1.5 * 1.5 - d * d);
      s += '<path d="M' + (c[0] - d) + " " + (c[1] - h) + " A1.5 1.5 0 1 1 " + (c[0] - d) + " " + (c[1] + h) + ' Z" fill="#f4f7ff" stroke="' + CINZA + '" stroke-width=".25"/>';
    });
    s += guia(-1.6, -LED_Y, -13.4) + tx(-13.8, -LED_Y + .55, "LED CIMA", "p", "end");
    s += guia(-10, -1.3, -13.4) + tx(-13.8, -1.3 + .55, "NERVURAS", "p", "end");
    s += guia(-4.25, 2.5, -13.4) + tx(-13.8, 2.5 + .55, "CHAVE PSW 8,5", "p", "end");
    s += guia(-1.6, LED_Y, -13.4) + tx(-13.8, LED_Y + .55, "LED BAIXO", "p", "end");
    s += tx(13.6, -LED_Y - .6, "LADO CHATO DO LED", "p") + tx(13.6, -LED_Y + 1.6, "= CATODO", "p");
  } else {
    s += '<rect x="-4.25" y="-4.25" width="8.5" height="8.5" rx=".5" fill="none" stroke="#6d757d" stroke-width=".2" stroke-dasharray=".7 .5"/>';
    [-LED_Y, LED_Y].forEach(function (y) {
      var c = pt(0, y);
      s += '<circle cx="' + c[0] + '" cy="' + c[1] + '" r="1.5" fill="none" stroke="#6d757d" stroke-width=".2" stroke-dasharray=".6 .4"/>';
    });
    s += tx(0, -9.3, "CIMA", "g", "middle");

    var fiosGnd = [pt(PE, LED_Y), pt(0, FILEIRA), [0, 0], [4.3, 0], [4.3, LED_Y], pt(PE, -LED_Y), [PE, 15.5]];
    var fios = {
      GND: fiosGnd,
      BTN: [pt(PASSO, FILEIRA), [6, -FILEIRA], [6, 15.5]],
      LC: [pt(-PE, LED_Y), [-8.5, -LED_Y], [-8.5, 15.5]],
      LB: [pt(-PE, -LED_Y), [-6, LED_Y], [-6, 15.5]]
    };
    var pins = { LB: -7.75, LC: -3.25, BTN: 1.25, GND: 5.75 };
    function caminho(p, chave) {
      var d = "M" + p[0][0] + " " + p[0][1];
      for (var i = 1; i < p.length; i++) d += " L" + p[i][0] + " " + p[i][1];
      d += " L" + pins[chave] + " 24 L" + pins[chave] + " 25.5";
      return d;
    }
    Object.keys(fios).forEach(function (k) {
      var d = caminho(fios[k], k);
      s += '<path d="' + d + '" fill="none" stroke="#e6e9ec" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"/>';
    });
    Object.keys(fios).forEach(function (k) {
      var d = caminho(fios[k], k);
      s += '<path d="' + d + '" fill="none" stroke="' + cor[k] + '" stroke-width=".6" stroke-linecap="round" stroke-linejoin="round"/>';
    });

    function ilha(x, y, c) {
      var p = pt(x, y);
      return '<circle cx="' + p[0] + '" cy="' + p[1] + '" r="1.1" fill="' + c + '" stroke="' + CINZA + '" stroke-width=".2"/><circle cx="' + p[0] + '" cy="' + p[1] + '" r=".45" fill="#0d0f10"/>';
    }
    var livre = "#5b636b";
    [-PASSO, 0, PASSO].forEach(function (x) {
      var c = x === 0 ? cor.GND : (x === PASSO ? cor.BTN : livre);
      s += ilha(x, FILEIRA, c) + ilha(x, -FILEIRA, livre);
    });
    s += ilha(-PE, LED_Y, cor.LC) + ilha(PE, LED_Y, cor.GND) + ilha(-PE, -LED_Y, cor.LB) + ilha(PE, -LED_Y, cor.GND);

    s += tx(-1.4, -FILEIRA - 1.8, "COMUM", "q", "end");
    s += tx(3.4, -FILEIRA - 1.8, "BTN", "q");

    s += tx(-9.3, 14.2, "LC", "p", "end") + tx(-5.2, 14.2, "LB", "p") + tx(2.1, 14.2, "GND", "p") + tx(6.8, 14.2, "BTN", "p");

    var notas = [
      "CHAVE: SO A FILEIRA DE CIMA", "MEIO = COMUM = GND", "PONTA DIREITA (+2,5) = BTN", "",
      "CONFERIR NO MULTIMETRO:", "A PERNA QUE FECHA COM O", "MEIO SO APERTADO", "",
      "GND EMENDA O CATODO DE CIMA,", "O COMUM E O CATODO DE BAIXO", "LC E LB NOS ANODOS"
    ];
    notas.forEach(function (t, i) { if (t) s += tx(13.6, -9.5 + i * 2.2, t, "p"); });

    var ordem = ["LB", "LC", "BTN", "GND"], num = { GND: 1, BTN: 2, LC: 3, LB: 4 };
    s += '<rect x="-10.75" y="25" width="19.5" height="10" rx=".6" fill="#e8e4d5" stroke="#8a8576" stroke-width=".3"/>';
    ordem.forEach(function (k) {
      s += '<path d="M' + pins[k] + ' 24 L' + pins[k] + ' 25.5" stroke="#e6e9ec" stroke-width="1" fill="none"/>';
    });
    ordem.forEach(function (k) {
      s += '<rect x="' + (pins[k] - .8) + '" y="25" width="1.6" height="5" fill="' + cor[k] + '" stroke="#e6e9ec" stroke-width=".2"/>';
      s += tx(pins[k], 33.6, num[k], "n", "middle");
      s += tx(pins[k], 38.2, k, "p", "middle");
    });
    s += tx(10, 19.5, "RABICHO ~10 CM", "p");
    s += tx(11.5, 29, "JST-XH FEMEA 4 VIAS", "p") + tx(11.5, 31.2, "VISTO PELO LADO DOS FIOS", "p") + tx(11.5, 33.4, "DESENHO SEM ESCALA", "p");
  }
  return s + "</g>";
}

var svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="-30 -21 138 62" role="img" aria-label="Ligacao do suporte do korry: chave, LEDs e rabicho com JST-XH">' +
  '<style>.t{font:700 2.6px "B612",Arial,sans-serif;fill:var(--fg,#1a1e22)}.p{font:700 1.5px "B612",Arial,sans-serif;fill:var(--fg,#1a1e22)}.g{font:700 2px "B612",Arial,sans-serif;fill:#c8ced4}.q{font:700 1.5px "B612",Arial,sans-serif;fill:#c8ced4}.n{font:700 2px "B612",Arial,sans-serif;fill:#1a1e22}</style>' +
  vista(0, "FRENTE: O QUE SE MONTA", false) + vista(64, "VERSO: ONDE SE SOLDA", true) + "</svg>";
fs.writeFileSync(require("path").join(__dirname, "ligacao.svg"), svg);
console.log("hardware/korry/ligacao.svg");
