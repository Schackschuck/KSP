// Gera o SVG de cada painel em hardware/img/<nome>.svg.
//
//   node hardware/desenho/desenhar.js                    todos os painéis
//   node hardware/desenho/desenhar.js editor_manobras    só um
//   node hardware/desenho/desenhar.js antigos            os de 150 mm, em img/antigos/
//
// Cada painel é um arquivo em paineis/ que exporta uma função sem
// argumentos e devolve { w, h, corpo, rotulo } (ver paineis/tempo.js).

"use strict";
var fs = require("fs");
var path = require("path");

var P = require("./pecas");
var pastaPaineis = path.join(__dirname, "paineis");
var pastaImg = path.join(__dirname, "..", "img");
var pastaAntigos = path.join(__dirname, "antigos");
var pastaImgAntigos = path.join(pastaImg, "antigos");
var grades = require("../korry/grades.json");

grades.forEach(function (g) {
  var arquivo = require.resolve(path.join(pastaPaineis, g.painel + ".js"));
  var original = require(arquivo);
  var parafusos = g.parafusos;
  require.cache[arquivo].exports = function () {
    var d = original();
    parafusos.forEach(function (p) { d.corpo += P.screw(p[0], p[1]); });
    return d;
  };
});

function gerar(arquivo, destino) {
  var d = require(arquivo)();
  fs.writeFileSync(destino, typeof d === "string" ? d : P.svg(d.w, d.h, d.corpo, d.rotulo));
  console.log(path.relative(process.cwd(), destino));
}

var nomes = process.argv.slice(2);
if (nomes.length === 0) {
  nomes = fs.readdirSync(pastaPaineis)
    .filter(function (f) { return f.endsWith(".js"); })
    .map(function (f) { return f.slice(0, -3); })
    .sort();
}

nomes.forEach(function (nome) {
  var arquivo = path.join(pastaPaineis, nome + ".js");
  if (nome === "antigos") {
    fs.readdirSync(pastaAntigos).filter(function (f) { return f.endsWith(".js"); }).sort().forEach(function (f) {
      gerar(path.join(pastaAntigos, f), path.join(pastaImgAntigos, f.slice(0, -3) + ".svg"));
    });
    return;
  }
  if (!fs.existsSync(arquivo)) {
    console.error("Painel não encontrado: " + arquivo);
    process.exitCode = 1;
    return;
  }
  gerar(arquivo, path.join(pastaImg, nome + ".svg"));
});
