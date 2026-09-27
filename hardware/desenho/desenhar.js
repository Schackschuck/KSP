// Gera o SVG de cada painel em hardware/img/<nome>.svg.
//
//   node hardware/desenho/desenhar.js                    todos os painéis
//   node hardware/desenho/desenhar.js editor_manobras    só um
//
// Cada painel é um arquivo em paineis/ que exporta uma função sem
// argumentos e devolve o SVG completo (ver paineis/editor_manobras.js).

"use strict";
var fs = require("fs");
var path = require("path");

var pastaPaineis = path.join(__dirname, "paineis");
var pastaImg = path.join(__dirname, "..", "img");

var nomes = process.argv.slice(2);
if (nomes.length === 0) {
  nomes = fs.readdirSync(pastaPaineis)
    .filter(function (f) { return f.endsWith(".js"); })
    .map(function (f) { return f.slice(0, -3); })
    .sort();
}

nomes.forEach(function (nome) {
  var arquivo = path.join(pastaPaineis, nome + ".js");
  if (!fs.existsSync(arquivo)) {
    console.error("Painel não encontrado: " + arquivo);
    process.exitCode = 1;
    return;
  }
  var svg = require(arquivo)();
  var destino = path.join(pastaImg, nome + ".svg");
  fs.writeFileSync(destino, svg);
  console.log(path.relative(process.cwd(), destino));
});
