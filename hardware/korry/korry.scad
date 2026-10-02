peca = "montagem";
texto_cima = "SAS";
texto_baixo = "SEM EC";
modo_sas = "";
celulas = [[0, 0]];
furos = [];
fonte = "B612:style=Bold";
folga = 0.5;

painel = 3;
tubo_interno = 22.9;
frente = tubo_interno - 2 * folga;
parede = 1.0;
saliencia = 3;
tampa = 1.8;
mascara = 0.6;
comprimento = 16;
recuo = 4;
divisoria_y = 0;
divisoria_e = 1.0;
ressalto_l = 1.4;
ressalto_c = 2;
ressalto_largura = 6;
ressalto_y = 0.7;
letra_cima = 3;
letra_baixo = 2.4;
caixa_l = 15;
caixa_a = 5.6;
caixa_traco = 0.6;
traco_icone = 0.7;
orelha_l = 7;
orelha_esp = 5;
furo_m3 = 2.5;
passo_min = 25.5;

chave = 8.5;
chave_h = 8;
haste_h = 5.5;
haste_x = 2;
haste_y = 3;
pino_c = 4;
pino_passo = 2.5;
pino_fileiras = 5.4;
curso = 2.5;
pre_carga = 0.3;
margem = 0.5;

tubo_parede = 1.2;
tubo_comprimento = 16;
suporte_esp = 1.6;
suporte_folga = 1.2;
furo_pino = 1.1;
furo_led = 1.0;
led_y = 7.2;
led_pernas = 2.54;

aba_l = 7;
aba_e = 0.8;
aba_c = 5;
dente = 0.5;

$fn = 48;

sas_nomes = [["ESTAB", "ESTAB"], ["MAN", "MANOBRA"], ["PRO", "PRO"], ["RETRO", "RETRO"], ["NRM", "NORMAL"],
             ["ANRM", "ANTINRM"], ["RFORA", "RAD FORA"], ["RDENTRO", "RAD DENTRO"], ["ALVO", "ALVO"], ["AALVO", "ANTIALVO"]];

lado = frente - 2 * parede;
largura_util = lado - 2.5;
palavras_sas = [for (p = sas_nomes) if (p[0] == modo_sas) p[1]];
palavra_sas = len(palavras_sas) > 0 ? palavras_sas[0] : "";
em_branco = texto_cima == "" && texto_baixo == "" && modo_sas == "";
duas_metades = texto_baixo != "" && modo_sas == "";
caixa_larg = min(caixa_l, max(len(texto_baixo), 3) * 0.85 * tamanho(texto_baixo, letra_baixo) + 4);
centro_cima = duas_metades ? (lado / 2 + divisoria_y + divisoria_e / 2) / 2 : 0;
centro_baixo = (-lado / 2 + divisoria_y - divisoria_e / 2) / 2;

tubo_externo = tubo_interno + 2 * tubo_parede;
suporte_lado = tubo_interno + suporte_folga;
trilho_l = frente / 2 + ressalto_l + folga - tubo_interno / 2;
trilho_largura = ressalto_largura + 2 * folga;
batente = comprimento - ressalto_c - painel;
costas = tampa - saliencia;

suporte_z = painel + tubo_comprimento;
chave_z = suporte_z - chave_h;
haste_z = chave_z - haste_h;
apoio_z = haste_z + pre_carga;
fundo_corpo = suporte_z - curso - margem;
degrau_z = chave_z - curso - margem;

dente_z = costas + 3.2;
dente_topo = costas + 4.0;
aba_topo = costas + aba_c;

assert(len(celulas) > 0, "sem celulas");
assert(passo_ok(celulas), "korry mais perto que passo_min");
assert(modo_sas == "" || len(palavras_sas) > 0, "modo_sas desconhecido");
assert(abs(fundo_corpo - comprimento) < 0.001, "fundo do corpo diferente do comprimento");
assert(led_y - 1.9 > chave / 2, "LED encosta na chave");
assert(led_y + 1.9 < lado / 2, "LED encosta na parede");

vidro = [0.85, 0.92, 1];
escuro = 0.62;
cortar = peca == "corte";

module pinta(c) {
    if (cortar) {
        color([c[0] * escuro, c[1] * escuro, c[2] * escuro, len(c) == 4 ? c[3] : 1]) render() difference() { children(); translate([-0.1, -50, -50]) cube([100, 100, 100]); }
        color(c) render() intersection() { children(); translate([-0.1, -50, -50]) cube([0.1, 100, 100]); }
    } else color(c) children();
}

module bloco(x0, x1, y0, y1, z0, z1) {
    translate([x0, y0, z0]) cube([x1 - x0, y1 - y0, z1 - z0]);
}

function tamanho(texto, maximo) = min(maximo, largura_util / (max(len(texto), 3) * 0.85));

module anel(r) {
    difference() { circle(r + traco_icone / 2, $fn = 48); circle(r - traco_icone / 2, $fn = 48); }
}

module raio(graus, r0, r1) {
    hull() for (r = [r0, r1]) translate([r * cos(-graus), r * sin(-graus)]) circle(d = traco_icone, $fn = 16);
}

module ponto() {
    circle(r = 0.55, $fn = 16);
}

module triangulo_icone(baixo, r) {
    pts = [for (i = [0 : 2]) let(a = -((baixo ? 90 : -90) + i * 120)) [r * cos(a), r * sin(a)]];
    difference() {
        offset(r = traco_icone / 2, $fn = 16) polygon(pts);
        offset(delta = -traco_icone / 2) polygon(pts);
    }
}

module seta_man(graus) {
    a = -graus;
    d = [cos(a), sin(a)];
    n = [-sin(a), cos(a)];
    polygon([2.6 * d, 3.9 * d + 1.2 * n, 3.9 * d - 1.2 * n]);
}

module anel_tracejado(r) {
    intersection() {
        anel(r);
        for (i = [0 : 8]) {
            a0 = -i * 40 - 1.1 / r * 180 / PI;
            a1 = -i * 40;
            polygon([[0, 0], 6 * [cos(a0), sin(a0)], 6 * [cos(a1), sin(a1)]]);
        }
    }
}

module icone_sas(modo) {
    if (modo == "ESTAB") { anel(2.6); raio(180, 0, 1.5); raio(0, 0, 1.5); }
    if (modo == "MAN") { anel(2.1); ponto(); for (g = [-90, 30, 150]) seta_man(g); }
    if (modo == "PRO") { anel(2.2); ponto(); for (g = [-90, 180, 0]) raio(g, 2.2, 3.8); }
    if (modo == "RETRO") {
        anel(2.2);
        for (g = [45, 135]) raio(g, -2.2, 2.2);
        for (g = [-90, 150, 30]) raio(g, 2.2, 3.8);
    }
    if (modo == "NRM") { triangulo_icone(false, 3); ponto(); }
    if (modo == "ANRM") { triangulo_icone(true, 3); ponto(); for (g = [-90, 30, 150]) raio(g, 1.5, 3.9); }
    if (modo == "RFORA") { anel(2); ponto(); for (g = [45, 135, 225, 315]) raio(g, 2, 3.7); }
    if (modo == "RDENTRO") { anel(3); for (g = [45, 135, 225, 315]) raio(g, 1, 3); }
    if (modo == "ALVO") { anel_tracejado(2.6); ponto(); for (g = [0, 90, 180, 270]) raio(g, 2.6, 3.8); }
    if (modo == "AALVO") { anel(2.6); for (g = [-90, 30, 150]) raio(g, 0, 2.6); }
}

module legenda() {
    mirror([1, 0]) {
        if (modo_sas != "") {
            translate([0, 2.0]) icone_sas(modo_sas);
            translate([0, -6.8]) text(palavra_sas, size = tamanho(palavra_sas, 2.4), font = fonte, halign = "center", valign = "center");
        } else {
            if (texto_cima != "")
                translate([0, centro_cima]) text(texto_cima, size = tamanho(texto_cima, letra_cima), font = fonte, halign = "center", valign = "center");
            if (duas_metades) translate([0, centro_baixo]) {
                text(texto_baixo, size = tamanho(texto_baixo, letra_baixo), font = fonte, halign = "center", valign = "center");
                difference() {
                    square([caixa_larg, caixa_a], center = true);
                    square([caixa_larg - 2 * caixa_traco, caixa_a - 2 * caixa_traco], center = true);
                }
            }
        }
    }
}

module letras(z0, h) {
    if (!em_branco)
        translate([0, 0, z0]) linear_extrude(h) intersection() { legenda(); square(lado, center = true); }
}

module divisoria_legenda() {
    if (duas_metades)
        bloco(-lado / 2, lado / 2, divisoria_y - divisoria_e / 2, divisoria_y + divisoria_e / 2, -saliencia + mascara, costas + recuo - 0.1);
}

module blocos_abas() {
    for (m = [0, 1]) mirror([0, m, 0]) bloco(-aba_l / 2, aba_l / 2, lado / 2 - 1, lado / 2, -saliencia + mascara, costas);
}

module aba() {
    y0 = lado / 2 - 0.1;
    bloco(-aba_l / 2, aba_l / 2, y0 - aba_e, y0, costas, aba_topo);
    rotate([90, 0, 90]) linear_extrude(aba_l, center = true)
        polygon([[y0 - 0.1, dente_z], [y0 + dente, dente_z], [y0 + dente, dente_topo], [y0, aba_topo], [y0 - 0.1, aba_topo]]);
}

module legenda_preto() {
    difference() {
        bloco(-frente / 2, frente / 2, -frente / 2, frente / 2, -saliencia, costas);
        bloco(-lado / 2, lado / 2, -lado / 2, lado / 2, -saliencia - 1, costas + 1);
    }
    difference() {
        bloco(-lado / 2, lado / 2, -lado / 2, lado / 2, -saliencia, -saliencia + mascara);
        letras(-saliencia - 1, mascara + 1);
    }
    divisoria_legenda();
    blocos_abas();
    for (m = [0, 1]) mirror([0, m, 0]) aba();
}

module legenda_transparente() {
    letras(-saliencia, mascara);
    difference() {
        bloco(-lado / 2, lado / 2, -lado / 2, lado / 2, -saliencia + mascara, costas);
        divisoria_legenda();
        blocos_abas();
    }
}

module janelas() {
    for (m = [0, 1]) mirror([0, m, 0])
        bloco(-aba_l / 2 - 0.25, aba_l / 2 + 0.25, lado / 2 - 0.1, frente / 2 + 1, dente_z - 0.1, aba_topo + 0.1);
}

module ressaltos() {
    for (m = [0, 1]) rotate([0, 0, 180 * m])
        bloco(frente / 2 - 0.1, frente / 2 + ressalto_l, ressalto_y, ressalto_y + ressalto_largura, comprimento - ressalto_c, comprimento);
}

module perfil_divisoria() {
    e = divisoria_e / 2;
    rotate([90, 0, 90]) linear_extrude(lado + 0.2, center = true)
        polygon([[divisoria_y - 0.2, costas + recuo], [divisoria_y + 0.2, costas + recuo], [divisoria_y + e, costas + recuo + 1.5],
                 [divisoria_y + e, comprimento], [divisoria_y - e, comprimento], [divisoria_y - e, costas + recuo + 1.5]]);
}

module degraus_divisoria() {
    w = lado / 2 + 0.1;
    rotate([90, 0, 0]) linear_extrude(6, center = true)
        polygon([[-w, 0], [-w, comprimento], [-4.6, comprimento], [-4.6, degrau_z], [-2.3, degrau_z], [-2.3, apoio_z],
                 [2.3, apoio_z], [2.3, degrau_z], [4.6, degrau_z], [4.6, comprimento], [w, comprimento], [w, 0]]);
}

module divisoria_corpo() {
    intersection() { perfil_divisoria(); degraus_divisoria(); }
    bloco(-1.8, 1.8, divisoria_y - 1.6, divisoria_y + 1.6, apoio_z - 1.5, apoio_z);
}

module corpo() {
    difference() {
        bloco(-frente / 2, frente / 2, -frente / 2, frente / 2, costas, comprimento);
        bloco(-lado / 2, lado / 2, -lado / 2, lado / 2, costas - 1, comprimento + 1);
        janelas();
    }
    ressaltos();
    divisoria_corpo();
}

function passo_ok(c) = len(c) < 2 ? true :
    min([for (i = [0 : len(c) - 2], j = [i + 1 : len(c) - 1]) max(abs(c[i][0] - c[j][0]), abs(c[i][1] - c[j][1]))]) >= passo_min - 0.001;

function dist_a(p, c) = [for (q = c) norm(q - p)];
function proxima(p, c) = c[search(min(dist_a(p, c)), dist_a(p, c))[0]];
function dist_i(i, c) = [for (k = [0 : len(c) - 1]) k == i ? 1e9 : norm(c[k] - c[i])];
function vizinha(i, c) = search(min(dist_i(i, c)), dist_i(i, c))[0];

module gancho(x0, x1) {
    bloco(x0, x1, suporte_lado / 2, suporte_lado / 2 + 0.9, tubo_comprimento - 1, tubo_comprimento + suporte_esp + 1.2);
    bloco(x0, x1, suporte_lado / 2 - 0.6, suporte_lado / 2, tubo_comprimento + suporte_esp, tubo_comprimento + suporte_esp + 1.2);
}

module ganchos() {
    gancho(-8, -3);
    mirror([0, 1, 0]) gancho(3, 8);
}

module vazios() {
    translate([-tubo_interno / 2, -tubo_interno / 2, -1]) cube([tubo_interno, tubo_interno, tubo_comprimento + 2]);
    for (s = [-1, 1])
        translate([s * (tubo_interno / 2 + trilho_l / 2) - trilho_l / 2, s * (ressalto_y + ressalto_largura / 2) - trilho_largura / 2, batente])
            cube([trilho_l, trilho_largura, tubo_comprimento]);
}

module tubos(cel) {
    linear_extrude(tubo_comprimento) offset(delta = -1) offset(delta = 1)
        for (c = cel) translate(c) square(tubo_externo, center = true);
}

module orelha(f, cel) {
    p = proxima(f, cel);
    pe = abs(p[0] - f[0]) >= abs(p[1] - f[1]) ? [p[0], f[1]] : [f[0], p[1]];
    linear_extrude(orelha_esp) hull() {
        translate(f) circle(d = orelha_l);
        translate(pe) square(orelha_l, center = true);
    }
}

module barras(cel) {
    if (len(cel) > 1) for (i = [0 : len(cel) - 1]) {
        j = vizinha(i, cel);
        if (norm(cel[i] - cel[j]) > tubo_externo + 2)
            linear_extrude(orelha_esp) hull() {
                translate(cel[i]) square(6, center = true);
                translate(cel[j]) square(6, center = true);
            }
    }
}

module grade(cel = [[0, 0]], fur = []) {
    difference() {
        union() {
            tubos(cel);
            for (c = cel) translate([c[0], c[1], 0]) ganchos();
            for (f = fur) orelha(f, cel);
            barras(cel);
        }
        for (c = cel) translate([c[0], c[1], 0]) vazios();
        for (f = fur) translate([f[0], f[1], -1]) cylinder(d = furo_m3, h = orelha_esp + 2);
    }
}

module nervuras() {
    for (m = [0, 1]) mirror([m, 0, 0])
        bloco(4.6, lado / 2 - 0.25, 0.9, 1.7, suporte_z - 2, suporte_z + 0.1);
}

module furos_suporte() {
    for (x = [-pino_passo, 0, pino_passo], y = [-pino_fileiras / 2, pino_fileiras / 2])
        translate([x, y, suporte_z - 1]) cylinder(d = furo_pino, h = suporte_esp + 2);
    for (x = [-led_pernas / 2, led_pernas / 2], y = [-led_y, led_y])
        translate([x, y, suporte_z - 1]) cylinder(d = furo_led, h = suporte_esp + 2);
}

module suporte() {
    difference() {
        union() {
            bloco(-suporte_lado / 2, suporte_lado / 2, -suporte_lado / 2, suporte_lado / 2, suporte_z, suporte_z + suporte_esp);
            nervuras();
        }
        furos_suporte();
        translate([0, 10, suporte_z + suporte_esp - 0.4]) linear_extrude(1)
            text("CIMA", size = 2, font = fonte, halign = "center", valign = "center");
    }
}

module chave_ref() {
    pinta([0.83, 0.83, 0.83]) bloco(-chave / 2, chave / 2, -chave / 2, chave / 2, chave_z, suporte_z);
    pinta([0, 0, 0]) bloco(-haste_x / 2, haste_x / 2, -haste_y / 2, haste_y / 2, haste_z + pre_carga, chave_z);
    pinta([1, 0.84, 0]) for (x = [-pino_passo, 0, pino_passo], y = [-pino_fileiras / 2, pino_fileiras / 2])
        bloco(x - 0.25, x + 0.25, y - 0.2, y + 0.2, suporte_z, suporte_z + pino_c);
}

module leds_ref() {
    for (y = [-led_y, led_y]) translate([0, y, 0]) {
        pinta([1, 1, 1]) translate([0, 0, suporte_z - 3.8]) { cylinder(d = 3, h = 3.8); sphere(d = 3); }
        pinta([1, 0.84, 0]) for (x = [-led_pernas / 2, led_pernas / 2])
            bloco(x - 0.25, x + 0.25, -0.25, 0.25, suporte_z, suporte_z + suporte_esp + 3);
    }
}

module painel_ref() {
    pinta([0.19, 0.21, 0.23, 0.55]) difference() {
        translate([-20, -20, 0]) cube([40, 40, painel]);
        translate([-11.5, -11.5, -1]) cube([23, 23, painel + 2]);
    }
}

module legenda_cores() {
    pinta([0.41, 0.41, 0.41]) legenda_preto();
    pinta(vidro) legenda_transparente();
}

module teste_folga() {
    folgas = [0.35, 0.4, 0.45, 0.5, 0.6];
    for (i = [0 : 4]) translate([i * 30, 0, 0]) difference() {
        translate([-13, -13, 0]) cube([26, 26, 6]);
        translate([-(frente / 2 + folgas[i]), -(frente / 2 + folgas[i]), -1]) cube([frente + 2 * folgas[i], frente + 2 * folgas[i], 8]);
        translate([-12, -12.6, 5.4]) linear_extrude(1) text(str(folgas[i]), size = 2.2, font = fonte);
    }
    translate([0, 40, 0]) difference() {
        translate([-frente / 2, -frente / 2, 0]) cube([frente, frente, 10]);
        translate([-lado / 2, -lado / 2, -1]) cube([lado, lado, 12]);
    }
}

module montagem() {
    painel_ref();
    legenda_cores();
    pinta([0.41, 0.41, 0.41]) corpo();
    pinta([0.5, 0.5, 0.5]) translate([0, 0, painel]) grade();
    pinta([0.18, 0.31, 0.31]) suporte();
    chave_ref();
    leds_ref();
}

module explodida() {
    legenda_cores();
    pinta([0.41, 0.41, 0.41]) translate([0, 0, 12]) corpo();
    pinta([0.5, 0.5, 0.5]) translate([0, 0, 40]) grade();
    translate([0, 0, 70]) {
        pinta([0.18, 0.31, 0.31]) suporte();
        chave_ref();
        leds_ref();
    }
}

if (peca == "montagem") montagem();
if (peca == "corte") rotate([0, 90, 0]) montagem();
if (peca == "frente") legenda_cores();
if (peca == "legenda_2d") intersection() { legenda(); square(lado, center = true); }
if (peca == "explodida") explodida();
if (peca == "legenda_preto") translate([0, 0, saliencia]) legenda_preto();
if (peca == "legenda_transparente") translate([0, 0, saliencia]) legenda_transparente();
if (peca == "corpo") translate([0, 0, comprimento]) rotate([180, 0, 0]) corpo();
if (peca == "base") grade();
if (peca == "grade") grade(celulas, furos);
if (peca == "suporte") translate([0, 0, suporte_z + suporte_esp]) rotate([180, 0, 0]) suporte();
if (peca == "teste") teste_folga();
