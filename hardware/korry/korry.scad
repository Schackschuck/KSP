peca = "montagem";
texto_cima = "SAS";
texto_baixo = "SEM EC";
fonte = "B612:style=Bold";
folga = 0.2;

frente = 22.5;
parede = 1.0;
tampa = 3;
mascara = 0.6;
comprimento = 21;
passo = 2.54;
divisoria_y = -passo / 2;
divisoria_e = 1.0;
pino_d = 3;
ressalto_l = 1.4;
ressalto_c = 2;
ressalto_largura = 6;
letra_cima = 3;
letra_baixo = 2.4;
caixa_l = 15;
caixa_a = 5.6;
caixa_traco = 0.6;

tubo_interno = frente + 2 * folga;
tubo_parede = 1.2;
tubo_externo = tubo_interno + 2 * tubo_parede;
tubo_comprimento = 16;
trilho_l = ressalto_l + 0.3;
trilho_largura = ressalto_largura + 0.6;
batente = 13;

placa = 10 * passo;
placa_esp = 1.6;
tatil_h = 5;

$fn = 48;

duas_metades = texto_baixo != "";
lado = frente - 2 * parede;
centro_cima = duas_metades ? (frente / 2 - parede + divisoria_y + divisoria_e / 2) / 2 : 0;
centro_baixo = (-frente / 2 + parede + divisoria_y - divisoria_e / 2) / 2;

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

module divisoria() {
    difference() {
        if (duas_metades)
            translate([-frente / 2, divisoria_y - divisoria_e / 2, mascara]) cube([frente, divisoria_e, comprimento - mascara]);
        else
            translate([-4, divisoria_y - divisoria_e / 2, comprimento - 9]) cube([8, divisoria_e, 9]);
        translate([-3.6, divisoria_y - 2, comprimento - 3]) cube([7.2, 4, 4]);
    }
}

module corpo_preto() {
    difference() {
        translate([-frente / 2, -frente / 2, 0]) cube([frente, frente, comprimento]);
        translate([-lado / 2, -lado / 2, mascara]) cube([lado, lado, comprimento]);
        translate([0, 0, -1]) linear_extrude(mascara + 1) intersection() { legenda(); square(lado, center = true); }
    }
    divisoria();
    translate([0, divisoria_y, comprimento - 9]) cylinder(d = pino_d, h = 4.8);
    for (s = [-1, 1])
        translate([s * (frente / 2 + ressalto_l / 2) - ressalto_l / 2, -ressalto_largura / 2, comprimento - ressalto_c])
            cube([ressalto_l, ressalto_largura, ressalto_c]);
}

module corpo_transparente() {
    linear_extrude(mascara) intersection() { legenda(); square(lado, center = true); }
    difference() {
        translate([-lado / 2, -lado / 2, mascara]) cube([lado, lado, tampa - mascara]);
        divisoria();
    }
}

module base() {
    difference() {
        translate([-tubo_externo / 2, -tubo_externo / 2, 0]) cube([tubo_externo, tubo_externo, tubo_comprimento]);
        translate([-tubo_interno / 2, -tubo_interno / 2, -1]) cube([tubo_interno, tubo_interno, tubo_comprimento + 2]);
        for (s = [-1, 1])
            translate([s * (tubo_interno / 2 + trilho_l / 2) - trilho_l / 2, -trilho_largura / 2, batente])
                cube([trilho_l, trilho_largura, tubo_comprimento]);
    }
    for (s = [-1, 1]) translate([-4, s * (tubo_externo / 2) - (s > 0 ? 0 : 1.2), tubo_comprimento - 0.01]) gancho(s);
}

module gancho(s) {
    cube([8, 1.2, placa_esp + 1.2]);
    translate([0, s > 0 ? -0.8 : 1.2, placa_esp]) cube([8, 0.8, 1.2]);
}

module placa_ref() {
    color("darkgreen") translate([-placa / 2, -placa / 2, 0]) cube([placa, placa, placa_esp]);
    color("dimgray") translate([-3, divisoria_y - 3, -3.5]) cube([6, 6, 3.5]);
    color("black") translate([0, divisoria_y, -tatil_h]) cylinder(d = 3.5, h = 1.5);
    for (y = [2.5 * passo, -2.5 * passo]) color("white") translate([0, y, -5.3]) { cylinder(d = 3, h = 5.3); sphere(d = 3); }
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

module painel_ref() {
    color([0.19, 0.21, 0.23, 0.55]) difference() {
        translate([-20, -20, 0]) cube([40, 40, 3]);
        translate([-11.5, -11.5, -1]) cube([23, 23, 5]);
    }
}

module montagem(corte = true) {
    difference() {
        union() {
            painel_ref();
            translate([0, 0, -tampa]) { color("dimgray") corpo_preto(); color([0.85, 0.92, 1]) corpo_transparente(); }
            color("gray") translate([0, 0, 3]) base();
            translate([0, 0, 3 + tubo_comprimento]) placa_ref();
        }
        if (corte) translate([0, -50, -20]) cube([100, 100, 100]);
    }
}

if (peca == "montagem") montagem(true);
if (peca == "corte") rotate([0, 90, 0]) montagem(true);
if (peca == "frente") { color("dimgray") corpo_preto(); color([0.85, 0.92, 1]) corpo_transparente(); }
if (peca == "explodida") {
    color("dimgray") corpo_preto();
    color([0.85, 0.92, 1]) corpo_transparente();
    color("gray") translate([0, 0, 35]) base();
    translate([0, 0, 65]) placa_ref();
}
if (peca == "preto") corpo_preto();
if (peca == "transparente") corpo_transparente();
if (peca == "base") base();
if (peca == "teste") teste_folga();
