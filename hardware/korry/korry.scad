peca = "montagem";
texto_cima = "SAS";
texto_baixo = "SEM EC";
fonte = "B612:style=Bold";
folga = 0.2;

painel = 3;
frente = 22.5;
parede = 1.0;
tampa = 3;
mascara = 0.6;
comprimento = 16;
recuo = 4;
divisoria_y = 0;
divisoria_e = 1.0;
ressalto_l = 1.4;
ressalto_c = 2;
ressalto_largura = 6;
letra_cima = 3;
letra_baixo = 2.4;
caixa_l = 15;
caixa_a = 5.6;
caixa_traco = 0.6;

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
furo_pino = 1.1;
furo_led = 1.0;
led_y = 7.2;
led_pernas = 2.54;

aba_l = 7;
aba_e = 0.8;
aba_c = 5;
dente = 0.5;

$fn = 48;

duas_metades = texto_baixo != "";
lado = frente - 2 * parede;
centro_cima = duas_metades ? (lado / 2 + divisoria_y + divisoria_e / 2) / 2 : 0;
centro_baixo = (-lado / 2 + divisoria_y - divisoria_e / 2) / 2;

tubo_interno = frente + 2 * folga;
tubo_externo = tubo_interno + 2 * tubo_parede;
trilho_l = ressalto_l + 0.3;
trilho_largura = ressalto_largura + 0.6;
batente = comprimento - ressalto_c - painel;

suporte_z = painel + tubo_comprimento;
chave_z = suporte_z - chave_h;
haste_z = chave_z - haste_h;
apoio_z = haste_z + pre_carga;
fundo_corpo = suporte_z - curso - margem;
degrau_z = chave_z - curso - margem;

dente_z = 3.2;
dente_topo = 4.0;

assert(abs(fundo_corpo - comprimento) < 0.001, "fundo do corpo diferente do comprimento");
assert(led_y - 1.9 > chave / 2, "LED encosta na chave");
assert(led_y + 1.9 < lado / 2, "LED encosta na parede");

vidro = [0.85, 0.92, 1];

module bloco(x0, x1, y0, y1, z0, z1) {
    translate([x0, y0, z0]) cube([x1 - x0, y1 - y0, z1 - z0]);
}

module legenda() {
    mirror([1, 0]) {
        translate([0, centro_cima]) text(texto_cima, size = letra_cima, font = fonte, halign = "center", valign = "center");
        if (duas_metades) translate([0, centro_baixo]) {
            text(texto_baixo, size = letra_baixo, font = fonte, halign = "center", valign = "center");
            difference() {
                square([caixa_l, caixa_a], center = true);
                square([caixa_l - 2 * caixa_traco, caixa_a - 2 * caixa_traco], center = true);
            }
        }
    }
}

module letras(z0, h) {
    translate([0, 0, z0]) linear_extrude(h) intersection() { legenda(); square(lado, center = true); }
}

module divisoria_legenda() {
    if (duas_metades)
        bloco(-lado / 2, lado / 2, divisoria_y - divisoria_e / 2, divisoria_y + divisoria_e / 2, -tampa + mascara, recuo - 0.1);
}

module blocos_abas() {
    for (m = [0, 1]) mirror([0, m, 0]) bloco(-aba_l / 2, aba_l / 2, lado / 2 - 1, lado / 2, -tampa + mascara, 0);
}

module aba() {
    y0 = lado / 2 - 0.1;
    bloco(-aba_l / 2, aba_l / 2, y0 - aba_e, y0, 0, aba_c);
    rotate([90, 0, 90]) linear_extrude(aba_l, center = true)
        polygon([[y0 - 0.1, dente_z], [y0 + dente, dente_z], [y0 + dente, dente_topo], [y0, aba_c], [y0 - 0.1, aba_c]]);
}

module legenda_preto() {
    difference() {
        bloco(-frente / 2, frente / 2, -frente / 2, frente / 2, -tampa, 0);
        bloco(-lado / 2, lado / 2, -lado / 2, lado / 2, -tampa - 1, 1);
    }
    difference() {
        bloco(-lado / 2, lado / 2, -lado / 2, lado / 2, -tampa, -tampa + mascara);
        letras(-tampa - 1, mascara + 1);
    }
    divisoria_legenda();
    blocos_abas();
    for (m = [0, 1]) mirror([0, m, 0]) aba();
}

module legenda_transparente() {
    letras(-tampa, mascara);
    difference() {
        bloco(-lado / 2, lado / 2, -lado / 2, lado / 2, -tampa + mascara, 0);
        divisoria_legenda();
        blocos_abas();
    }
}

module janelas() {
    for (m = [0, 1]) mirror([0, m, 0])
        bloco(-aba_l / 2 - 0.25, aba_l / 2 + 0.25, lado / 2 - 0.1, frente / 2 + 1, dente_z - 0.1, aba_c + 0.1);
}

module ressaltos() {
    for (m = [0, 1]) mirror([m, 0, 0])
        bloco(frente / 2 - 0.1, frente / 2 + ressalto_l, -ressalto_largura / 2, ressalto_largura / 2, comprimento - ressalto_c, comprimento);
}

module perfil_divisoria() {
    e = divisoria_e / 2;
    rotate([90, 0, 90]) linear_extrude(lado + 0.2, center = true)
        polygon([[divisoria_y - 0.2, recuo], [divisoria_y + 0.2, recuo], [divisoria_y + e, recuo + 1.5],
                 [divisoria_y + e, comprimento], [divisoria_y - e, comprimento], [divisoria_y - e, recuo + 1.5]]);
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
        bloco(-frente / 2, frente / 2, -frente / 2, frente / 2, 0, comprimento);
        bloco(-lado / 2, lado / 2, -lado / 2, lado / 2, -1, comprimento + 1);
        janelas();
    }
    ressaltos();
    divisoria_corpo();
}

module gancho() {
    bloco(-4, 4, tubo_externo / 2 - 0.6, tubo_externo / 2 + 0.1, tubo_comprimento - 1, tubo_comprimento);
    bloco(-4, 4, tubo_externo / 2, tubo_externo / 2 + 1.2, tubo_comprimento - 1, tubo_comprimento + suporte_esp + 1.2);
    bloco(-4, 4, tubo_externo / 2 - 0.8, tubo_externo / 2, tubo_comprimento + suporte_esp, tubo_comprimento + suporte_esp + 1.2);
}

module base() {
    difference() {
        translate([-tubo_externo / 2, -tubo_externo / 2, 0]) cube([tubo_externo, tubo_externo, tubo_comprimento]);
        translate([-tubo_interno / 2, -tubo_interno / 2, -1]) cube([tubo_interno, tubo_interno, tubo_comprimento + 2]);
        for (s = [-1, 1])
            translate([s * (tubo_interno / 2 + trilho_l / 2) - trilho_l / 2, -trilho_largura / 2, batente])
                cube([trilho_l, trilho_largura, tubo_comprimento]);
    }
    for (m = [0, 1]) mirror([0, m, 0]) gancho();
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
            bloco(-tubo_externo / 2, tubo_externo / 2, -tubo_externo / 2, tubo_externo / 2, suporte_z, suporte_z + suporte_esp);
            nervuras();
        }
        furos_suporte();
        translate([0, 10, suporte_z + suporte_esp - 0.4]) linear_extrude(1)
            text("CIMA", size = 2, font = fonte, halign = "center", valign = "center");
    }
}

module chave_ref() {
    color("lightgray") bloco(-chave / 2, chave / 2, -chave / 2, chave / 2, chave_z, suporte_z);
    color("black") bloco(-haste_x / 2, haste_x / 2, -haste_y / 2, haste_y / 2, haste_z + pre_carga, chave_z);
    color("gold") for (x = [-pino_passo, 0, pino_passo], y = [-pino_fileiras / 2, pino_fileiras / 2])
        bloco(x - 0.25, x + 0.25, y - 0.2, y + 0.2, suporte_z, suporte_z + pino_c);
}

module leds_ref() {
    for (y = [-led_y, led_y]) translate([0, y, 0]) {
        color("white") translate([0, 0, suporte_z - 3.8]) { cylinder(d = 3, h = 3.8); sphere(d = 3); }
        color("gold") for (x = [-led_pernas / 2, led_pernas / 2])
            bloco(x - 0.25, x + 0.25, -0.25, 0.25, suporte_z, suporte_z + suporte_esp + 3);
    }
}

module painel_ref() {
    color([0.19, 0.21, 0.23, 0.55]) difference() {
        translate([-20, -20, 0]) cube([40, 40, painel]);
        translate([-11.5, -11.5, -1]) cube([23, 23, painel + 2]);
    }
}

module legenda_cores() {
    color("dimgray") legenda_preto();
    color(vidro) legenda_transparente();
}

module teste_folga() {
    folgas = [0.1, 0.15, 0.2, 0.25, 0.3];
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

module montagem(corte = true) {
    difference() {
        union() {
            painel_ref();
            legenda_cores();
            color("dimgray") corpo();
            color("gray") translate([0, 0, painel]) base();
            color("darkslategray") suporte();
            chave_ref();
            leds_ref();
        }
        if (corte) translate([0, -50, -20]) cube([100, 100, 100]);
    }
}

module explodida() {
    legenda_cores();
    color("dimgray") translate([0, 0, 12]) corpo();
    color("gray") translate([0, 0, 40]) base();
    translate([0, 0, 70]) {
        color("darkslategray") suporte();
        chave_ref();
        leds_ref();
    }
}

if (peca == "montagem") montagem(true);
if (peca == "corte") rotate([0, 90, 0]) montagem(true);
if (peca == "frente") legenda_cores();
if (peca == "explodida") explodida();
if (peca == "legenda_preto") translate([0, 0, tampa]) legenda_preto();
if (peca == "legenda_transparente") translate([0, 0, tampa]) legenda_transparente();
if (peca == "corpo") translate([0, 0, comprimento]) rotate([180, 0, 0]) corpo();
if (peca == "base") base();
if (peca == "suporte") translate([0, 0, suporte_z + suporte_esp]) rotate([180, 0, 0]) suporte();
if (peca == "teste") teste_folga();
