"""Gera os STL (legendas, pecas iguais e grades) e as imagens do korry.

Uso, de qualquer pasta:

    python hardware/korry/gerar.py              gera tudo
    python hardware/korry/gerar.py --legendas   so as legendas
    python hardware/korry/gerar.py --pecas      so corpo, base, suporte e teste
    python hardware/korry/gerar.py --grades     so as grades do grades.json
    python hardware/korry/gerar.py --imagens    so as imagens
    python hardware/korry/gerar.py --3mf rcs    a legenda rcs num 3MF de duas cores

O --3mf le os dois STL da legenda ja gerados e nao precisa do OpenSCAD.

Precisa do OpenSCAD no PATH e da fonte B612 Bold instalada. As imagens usam
xvfb-run quando nao ha tela.
"""

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PASTA = Path(__file__).resolve().parent
SCAD = PASTA / "korry.scad"
GRADES = PASTA / "grades.json"
STL = PASTA / "stl"
IMG = PASTA / "img"
TRES_MF = PASTA / "3mf"

CORES_3MF = [("preto", "#1A1A1AFF"), ("transparente", "#E8F0F8FF")]

SAS = [
    ("sas_estab", "ESTAB"),
    ("sas_manobra", "MAN"),
    ("sas_pro", "PRO"),
    ("sas_retro", "RETRO"),
    ("sas_normal", "NRM"),
    ("sas_antinrm", "ANRM"),
    ("sas_rad_fora", "RFORA"),
    ("sas_rad_dentro", "RDENTRO"),
    ("sas_alvo", "ALVO"),
    ("sas_antialvo", "AALVO"),
]

METADES = [
    ("sas", "SAS", "SEM EC"),
    ("rcs", "RCS", "SEM MP"),
    ("fbw", "FBW", "DIRETA"),
]

UNICAS = [
    ("trava_alt", "TRAVA ALT"),
    ("pouso", "POUSO"),
    ("branco", ""),
    ("pro", "PRO"),
    ("nrm", "NRM"),
    ("rad", "RAD"),
    ("paraquedas", "PARAQUEDAS"),
    ("solar", "SOLAR"),
    ("antenas", "ANTENAS"),
    ("carga", "CARGA"),
    ("trem", "TREM"),
    ("freios", "FREIOS"),
    ("luzes", "LUZES"),
    ("jato", "JATO"),
    ("luz", "LUZ"),
    ("mapa", "MAPA"),
    ("iva", "IVA"),
    ("fisico", "FISICO"),
]

LEGENDAS = (
    [(n, "", "", m) for n, m in SAS]
    + [(n, c, b, "") for n, c, b in METADES]
    + [(n, t, "", "") for n, t in UNICAS]
)

PECAS = [
    ("corpo", "korry_corpo.stl"),
    ("base", "korry_base.stl"),
    ("suporte", "korry_suporte.stl"),
    ("teste", "korry_teste.stl"),
]

CAMERA_FRENTE = ["--projection=o", "--viewall", "--autocenter", "--camera=0,0,0,0,180,0,100", "--colorscheme=Tomorrow"]


class Erro(Exception):
    pass


def parametro(nome):
    achado = re.search(rf"^{nome}\s*=\s*([-0-9.]+)\s*;", SCAD.read_text(encoding="utf-8"), re.M)
    if not achado:
        raise Erro(f"parametro {nome} nao encontrado em korry.scad")
    return float(achado.group(1))


def valor(v):
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(valor(i) for i in v) + "]"
    if isinstance(v, float):
        return repr(round(v, 4) + 0.0)
    return str(v)


def openscad(saida, params, extra=(), arquivo=SCAD, tela=False):
    cmd = []
    if tela and not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
        cmd += ["xvfb-run", "-a"]
    cmd += ["openscad", "-o", str(saida)]
    for chave, v in params.items():
        cmd += ["-D", f"{chave}={valor(v)}"]
    cmd += list(extra) + [str(arquivo)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=PASTA)
    if r.returncode != 0:
        raise Erro(f"openscad falhou em {Path(saida).name}:\n{r.stderr.strip()}")
    return r.stderr


def stl_binario(caminho):
    dados = Path(caminho).read_bytes()
    if not dados.startswith(b"solid") or b"facet" not in dados[:2000]:
        return
    texto = dados.decode("ascii")
    numero = r"([-+0-9.eE]+)"
    normais = re.findall(rf"facet normal\s+{numero}\s+{numero}\s+{numero}", texto)
    vertices = re.findall(rf"vertex\s+{numero}\s+{numero}\s+{numero}", texto)
    if len(vertices) != 3 * len(normais):
        raise Erro(f"STL malformado: {Path(caminho).name}")
    saida = bytearray(b"KSP korry".ljust(80, b"\0"))
    saida += struct.pack("<I", len(normais))
    for i, n in enumerate(normais):
        v = vertices[3 * i : 3 * i + 3]
        valores = [float(x) for x in n] + [float(x) for p in v for x in p]
        saida += struct.pack("<12fH", *valores, 0)
    Path(caminho).write_bytes(bytes(saida))


def exportar_stl(saida, params):
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    avisos = openscad(saida, params)
    if "WARNING" in avisos:
        raise Erro(f"avisos do openscad em {saida.name}:\n{avisos.strip()}")
    stl_binario(saida)


def pontos_svg(caminho):
    texto = Path(caminho).read_text(encoding="utf-8")
    achados = re.findall(r"(-?[0-9.]+(?:e[-+]?[0-9]+)?),(-?[0-9.]+(?:e[-+]?[0-9]+)?)", texto)
    return [(float(x), -float(y)) for x, y in achados]


def conferir_legenda(nome, params, em_branco, duas_metades):
    if em_branco:
        return
    lado = parametro("tubo_interno") - 2 * parametro("folga") - 2 * parametro("parede")
    meia_div = parametro("divisoria_e") / 2
    centro_div = parametro("divisoria_y")
    limite = lado / 2 - 0.5
    with tempfile.TemporaryDirectory() as tmp:
        svg = Path(tmp) / "legenda.svg"
        openscad(svg, {**params, "peca": "legenda_2d"})
        pontos = pontos_svg(svg)
    if not pontos:
        raise Erro(f"{nome}: legenda vazia")
    maior_x = max(abs(x) for x, _ in pontos)
    if maior_x > limite + 1e-6:
        raise Erro(f"{nome}: passa da largura util ({maior_x:.2f} mm, limite {limite:.2f} mm)")
    maior_y = max(abs(y) for _, y in pontos)
    if maior_y > limite + 1e-6:
        raise Erro(f"{nome}: passa da altura util ({maior_y:.2f} mm, limite {limite:.2f} mm)")
    if duas_metades:
        acima = [y for _, y in pontos if y > centro_div]
        abaixo = [y for _, y in pontos if y < centro_div]
        if not acima or not abaixo:
            raise Erro(f"{nome}: falta o texto de cima ou o de baixo")
        if min(acima) < centro_div + meia_div - 1e-6:
            raise Erro(f"{nome}: o texto de cima invade a divisoria ({min(acima):.2f} mm)")
        if max(abaixo) > centro_div - meia_div + 1e-6:
            raise Erro(f"{nome}: o texto de baixo invade a divisoria ({max(abaixo):.2f} mm)")


def gerar_legenda(item):
    nome, cima, baixo, modo = item
    params = {"texto_cima": cima, "texto_baixo": baixo, "modo_sas": modo}
    em_branco = cima == "" and baixo == "" and modo == ""
    conferir_legenda(nome, params, em_branco, baixo != "" and modo == "")
    for cor in ("preto", "transparente"):
        exportar_stl(STL / "legendas" / f"{nome}_{cor}.stl", {**params, "peca": f"legenda_{cor}"})
    return nome


def gerar_peca(item):
    peca, arquivo = item
    exportar_stl(STL / arquivo, {"peca": peca})
    return arquivo


def centros_scad(korry, pontos):
    cx = sum(p[0] for p in korry) / len(korry)
    cy = sum(p[1] for p in korry) / len(korry)
    return [[-(p[0] - cx), -(p[1] - cy)] for p in pontos]


def parametros_grade(g):
    return {
        "peca": "grade",
        "celulas": centros_scad(g["korry"], g["korry"]),
        "furos": centros_scad(g["korry"], g["parafusos"]),
    }


def gerar_grade(g):
    arquivo = STL / "grades" / f"grade_{g['nome']}.stl"
    exportar_stl(arquivo, parametros_grade(g))
    return arquivo.name


def ler_stl(caminho):
    dados = Path(caminho).read_bytes()
    if dados.startswith(b"solid") and b"facet" in dados[:2000]:
        raise Erro(f"{Path(caminho).name} esta em texto: gerar de novo com o gerar.py")
    (n,) = struct.unpack_from("<I", dados, 80)
    if len(dados) != 84 + 50 * n:
        raise Erro(f"STL malformado: {Path(caminho).name}")
    indices = {}
    vertices = []
    triangulos = []
    for i in range(n):
        v = struct.unpack_from("<9f", dados, 84 + 50 * i + 12)
        tri = []
        for k in range(3):
            p = v[3 * k : 3 * k + 3]
            if p not in indices:
                indices[p] = len(vertices)
                vertices.append(p)
            tri.append(indices[p])
        if len(set(tri)) == 3:
            triangulos.append(tri)
    return vertices, triangulos


def malha_3mf(id_objeto, nome, indice_cor, vertices, triangulos):
    linhas = [f'  <object id="{id_objeto}" name="{nome}" type="model" pid="1" pindex="{indice_cor}">', "   <mesh>", "    <vertices>"]
    linhas += [f'     <vertex x="{x:.6g}" y="{y:.6g}" z="{z:.6g}"/>' for x, y, z in vertices]
    linhas += ["    </vertices>", "    <triangles>"]
    linhas += [f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in triangulos]
    linhas += ["    </triangles>", "   </mesh>", "  </object>"]
    return linhas


def modelo_3mf(nome, partes):
    linhas = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<model unit="millimeter" xml:lang="pt-BR" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
        f' <metadata name="Title">korry {nome}</metadata>',
        " <resources>",
        '  <basematerials id="1">',
    ]
    linhas += [f'   <base name="{cor}" displaycolor="{rgba}"/>' for cor, rgba in CORES_3MF]
    linhas.append("  </basematerials>")
    for i, (cor, vertices, triangulos) in enumerate(partes):
        linhas += malha_3mf(i + 2, f"{nome}_{cor}", i, vertices, triangulos)
    conjunto = len(partes) + 2
    linhas.append(f'  <object id="{conjunto}" name="legenda_{nome}" type="model">')
    linhas.append("   <components>")
    linhas += [f'    <component objectid="{i + 2}"/>' for i in range(len(partes))]
    linhas += ["   </components>", "  </object>", " </resources>", " <build>"]
    linhas += [f'  <item objectid="{conjunto}"/>', " </build>", "</model>"]
    return "\n".join(linhas) + "\n"


def gerar_3mf(nome):
    partes = []
    for cor, _ in CORES_3MF:
        stl = STL / "legendas" / f"{nome}_{cor}.stl"
        if not stl.exists():
            raise Erro(f"falta {stl.name}: gerar as legendas antes")
        partes.append((cor, *ler_stl(stl)))
    saida = TRES_MF / f"legenda_{nome}.3mf"
    TRES_MF.mkdir(exist_ok=True)
    tipos = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        "</Types>\n"
    )
    relacoes = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        "</Relationships>\n"
    )
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipos)
        z.writestr("_rels/.rels", relacoes)
        z.writestr("3D/3dmodel.model", modelo_3mf(nome, partes))
    return saida.name


def em_paralelo(funcao, itens, rotulo):
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as ex:
        for nome in ex.map(funcao, itens):
            print(f"  {rotulo}: {nome}", flush=True)


def gerar_legendas():
    print(f"Legendas ({len(LEGENDAS)})")
    em_paralelo(gerar_legenda, LEGENDAS, "legenda")


def gerar_pecas():
    print("Pecas iguais para todos")
    em_paralelo(gerar_peca, PECAS, "peca")


def gerar_grades():
    grades = json.loads(GRADES.read_text(encoding="utf-8"))
    print(f"Grades ({len(grades)})")
    em_paralelo(gerar_grade, grades, "grade")


def folha_scad(colunas, passo):
    linhas = ["fonte = \"B612:style=Bold\";"]
    for i, (nome, _, _, _) in enumerate(LEGENDAS):
        x = -(i % colunas) * passo
        y = -(i // colunas) * passo
        base = (STL / "legendas" / nome).as_posix()
        linhas.append(f"translate([{x}, {y}, 0]) {{")
        linhas.append(f"  color([0.41, 0.41, 0.41]) import(\"{base}_preto.stl\");")
        linhas.append(f"  color([0.85, 0.92, 1]) import(\"{base}_transparente.stl\");")
        linhas.append(
            f"  color([0.2, 0.2, 0.2]) translate([0, -14.2, 0]) mirror([1, 0, 0]) "
            f"linear_extrude(0.4) text(\"{nome}\", size = 1.8, font = fonte, halign = \"center\", valign = \"center\");"
        )
        linhas.append("}")
    return "\n".join(linhas) + "\n"


def gerar_imagens():
    print("Imagens")
    IMG.mkdir(exist_ok=True)
    openscad(IMG / "frente.png", {"peca": "frente"}, ["--imgsize=600,600", *CAMERA_FRENTE], tela=True)
    openscad(IMG / "corte.png", {"peca": "corte"}, ["--imgsize=800,560", *CAMERA_FRENTE], tela=True)
    openscad(
        IMG / "explodida.png",
        {"peca": "explodida"},
        ["--imgsize=800,600", "--viewall", "--autocenter", "--camera=0,0,0,-25,210,0,200", "--colorscheme=Tomorrow"],
        tela=True,
    )
    colunas, passo = 8, 28
    linhas = -(-len(LEGENDAS) // colunas)
    with tempfile.TemporaryDirectory() as tmp:
        folha = Path(tmp) / "folha.scad"
        folha.write_text(folha_scad(colunas, passo), encoding="utf-8")
        largura = 200 * colunas
        altura = int(largura * linhas / colunas * 1.05)
        centro = f"{-(colunas - 1) * passo / 2},{-(linhas - 1) * passo / 2},0"
        camera = ["--projection=o", f"--camera={centro},0,180,0,400", "--colorscheme=Tomorrow"]
        openscad(IMG / "legendas.png", {}, [f"--imgsize={largura},{altura}", *camera], arquivo=folha, tela=True)
    grades = {g["nome"]: g for g in json.loads(GRADES.read_text(encoding="utf-8"))}
    params = parametros_grade(grades["voo_sas"])
    openscad(
        IMG / "grade.png",
        params,
        ["--imgsize=1000,600", "--viewall", "--autocenter", "--camera=0,0,0,-130,0,20,300", "--colorscheme=Tomorrow"],
        tela=True,
    )
    for nome in ("frente", "corte", "explodida", "legendas", "grade"):
        print(f"  imagem: {nome}.png")


def main():
    ap = argparse.ArgumentParser(description="Gera os STL e as imagens do korry.")
    ap.add_argument("--legendas", action="store_true", help="so as 31 legendas")
    ap.add_argument("--pecas", action="store_true", help="so corpo, base, suporte e teste")
    ap.add_argument("--grades", action="store_true", help="so as grades do grades.json")
    ap.add_argument("--imagens", action="store_true", help="so as imagens")
    ap.add_argument("--3mf", dest="tres_mf", nargs="+", metavar="NOME", help="legendas num 3MF de duas cores, pelos STL ja gerados")
    a = ap.parse_args()
    if a.tres_mf:
        nomes = {n for n, _, _, _ in LEGENDAS}
        try:
            for nome in a.tres_mf:
                if nome not in nomes:
                    raise Erro(f"legenda desconhecida: {nome}")
                print(f"  3mf: {gerar_3mf(nome)}")
        except Erro as e:
            print(f"ERRO: {e}", file=sys.stderr)
            return 1
        return 0
    tudo = not (a.legendas or a.pecas or a.grades or a.imagens)
    if not shutil.which("openscad"):
        print("openscad nao encontrado no PATH", file=sys.stderr)
        return 1
    try:
        if tudo or a.legendas:
            gerar_legendas()
        if tudo or a.pecas:
            gerar_pecas()
        if tudo or a.grades:
            gerar_grades()
        if tudo or a.imagens:
            gerar_imagens()
    except Erro as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    total = sum(f.stat().st_size for f in STL.rglob("*.stl"))
    print(f"STL: {total / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
