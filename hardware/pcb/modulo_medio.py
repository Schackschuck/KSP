"""Gera a PCB do módulo médio a partir do esquema.

Posiciona as peças, roteia com o Freerouting, preenche o GND nas duas faces,
roda o DRC e exporta os Gerbers e a furação para a fábrica.

Uso (KiCad 7 com o módulo pcbnew do Python, Java e o jar do Freerouting):

    python3 hardware/pcb/modulo_medio.py

O jar vem da variável FREEROUTING_JAR (padrão: /opt/fr/fr.jar). Sem tela,
o Freerouting roda dentro do xvfb-run.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

os.environ.setdefault('KICAD7_FOOTPRINT_DIR', '/usr/share/kicad/footprints')

import pcbnew

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA = os.path.join(RAIZ, 'modulo_medio')
SCH = os.path.join(PASTA, 'modulo_medio.kicad_sch')
PRO = os.path.join(PASTA, 'modulo_medio.kicad_pro')
PCB = os.path.join(PASTA, 'modulo_medio.kicad_pcb')
FAB = os.path.join(PASTA, 'fabricacao')
LIBS = os.environ.get('KICAD7_FOOTPRINT_DIR', '/usr/share/kicad/footprints')
FREEROUTING = os.environ.get('FREEROUTING_JAR', '/opt/fr/fr.jar')

LARGURA, ALTURA = 100.0, 100.0
Y_A, Y_B = 16.0, 58.0
Y_KA, Y_KB = 5.0, 95.0
X_U4, X_U5, X_U2, X_U6, X_U3, X_U1 = 4.0, 27.0, 51.0, 4.0, 27.0, 61.0
PASSO_R = 3.3

POSICOES = {
    'U4': (X_U4, Y_A, 0), 'U5': (X_U5, Y_A, 0), 'U2': (X_U2, Y_A, 0), 'RN2': (X_U2 + 12.0, Y_A - 2.54, 270),
    'C4': (X_U4 + 1.5, Y_A - 4.5, 0), 'C5': (X_U5 + 1.5, Y_A - 4.5, 0), 'C2': (X_U2 + 1.5, Y_A - 4.5, 0),
    'J1': (70.0, Y_A - 1.0, 0), 'J6': (80.0, Y_A, 0),
    'U6': (X_U6, Y_B, 0), 'U3': (X_U3, Y_B, 0), 'RN3': (X_U3 + 12.0, Y_B - 2.54, 270),
    'RN1': (44.0, Y_B - 2.54, 270), 'SW1': (48.0, Y_B, 0), 'U1': (X_U1, Y_B, 0), 'J2': (75.0, Y_B, 0),
    'C7': (X_U6 + 1.5, Y_B - 4.5, 0), 'C3': (X_U3 + 1.5, Y_B - 4.5, 0), 'C1': (X_U1 + 1.5, Y_B - 4.5, 0),
    'C6': (82.0, 80.0, 0),
}
for banco, (xu, y0) in enumerate(((X_U4, Y_A), (X_U5, Y_A), (X_U6, Y_B))):
    for i in range(8):
        POSICOES['R%d' % (8 * banco + i + 1)] = (xu + 12.0, y0 - 1.0 + PASSO_R * i, 0)
for i in range(6):
    POSICOES['K%d' % (i + 1)] = (10.0 + 14.2 * i, Y_KA, 0)
    POSICOES['K%d' % (i + 7)] = (10.0 + 14.2 * i, Y_KB, 0)

FUROS = [(3.5, 3.5), (LARGURA - 3.5, 3.5), (3.5, ALTURA - 3.5), (LARGURA - 3.5, ALTURA - 3.5)]

ROTULOS = {
    'J2': ['IN12', 'IN13', 'IN14', 'IN15', 'GND'],
    'J6': ['+5V', 'AN_A', 'AN_B', 'AN_C', 'GND'],
}
LADO_ROTULO = {'J2': 1, 'J6': 1}

CLASSES = {
    'Default': {'track_width': 0.3, 'clearance': 0.2, 'via_diameter': 0.8, 'via_drill': 0.4},
    'Power': {'track_width': 0.6, 'clearance': 0.25, 'via_diameter': 1.0, 'via_drill': 0.5},
}


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def sexpr(texto):
    pilha, atual, i, n = [], [], 0, len(texto)
    while i < n:
        c = texto[i]
        if c == '(':
            pilha.append(atual)
            atual = []
            i += 1
        elif c == ')':
            feito = atual
            atual = pilha.pop()
            atual.append(feito)
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while texto[j] != '"':
                if texto[j] == '\\':
                    j += 1
                buf.append(texto[j])
                j += 1
            atual.append(''.join(buf))
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not texto[j].isspace() and texto[j] not in '()':
                j += 1
            atual.append(texto[i:j])
            i = j
    return atual[0]


def filhos(no, nome):
    return [c for c in no if isinstance(c, list) and c and c[0] == nome]


def valor(no, nome):
    f = filhos(no, nome)
    return f[0][1] if f else None


def ler_netlist():
    with tempfile.TemporaryDirectory() as tmp:
        saida = os.path.join(tmp, 'modulo_medio.net')
        subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '-o', saida, SCH], check=True, capture_output=True)
        arvore = sexpr(open(saida, encoding='utf-8').read())
    comps = {}
    for c in filhos(filhos(arvore, 'components')[0], 'comp'):
        comps[valor(c, 'ref')] = {'valor': valor(c, 'value'), 'footprint': valor(c, 'footprint')}
    nets = {}
    for n in filhos(filhos(arvore, 'nets')[0], 'net'):
        nets[valor(n, 'name')] = [(valor(no, 'ref'), valor(no, 'pin')) for no in filhos(n, 'node')]
    return comps, nets


def escrever_regras():
    with open(os.path.join(PASTA, 'modulo_medio.kicad_dru'), 'w', encoding='utf-8') as f:
        f.write('(version 1)\n(rule "um raio basta nos pads de GND"\n  (constraint min_resolved_spokes 1))\n')


def escrever_projeto():
    base = {'bus_width': 12, 'diff_pair_gap': 0.25, 'diff_pair_via_gap': 0.25, 'diff_pair_width': 0.2,
            'line_style': 0, 'microvia_diameter': 0.3, 'microvia_drill': 0.1,
            'pcb_color': 'rgba(0, 0, 0, 0.000)', 'schematic_color': 'rgba(0, 0, 0, 0.000)', 'wire_width': 6}
    classes = [dict(base, name=nome, **v) for nome, v in CLASSES.items()]
    projeto = {
        'meta': {'filename': 'modulo_medio.kicad_pro', 'version': 1},
        'net_settings': {
            'classes': classes,
            'meta': {'version': 3},
            'net_colors': None,
            'netclass_assignments': None,
            'netclass_patterns': [{'netclass': 'Power', 'pattern': '+5V'}, {'netclass': 'Power', 'pattern': 'GND'}],
        },
    }
    with open(PRO, 'w', encoding='utf-8') as f:
        json.dump(projeto, f, indent=2)
        f.write('\n')


def texto(board, s, x, y, tam=1.0, just=0, camada=pcbnew.F_SilkS, grosso=0.15):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(pt(x, y))
    t.SetLayer(camada)
    t.SetTextSize(pcbnew.VECTOR2I(mm(tam), mm(tam)))
    t.SetTextThickness(mm(grosso))
    t.SetHorizJustify({-1: pcbnew.GR_TEXT_H_ALIGN_RIGHT, 0: pcbnew.GR_TEXT_H_ALIGN_CENTER, 1: pcbnew.GR_TEXT_H_ALIGN_LEFT}[just])
    board.Add(t)
    return t


def montar(comps, nets):
    board = pcbnew.NewBoard(PCB)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(mm(1.6))
    ds.m_TrackMinWidth = mm(0.2)
    ds.m_MinClearance = mm(0.2)
    ds.m_ViasMinSize = mm(0.6)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_CopperEdgeClearance = mm(0.5)
    ds.m_HoleClearance = mm(0.25)
    ds.m_HoleToHoleMin = mm(0.25)
    ds.m_SilkClearance = mm(0.0)

    borda = pcbnew.PCB_SHAPE(board)
    borda.SetShape(pcbnew.SHAPE_T_RECT)
    borda.SetStart(pt(0, 0))
    borda.SetEnd(pt(LARGURA, ALTURA))
    borda.SetLayer(pcbnew.Edge_Cuts)
    borda.SetWidth(mm(0.1))
    board.Add(borda)

    netinfo = {}
    for nome in nets:
        ni = pcbnew.NETINFO_ITEM(board, nome)
        board.Add(ni)
        netinfo[nome] = ni
    net_do_pino = {}
    for nome, nos in nets.items():
        for ref, pino in nos:
            net_do_pino[(ref, pino)] = nome

    for ref, c in sorted(comps.items()):
        lib, nome = c['footprint'].split(':')
        fp = pcbnew.FootprintLoad(os.path.join(LIBS, lib + '.pretty'), nome)
        if fp is None:
            sys.exit('footprint nao encontrado: ' + c['footprint'])
        fp.SetFPID(pcbnew.LIB_ID(lib, nome))
        fp.SetReference(ref)
        fp.SetValue(c['valor'])
        x, y, rot = POSICOES[ref]
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
        board.Add(fp)
        for pad in fp.Pads():
            nome_net = net_do_pino.get((ref, pad.GetNumber()))
            if nome_net:
                pad.SetNet(netinfo[nome_net])
        if ref.startswith('R') and not ref.startswith('RN'):
            centro = fp.GetPosition() + pcbnew.VECTOR2I(mm(3.81), 0)
            fp.Reference().SetPosition(centro)
            fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
            fp.Reference().SetTextThickness(mm(0.12))
        if ref.startswith('RN'):
            fp.Reference().SetPosition(pt(x, y - 3.3))
            fp.Reference().SetTextAngleDegrees(0)
            fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.9), mm(0.9)))
        if ref.startswith('U'):
            fp.Reference().SetPosition(pt(x + 3.81, y + 8.89))
            fp.Reference().SetTextAngleDegrees(90)
            fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(1.2), mm(1.2)))
        if ref.startswith('K'):
            fp.Reference().SetPosition(pt(x + 3.75, y + 1.7))
            fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
            fp.Reference().SetTextThickness(mm(0.12))
        if ref.startswith('C') and ref != 'C6':
            fp.Reference().SetPosition(pt(x + 2.5, y))
            fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
            fp.Reference().SetTextThickness(mm(0.12))
        if ref == 'J1':
            fp.Reference().SetPosition(pt(x + 1.27, y + 24.0))
        if ref in ROTULOS:
            fp.Reference().SetPosition(pt(x, y + 2.54 * (len(ROTULOS[ref]) - 1) + 2.4))

    for i, (x, y) in enumerate(FUROS):
        fp = pcbnew.FootprintLoad(os.path.join(LIBS, 'MountingHole.pretty'), 'MountingHole_3.2mm_M3')
        fp.SetFPID(pcbnew.LIB_ID('MountingHole', 'MountingHole_3.2mm_M3'))
        fp.SetReference('H%d' % (i + 1))
        fp.Reference().SetVisible(False)
        fp.SetPosition(pt(x, y))
        board.Add(fp)

    for ref, rotulos in ROTULOS.items():
        x0, y0, _ = POSICOES[ref]
        lado = LADO_ROTULO[ref]
        for k, r in enumerate(rotulos):
            texto(board, r, x0 + lado * 1.9, y0 + 2.54 * k, tam=0.9, just=lado)
    texto(board, 'ANALOG', 80.0, Y_A - 3.8, tam=0.9)
    texto(board, 'BOTOES', 75.0, Y_B - 3.2, tam=0.9)
    t = texto(board, 'BACKPLANE', 77.2, Y_A + 9.0, tam=0.9)
    t.SetTextAngleDegrees(90)
    texto(board, 'ETIQUETA', 51.8, Y_B - 4.6, tam=0.9)
    texto(board, 'KSP COCKPIT  MODULO MEDIO  REV 2', LARGURA / 2, 44.2, tam=1.2, grosso=0.18)
    texto(board, 'KORRY: 1 GND  2 BOTAO  3 LED CIMA  4 LED BAIXO', LARGURA / 2, 46.8, tam=0.9)
    texto(board, '220R: EVITE OS 8 LEDS DE UM 595 ACESOS JUNTOS', LARGURA / 2, 49.0, tam=0.9)
    board.SynchronizeNetsAndNetClasses(True)
    return board


def desconectados(board):
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(True)


def rotear(board, tentativas=4):
    for _ in range(tentativas):
        rotear_uma_vez(board)
        if desconectados(board) == 0:
            return
    sys.exit('o Freerouting deixou %d ligacoes sem rotear' % desconectados(board))


def rotear_uma_vez(board):
    with tempfile.TemporaryDirectory() as tmp:
        dsn = os.path.join(tmp, 'placa.dsn')
        ses = os.path.join(tmp, 'placa.ses')
        if not pcbnew.ExportSpecctraDSN(board, dsn):
            sys.exit('falha ao exportar o DSN')
        cmd = ['java', '-jar', FREEROUTING, '-de', dsn, '-do', ses, '-mp', '100', '-mt', '1']
        if not os.environ.get('DISPLAY') and shutil.which('xvfb-run'):
            cmd = ['xvfb-run', '-a'] + cmd
        subprocess.run(cmd, check=True, capture_output=True, timeout=3600, cwd=tmp)
        if not os.path.exists(ses):
            sys.exit('o Freerouting nao gerou o SES')
        for t in list(board.GetTracks()):
            board.Remove(t)
        importar_ses(board, open(ses, encoding='utf-8').read())


def importar_ses(board, conteudo):
    arvore = sexpr(conteudo)
    rotas = filhos(arvore, 'routes')[0]
    res = filhos(rotas, 'resolution')[0]
    escala = {'um': 0.001, 'mm': 1.0, 'mil': 0.0254}[res[1]] / float(res[2])
    camadas = {'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu}
    vias = {}
    for ps in filhos(filhos(rotas, 'library_out')[0], 'padstack'):
        diam = float(filhos(filhos(ps, 'shape')[0], 'circle')[0][2]) * escala
        furo = float(ps[1].split(':')[1].split('_')[0]) / 1000.0
        vias[ps[1]] = (diam, furo)

    def ponto(x, y):
        return pcbnew.VECTOR2I(mm(float(x) * escala), mm(-float(y) * escala))

    for net in filhos(filhos(rotas, 'network_out')[0], 'net'):
        ni = board.FindNet(net[1])
        for fio in filhos(net, 'wire'):
            caminho = filhos(fio, 'path')[0]
            camada, largura, coords = caminho[1], float(caminho[2]) * escala, caminho[3:]
            pts = [ponto(coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2)]
            for a, b in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(a)
                t.SetEnd(b)
                t.SetWidth(mm(largura))
                t.SetLayer(camadas[camada])
                t.SetNet(ni)
                board.Add(t)
        for v in filhos(net, 'via'):
            diam, furo = vias[v[1]]
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(ponto(v[2], v[3]))
            via.SetWidth(mm(diam))
            via.SetDrill(mm(furo))
            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            via.SetNet(ni)
            board.Add(via)


def preencher_gnd(board):
    gnd = board.FindNet('GND')
    for camada in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(camada)
        z.SetNet(gnd)
        z.SetLocalClearance(mm(0.3))
        z.SetMinThickness(mm(0.25))
        z.SetThermalReliefGap(mm(0.5))
        z.SetThermalReliefSpokeWidth(mm(0.5))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        contorno = z.Outline()
        contorno.NewOutline()
        for x, y in ((0.5, 0.5), (LARGURA - 0.5, 0.5), (LARGURA - 0.5, ALTURA - 0.5), (0.5, ALTURA - 0.5)):
            contorno.Append(mm(x), mm(y))
        board.Add(z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def drc(board):
    with tempfile.TemporaryDirectory() as tmp:
        rel = os.path.join(tmp, 'drc.txt')
        pcbnew.WriteDRCReport(board, rel, pcbnew.EDA_UNITS_MILLIMETRES, True)
        return open(rel, encoding='utf-8').read()


def exportar():
    if os.path.isdir(FAB):
        shutil.rmtree(FAB)
    with tempfile.TemporaryDirectory() as tmp:
        camadas = 'F.Cu,B.Cu,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts'
        subprocess.run(['kicad-cli', 'pcb', 'export', 'gerbers', '--layers', camadas, '--no-x2', '--subtract-soldermask',
                        '-o', tmp + '/', PCB], check=True, capture_output=True)
        subprocess.run(['kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute',
                        '--excellon-units', 'mm', '--excellon-separate-th', '-o', tmp + '/', PCB], check=True, capture_output=True)
        os.makedirs(FAB)
        arquivos = sorted(os.listdir(tmp))
        with zipfile.ZipFile(os.path.join(FAB, 'modulo_medio_gerbers.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
            for a in arquivos:
                info = zipfile.ZipInfo(a, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, open(os.path.join(tmp, a), 'rb').read())
    return arquivos


def main():
    comps, nets = ler_netlist()
    faltando = sorted(set(comps) - set(POSICOES))
    if faltando:
        sys.exit('sem posicao: ' + ', '.join(faltando))
    escrever_projeto()
    escrever_regras()
    board = montar(comps, nets)
    rotear(board)
    board.Save(PCB)
    board = pcbnew.LoadBoard(PCB)
    preencher_gnd(board)
    board.Save(PCB)
    board = pcbnew.LoadBoard(PCB)
    relatorio = drc(board)
    print(relatorio)
    arquivos = exportar()
    print('\n'.join(arquivos))


if __name__ == '__main__':
    main()
