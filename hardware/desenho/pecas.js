// Peças do painel desenhadas em SVG, no tamanho real (unidades em mm).
// Cada função devolve um pedaço de SVG em texto. A identidade visual
// (cores, fontes, medidas) está em hardware/identidade_visual.md.
//
// Peças no tamanho de catálogo, para os painéis novos:
//   korry(x, y, 22.5, 22.5, cima, baixo, corCima, corBaixo)  korry de 22,5 mm
//   encoder(x, y, 15) + encoderArc(x, y, 20.5)             encoder com knob de 30 mm
//   rotaryReal(x, y, legendas, posicao)                    chave rotativa, knob de 22 mm
//   rockerReal(x, y)                                       tecla basculante deitada, 21 x 15 mm
//   metalButton(x, y, legenda, seta)                       botão de metal de 12 mm
//   korrySas(x, y, modo, cor)                              korry de 22,5 mm com o ícone de um modo do SAS
//   guardedToggle(x, y, legenda)                           chave com capa de proteção
// Moldura: panel(w, h, titulo, corpo), group(x, y, w, h, rotulo), t(x, y, texto, ...).
// rocker(), button(), rotary() e led() são as versões simplificadas da primeira rodada.

"use strict";
var C = {
  panel: "#30353a", edge: "#15181b", legend: "#eef0ea", line: "#9aa1a8",
  korry: "#15181b", unlit: "#555c63",
  green: "#46d37f", amber: "#f2a93b", red: "#e5484d", white: "#f4f7ff",
  pro: "#c6e04a", nrm: "#d24fe0", rad: "#40c9e3", tempo: "#e9ecef", plain: "#e9ecef",
  blue: "#4c9dff"
};

function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

function t(x, y, s, size, anchor, fill, extra) {
  return '<text class="lg" x="' + x + '" y="' + y + '" font-size="' + (size || 3) +
    '" text-anchor="' + (anchor || "middle") + '" fill="' + (fill || C.legend) + '"' +
    (extra ? " " + extra : "") + ">" + esc(s) + "</text>";
}

function screw(x, y) {
  return '<circle cx="' + x + '" cy="' + y + '" r="2.6" fill="url(#nut)" stroke="#1b1f23" stroke-width=".4"/>' +
    '<line x1="' + (x - 1.7) + '" y1="' + (y + 1.7) + '" x2="' + (x + 1.7) + '" y2="' + (y - 1.7) + '" stroke="#2a2e32" stroke-width=".7"/>';
}

function panel(w, h, title, inner) {
  var s = '<rect x="0" y="0" width="' + w + '" height="' + h + '" rx="2.5" fill="' + C.panel + '" stroke="' + C.edge + '" stroke-width=".8"/>';
  s += screw(6, 6) + screw(w - 6, 6) + screw(6, h - 6) + screw(w - 6, h - 6);
  if (title) s += t(w / 2, 10.5, title, 4, "middle", C.legend, 'letter-spacing=".5"');
  return s + inner;
}

function group(x, y, w, h, label) {
  var s = '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="1.2" fill="none" stroke="' + C.legend + '" stroke-width=".35"/>';
  if (label) {
    var lw = label.length * 2.8 * 0.72 + 3;
    s += '<rect x="' + (x + w / 2 - lw / 2) + '" y="' + (y - 2) + '" width="' + lw + '" height="4" fill="' + C.panel + '"/>';
    s += t(x + w / 2, y + 1, label, 2.8, "middle", C.legend, 'letter-spacing=".3"');
  }
  return s;
}

function hexNut(x, y, r) {
  var p = [];
  for (var i = 0; i < 6; i++) { var a = Math.PI / 6 + i * Math.PI / 3; p.push((x + r * Math.cos(a)).toFixed(2) + "," + (y + r * Math.sin(a)).toFixed(2)); }
  return '<polygon points="' + p.join(" ") + '" fill="url(#nut)" stroke="#3a3f44" stroke-width=".3"/>' +
    '<circle cx="' + x + '" cy="' + y + '" r="3.3" fill="#2a2e32"/>';
}

function tri(x, y, dir, color, s) {
  s = s || 1.5;
  var pts;
  if (dir === "up") pts = [x, y - s, x + s, y + s * .8, x - s, y + s * .8];
  else if (dir === "down") pts = [x, y + s, x + s, y - s * .8, x - s, y - s * .8];
  else if (dir === "left") pts = [x - s, y, x + s * .8, y - s, x + s * .8, y + s];
  else pts = [x + s, y, x - s * .8, y - s, x - s * .8, y + s];
  return '<polygon points="' + pts.map(function (v) { return (+v).toFixed(2); }).join(" ") + '" fill="' + (color || C.legend) + '"/>';
}

// seta grossa, como na tecla do TIME WARP: triângulo + haste
function arrow(x, y, dir, color) {
  var s = "", c = color || C.legend;
  if (dir === "up") s += tri(x, y - 1, "up", c, 2.1) + '<rect x="' + (x - .8) + '" y="' + (y + .6) + '" width="1.6" height="2.2" fill="' + c + '"/>';
  else if (dir === "down") s += tri(x, y + 1, "down", c, 2.1) + '<rect x="' + (x - .8) + '" y="' + (y - 2.8) + '" width="1.6" height="2.2" fill="' + c + '"/>';
  else if (dir === "left") s += tri(x - 1, y, "left", c, 2.1) + '<rect x="' + (x + .6) + '" y="' + (y - .8) + '" width="2.2" height="1.6" fill="' + c + '"/>';
  else s += tri(x + 1, y, "right", c, 2.1) + '<rect x="' + (x - 2.8) + '" y="' + (y - .8) + '" width="2.2" height="1.6" fill="' + c + '"/>';
  return s;
}

// tecla basculante com mola, vista de frente
function rocker(x, y, o) {
  var hz = !!o.horiz, w = hz ? 18 : 12, h = hz ? 12 : 18, col = o.color || C.plain, s = "";
  s += '<rect x="' + (x - w / 2 - 1.8) + '" y="' + (y - h / 2 - 1.8) + '" width="' + (w + 3.6) + '" height="' + (h + 3.6) + '" rx="1.6" fill="none" stroke="' + C.legend + '" stroke-width=".35"/>';
  s += '<rect x="' + (x - w / 2 - .7) + '" y="' + (y - h / 2 - .7) + '" width="' + (w + 1.4) + '" height="' + (h + 1.4) + '" rx="1.2" fill="#08090a"/>';
  s += '<rect x="' + (x - w / 2) + '" y="' + (y - h / 2) + '" width="' + w + '" height="' + h + '" rx=".9" fill="url(#knob)"/>';
  if (hz) {
    s += '<line x1="' + x + '" y1="' + (y - h / 2 + 1) + '" x2="' + x + '" y2="' + (y + h / 2 - 1) + '" stroke="#060708" stroke-width=".5"/>';
    s += arrow(x - 4.5, y, "left", col) + arrow(x + 4.5, y, "right", col);
    s += t(x - 5, y - 9, o.minus, 2.4) + t(x + 5, y - 9, o.plus, 2.4);
    if (o.name) s += t(x, y + 12.5, o.name, 3.2);
  } else {
    s += '<line x1="' + (x - w / 2 + 1) + '" y1="' + y + '" x2="' + (x + w / 2 - 1) + '" y2="' + y + '" stroke="#060708" stroke-width=".5"/>';
    s += arrow(x, y - 4.5, "up", col) + arrow(x, y + 4.5, "down", col);
    s += t(x, y - 12.8, o.plus, 2.6) + t(x, y + 15.2, o.minus, 2.6);
    if (o.name) s += t(x, y + 22.5, o.name, 3.2);
  }
  return s;
}

function cap(x, y, color) {
  return '<circle cx="' + x + '" cy="' + y + '" r="2.2" fill="' + color + '" stroke="#0b0d0f" stroke-width=".45"/>';
}

// korry: legenda de uma ou duas metades; acesa ou apagada
function korry(x, y, w, h, top, bot, topColor, botColor) {
  var s = '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="1.3" fill="#0a0c0d"/>';
  s += '<rect x="' + (x + .9) + '" y="' + (y + .9) + '" width="' + (w - 1.8) + '" height="' + (h - 1.8) + '" rx=".8" fill="' + C.korry + '" stroke="#3a4046" stroke-width=".25"/>';
  var fs = Math.min(3.1, (w - 3) / Math.max(top.length, 3) / 0.66);
  if (bot) {
    s += '<line x1="' + (x + 2) + '" y1="' + (y + h * .56) + '" x2="' + (x + w - 2) + '" y2="' + (y + h * .56) + '" stroke="#2c3136" stroke-width=".4"/>';
    if (topColor) s += '<rect x="' + (x + 1.6) + '" y="' + (y + 1.6) + '" width="' + (w - 3.2) + '" height="' + (h * .56 - 2) + '" rx=".5" fill="' + topColor + '" opacity=".13"/>';
    if (botColor) s += '<rect x="' + (x + 1.6) + '" y="' + (y + h * .56 + .4) + '" width="' + (w - 3.2) + '" height="' + (h * .44 - 2) + '" rx=".5" fill="' + botColor + '" opacity=".13"/>';
    s += t(x + w / 2, y + h * .43, top, fs, "middle", topColor || C.unlit);
    var bs = Math.min(2.5, (w - 3) / Math.max(bot.length, 3) / 0.66);
    s += t(x + w / 2, y + h * .86, bot, bs, "middle", botColor || C.unlit);
  } else {
    // topColor = C.unlit: legenda única com LED, apagada
    if (topColor && topColor !== C.unlit) s += '<rect x="' + (x + 1.6) + '" y="' + (y + 1.6) + '" width="' + (w - 3.2) + '" height="' + (h - 3.2) + '" rx=".5" fill="' + topColor + '" opacity=".13"/>';
    s += t(x + w / 2, y + h / 2 + fs * .36, top, fs, "middle", topColor || "#c9ced3");
  }
  return s;
}

function button(x, y, r, label, dir) {
  var s = '<circle cx="' + x + '" cy="' + y + '" r="' + (r + .9) + '" fill="#0a0c0d"/>' +
    '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="url(#knob)"/>';
  if (dir) s += tri(x, y, dir, "#c9ced3");
  if (label) s += t(x, y + r + 4.2, label, 2.6);
  return s;
}

function led(x, y, on, color) {
  var s = "";
  if (on) s += '<circle cx="' + x + '" cy="' + y + '" r="3.2" fill="' + color + '" opacity=".22"/>';
  return s + '<circle cx="' + x + '" cy="' + y + '" r="1.6" fill="' + (on ? color : "#262a2e") + '" stroke="#0a0c0d" stroke-width=".35"/>';
}

function rotary(x, y, labels, sel) {
  var s = "", n = labels.length, a0 = -150, a1 = -30;
  for (var i = 0; i < n; i++) {
    var a = (a0 + (a1 - a0) * i / (n - 1)) * Math.PI / 180;
    var lx = x + 13 * Math.cos(a), ly = y + 13 * Math.sin(a);
    var tx = x + 9.6 * Math.cos(a), ty = y + 9.6 * Math.sin(a);
    s += '<line x1="' + (x + 8.4 * Math.cos(a)).toFixed(2) + '" y1="' + (y + 8.4 * Math.sin(a)).toFixed(2) + '" x2="' + tx.toFixed(2) + '" y2="' + ty.toFixed(2) + '" stroke="' + C.legend + '" stroke-width=".4"/>';
    var parts = labels[i].split("|");
    if (parts[0]) s += t(lx.toFixed(2), (ly + (parts[1] ? -.6 : .9)).toFixed(2), parts[0], 2.3);
    if (parts[1]) s += t(lx.toFixed(2), (ly + 2.2).toFixed(2), parts[1], 1.9, "middle", "#b9bfc5");
  }
  var sa = (a0 + (a1 - a0) * sel / (n - 1)) * Math.PI / 180;
  s += '<circle cx="' + x + '" cy="' + y + '" r="7.8" fill="#0a0c0d"/><circle cx="' + x + '" cy="' + y + '" r="7" fill="url(#knob)"/>';
  s += '<line x1="' + x + '" y1="' + y + '" x2="' + (x + 6.2 * Math.cos(sa)).toFixed(2) + '" y2="' + (y + 6.2 * Math.sin(sa)).toFixed(2) + '" stroke="' + C.legend + '" stroke-width="1" stroke-linecap="round"/>';
  return s;
}

function guardedToggle(x, y, label) {
  var s = '<rect x="' + (x - 7) + '" y="' + (y - 12) + '" width="14" height="22" rx="2" fill="' + C.red + '" opacity=".3"/>';
  s += '<rect x="' + (x - 7) + '" y="' + (y - 12) + '" width="14" height="22" rx="2" fill="none" stroke="' + C.red + '" stroke-width=".7"/>';
  s += '<line x1="' + (x - 7) + '" y1="' + (y - 10.5) + '" x2="' + (x + 7) + '" y2="' + (y - 10.5) + '" stroke="#7a2224" stroke-width="1.2"/>';
  s += hexNut(x, y, 5.2) + cap(x, y + 2, "#d9dde0");
  s += t(x, y + 15.5, label, 3);
  return s;
}

function dims(w, h) {
  var y = h + 6, x = w + 6;
  var s = '<line class="dimline" x1="0" y1="' + y + '" x2="' + w + '" y2="' + y + '"/>' +
    '<line class="dimline" x1="0" y1="' + (y - 2) + '" x2="0" y2="' + (y + 2) + '"/>' +
    '<line class="dimline" x1="' + w + '" y1="' + (y - 2) + '" x2="' + w + '" y2="' + (y + 2) + '"/>';
  s += '<text class="dimtext" x="' + w / 2 + '" y="' + (y + 4.6) + '" text-anchor="middle">' + w + " mm</text>";
  s += '<line class="dimline" x1="' + x + '" y1="0" x2="' + x + '" y2="' + h + '"/>' +
    '<line class="dimline" x1="' + (x - 2) + '" y1="0" x2="' + (x + 2) + '" y2="0"/>' +
    '<line class="dimline" x1="' + (x - 2) + '" y1="' + h + '" x2="' + (x + 2) + '" y2="' + h + '"/>';
  s += '<text class="dimtext" transform="translate(' + (x + 4.4) + " " + h / 2 + ') rotate(90)" text-anchor="middle">' + h + " mm</text>";
  return s;
}

var ESTILO = '<style>.lg{font-family:"B612","Arial Narrow",Arial,sans-serif;font-weight:700}' +
  '.lcdt{font-family:"B612 Mono","Courier New",monospace;font-weight:700}' +
  '.dimline{stroke:#6d7780;stroke-width:.3;fill:none}' +
  '.dimtext{fill:#6d7780;font-family:"B612 Mono","Courier New",monospace;font-size:3.4px}</style>';
var DEFS = '<defs>' +
  '<pattern id="zebra" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">' +
  '<rect width="6" height="6" fill="#1b1d1f"/><rect width="3" height="6" fill="#e7b416"/></pattern>' +
  '<radialGradient id="knob" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#4a5056"/><stop offset="1" stop-color="#15181b"/></radialGradient>' +
  '<radialGradient id="nut" cx="40%" cy="35%" r="75%"><stop offset="0" stop-color="#c9ced3"/><stop offset="1" stop-color="#6c7379"/></radialGradient>' +
  '</defs>';

// Documento SVG completo, com as cotas. Unidades em mm; 4 px por mm na tela.
function svg(w, h, body, label) {
  var vw = w + 16, vh = h + 17;
  return '<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -3 ' + vw + " " + vh +
    '" width="' + vw * 4 + '" height="' + vh * 4 + '" role="img" aria-label="' + esc(label) + '">' +
    ESTILO + DEFS + body + dims(w, h) + "</svg>\n";
}

var KSP = {
  PRO: { color: C.pro, plus: "PRO", minus: "RETRO" },
  NRM: { color: C.nrm, plus: "NRM", minus: "ANTI" },
  RAD: { color: C.rad, plus: "FORA", minus: "DENTRO" },
  TEMPO: { color: C.tempo, plus: "DEPOIS", minus: "ANTES" }
};

// peças no tamanho real (mm)

// encoder EC11 com knob de alumínio Ø 30: estriado, sem risco (não tem posição)
function encoder(x, y, r) {
  var s = '<circle cx="' + x + '" cy="' + y + '" r="' + (r + .8) + '" fill="#07080a"/>';
  s += '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="url(#nut)"/>';
  for (var i = 0; i < 48; i++) {
    var a = i * Math.PI * 2 / 48;
    s += '<line x1="' + (x + (r - 2.2) * Math.cos(a)).toFixed(2) + '" y1="' + (y + (r - 2.2) * Math.sin(a)).toFixed(2) +
      '" x2="' + (x + r * Math.cos(a)).toFixed(2) + '" y2="' + (y + r * Math.sin(a)).toFixed(2) + '" stroke="#5d646b" stroke-width=".35"/>';
  }
  s += '<circle cx="' + x + '" cy="' + y + '" r="' + (r - 2.6) + '" fill="url(#knob)" stroke="#8a9096" stroke-width=".3"/>';
  s += '<circle cx="' + x + '" cy="' + (y - r * .45) + '" r="2.2" fill="#101316" stroke="#3c4248" stroke-width=".3"/>';
  return s;
}

// arco com setas gravado em volta do encoder: - no anti-horário, + no horário
function encoderArc(x, y, R) {
  function pt(deg, rr) { var a = deg * Math.PI / 180; return [x + (rr || R) * Math.cos(a), y + (rr || R) * Math.sin(a)]; }
  var p0 = pt(-150), p1 = pt(-30), s = "";
  s += '<path d="M' + p0[0].toFixed(2) + " " + p0[1].toFixed(2) + " A" + R + " " + R + " 0 0 1 " + p1[0].toFixed(2) + " " + p1[1].toFixed(2) +
    '" fill="none" stroke="' + C.legend + '" stroke-width=".4"/>';
  // pontas de seta, tangentes ao arco
  function head(deg, dir) {
    var a = deg * Math.PI / 180, tx = -Math.sin(a) * dir, ty = Math.cos(a) * dir, p = pt(deg);
    var nx = Math.cos(a), ny = Math.sin(a), L = 2.2, W = 1.1;
    return '<polygon points="' + (p[0] + tx * L).toFixed(2) + "," + (p[1] + ty * L).toFixed(2) + " " +
      (p[0] + nx * W).toFixed(2) + "," + (p[1] + ny * W).toFixed(2) + " " + (p[0] - nx * W).toFixed(2) + "," + (p[1] - ny * W).toFixed(2) +
      '" fill="' + C.legend + '"/>';
  }
  s += head(-150, -1) + head(-30, 1);
  var m = pt(-160, R + 1.5), p = pt(-20, R + 1.5);
  s += t(m[0].toFixed(2), (m[1] + 1.6).toFixed(2), "-", 4.2) + t(p[0].toFixed(2), (p[1] + 1.6).toFixed(2), "+", 4.2);
  return s;
}

// chave rotativa com knob de ponteiro Ø 22 e a legenda gravada em volta
function rotaryReal(x, y, labels, sel) {
  var s = "", n = labels.length, a0 = -150, a1 = -30, r = 11, R = 15.5;
  for (var i = 0; i < n; i++) {
    var a = (a0 + (a1 - a0) * i / (n - 1)) * Math.PI / 180;
    s += '<line x1="' + (x + (r + 1) * Math.cos(a)).toFixed(2) + '" y1="' + (y + (r + 1) * Math.sin(a)).toFixed(2) +
      '" x2="' + (x + (r + 2.6) * Math.cos(a)).toFixed(2) + '" y2="' + (y + (r + 2.6) * Math.sin(a)).toFixed(2) + '" stroke="' + C.legend + '" stroke-width=".45"/>';
    var parts = labels[i].split("|"), lx = x + (R + 2.4) * Math.cos(a), ly = y + (R + 2.4) * Math.sin(a);
    s += t(lx.toFixed(2), (ly - .4).toFixed(2), parts[0], 2.5);
    s += t(lx.toFixed(2), (ly + 2.4).toFixed(2), parts[1], 2, "middle", "#b9bfc5");
  }
  var sa = (a0 + (a1 - a0) * sel / (n - 1)) * Math.PI / 180;
  s += '<circle cx="' + x + '" cy="' + y + '" r="' + (r + .7) + '" fill="#07080a"/><circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="url(#knob)"/>';
  s += '<circle cx="' + x + '" cy="' + y + '" r="' + (r - 3) + '" fill="none" stroke="#454b51" stroke-width=".35"/>';
  s += '<line x1="' + (x + 2 * Math.cos(sa)).toFixed(2) + '" y1="' + (y + 2 * Math.sin(sa)).toFixed(2) + '" x2="' + (x + (r - .8) * Math.cos(sa)).toFixed(2) +
    '" y2="' + (y + (r - .8) * Math.sin(sa)).toFixed(2) + '" stroke="' + C.legend + '" stroke-width="1.2" stroke-linecap="round"/>';
  return s;
}

// tecla basculante 21 x 15 mm (moldura), deitada
function rockerReal(x, y) {
  var W = 21, H = 15, s = "";
  s += '<rect x="' + (x - W / 2) + '" y="' + (y - H / 2) + '" width="' + W + '" height="' + H + '" rx="1.4" fill="#08090a"/>';
  s += '<rect x="' + (x - W / 2 + 1.6) + '" y="' + (y - H / 2 + 1.6) + '" width="' + (W - 3.2) + '" height="' + (H - 3.2) + '" rx=".8" fill="url(#knob)"/>';
  s += '<line x1="' + x + '" y1="' + (y - H / 2 + 2.4) + '" x2="' + x + '" y2="' + (y + H / 2 - 2.4) + '" stroke="#060708" stroke-width=".5"/>';
  s += arrow(x - 4.6, y, "left", C.tempo) + arrow(x + 4.6, y, "right", C.tempo);
  return s;
}

// botão de metal 12 mm: cabeça Ø 14
function metalButton(x, y, label, dir) {
  var s = '<circle cx="' + x + '" cy="' + y + '" r="7" fill="url(#nut)" stroke="#2a2e32" stroke-width=".3"/>';
  s += '<circle cx="' + x + '" cy="' + y + '" r="4.8" fill="url(#knob)" stroke="#9aa1a8" stroke-width=".3"/>';
  if (dir) s += tri(x, y, dir, "#c9ced3", 1.4);
  s += t(x, y + 11, label, 2.7);
  return s;
}

// Modos do SAS: o ícone é o marcador na navball do KSP
var SAS = {
  ESTAB: "ESTAB", MAN: "MANOBRA", PRO: "PRO", RETRO: "RETRO", NRM: "NORMAL", ANRM: "ANTINRM",
  RFORA: "RAD FORA", RDENTRO: "RAD DENTRO", ALVO: "ALVO", AALVO: "ANTIALVO"
};

// ícone de um modo do SAS, centrado em (x, y), uns 7 mm de largura
function sasIcon(x, y, modo, cor) {
  var sw = 'stroke="' + cor + '" stroke-width=".55" fill="none" stroke-linecap="round"';
  function circ(r, extra) { return '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" ' + sw + (extra || "") + "/>"; }
  function dot() { return '<circle cx="' + x + '" cy="' + y + '" r=".55" fill="' + cor + '"/>'; }
  function ray(deg, r0, r1) {
    var a = deg * Math.PI / 180;
    return '<line x1="' + (x + r0 * Math.cos(a)).toFixed(2) + '" y1="' + (y + r0 * Math.sin(a)).toFixed(2) +
      '" x2="' + (x + r1 * Math.cos(a)).toFixed(2) + '" y2="' + (y + r1 * Math.sin(a)).toFixed(2) + '" ' + sw + "/>";
  }
  function tri3(dir, r) {
    var p = [], d0 = dir === "up" ? -90 : 90;
    for (var i = 0; i < 3; i++) { var a = (d0 + i * 120) * Math.PI / 180; p.push((x + r * Math.cos(a)).toFixed(2) + "," + (y + r * Math.sin(a)).toFixed(2)); }
    return '<polygon points="' + p.join(" ") + '" ' + sw + ' stroke-linejoin="round"/>';
  }
  switch (modo) {
    case "ESTAB": return circ(2.6) + ray(180, 0, 1.5) + ray(0, 0, 1.5);
    case "MAN": return circ(2.1) + dot() + [-90, 30, 150].map(function (d) {
      var a = d * Math.PI / 180, b = 3.9, w = 1.2, px = -Math.sin(a), py = Math.cos(a);
      return '<polygon points="' + (x + 2.6 * Math.cos(a)).toFixed(2) + "," + (y + 2.6 * Math.sin(a)).toFixed(2) + " " +
        (x + b * Math.cos(a) + w * px).toFixed(2) + "," + (y + b * Math.sin(a) + w * py).toFixed(2) + " " +
        (x + b * Math.cos(a) - w * px).toFixed(2) + "," + (y + b * Math.sin(a) - w * py).toFixed(2) + '" fill="' + cor + '"/>';
    }).join("");
    case "PRO": return circ(2.2) + dot() + ray(-90, 2.2, 3.8) + ray(180, 2.2, 3.8) + ray(0, 2.2, 3.8);
    case "RETRO": return circ(2.2) + ray(45, -2.2, 2.2) + ray(135, -2.2, 2.2) + ray(-90, 2.2, 3.8) + ray(150, 2.2, 3.8) + ray(30, 2.2, 3.8);
    case "NRM": return tri3("up", 3) + dot();
    case "ANRM": return tri3("down", 3) + dot() + ray(-90, 1.5, 3.9) + ray(30, 1.5, 3.9) + ray(150, 1.5, 3.9);
    case "RFORA": return circ(2) + dot() + [45, 135, 225, 315].map(function (d) { return ray(d, 2, 3.7); }).join("");
    case "RDENTRO": return circ(3) + [45, 135, 225, 315].map(function (d) { return ray(d, 1, 3); }).join("");
    case "ALVO": return circ(2.6, ' stroke-dasharray="1.1 .7"') + dot() + [0, 90, 180, 270].map(function (d) { return ray(d, 2.6, 3.8); }).join("");
    case "AALVO": return circ(2.6) + [-90, 30, 150].map(function (d) { return ray(d, 0, 2.6); }).join("");
  }
  return "";
}

// korry de modo do SAS: ícone em cima, legenda embaixo. Um LED de duas cores atrás:
// cor = C.blue (a nave vira para o marcador), C.green (o SAS segura nele) ou nada (apagado)
function korrySas(x, y, modo, cor) {
  var legenda = SAS[modo], w = 22.5, c = cor || C.unlit;
  var s = '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + w + '" rx="1.3" fill="#0a0c0d"/>';
  s += '<rect x="' + (x + .9) + '" y="' + (y + .9) + '" width="' + (w - 1.8) + '" height="' + (w - 1.8) + '" rx=".8" fill="' + C.korry + '" stroke="#3a4046" stroke-width=".25"/>';
  if (cor) s += '<rect x="' + (x + 1.6) + '" y="' + (y + 1.6) + '" width="' + (w - 3.2) + '" height="' + (w - 3.2) + '" rx=".5" fill="' + cor + '" opacity=".13"/>';
  s += sasIcon(x + w / 2, y + 9.2, modo, c);
  var fs = Math.min(2.4, (w - 3) / legenda.length / 0.66);
  s += t(x + w / 2, y + 19.3, legenda, fs, "middle", c);
  return s;
}

module.exports = { SAS, sasIcon, korrySas, C, KSP, esc, t, screw, panel, group, hexNut, tri, arrow, rocker, cap, korry, button, led, rotary, guardedToggle, dims, svg, encoder, encoderArc, rotaryReal, rockerReal, metalButton };
