"""Gera a versão caseira da PCB do módulo médio, para fazer por corrosão.

Mesmo esquema da placa de fábrica, com regras de quem faz a placa em casa:
trilhas de pelo menos 0,8 mm, folga de 0,5 mm, ilhas grandes, furos sem
metalização (só resistores, capacitores cerâmicos e vias têm cobre em cima)
e o mínimo de vias. Exporta os PDFs em tamanho real para a transferência
térmica, o mapa de furação e os Gerbers.

Uso: python3 hardware/pcb/modulo_medio_caseira.py [--ses roteamento.ses]

Com --ses, usa um roteamento já pronto do Freerouting em vez de rotear de novo.
Precisa do mesmo que o modulo_medio.py (KiCad 7, Java, Freerouting e xvfb-run).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

import modulo_medio as base
import pcbnew

mm, pt, texto = base.mm, base.pt, base.texto

PASTA = os.path.join(base.RAIZ, 'modulo_medio_caseira')
NOME = 'modulo_medio_caseira'
PRO = os.path.join(PASTA, NOME + '.kicad_pro')
PCB = os.path.join(PASTA, NOME + '.kicad_pcb')
IMPRESSAO = os.path.join(PASTA, 'impressao')

LARGURA, ALTURA = 136.0, 120.0
Y_KA, Y_KB = 6.0, 106.0
Y_A, Y_B = 21.0, 68.0
X_U4, X_U5, X_U2 = 8.0, 42.0, 77.0
X_U6, X_U3, X_U1 = 8.0, 42.0, 87.0
PASSO_R = 3.3

POSICOES = {
    'U4': (X_U4, Y_A, 0), 'U5': (X_U5, Y_A, 0), 'U2': (X_U2, Y_A, 0), 'RN2': (X_U2 + 14.0, Y_A - 2.54, 270),
    'C4': (X_U4 + 1.5, Y_A - 5.5, 0), 'C5': (X_U5 + 1.5, Y_A - 5.5, 0), 'C2': (X_U2 + 1.5, Y_A - 5.5, 0),
    'J1': (103.0, Y_A - 1.0, 0), 'J6': (121.0, Y_A, 0),
    'U6': (X_U6, Y_B, 0), 'U3': (X_U3, Y_B, 0), 'RN3': (X_U3 + 14.0, Y_B - 2.54, 270),
    'RN1': (63.0, Y_B - 2.54, 270), 'SW1': (69.0, Y_B, 0), 'U1': (X_U1, Y_B, 0), 'J2': (104.0, Y_B, 0),
    'C7': (X_U6 + 1.5, Y_B - 5.5, 0), 'C3': (X_U3 + 1.5, Y_B - 5.5, 0), 'C1': (X_U1 + 1.5, Y_B - 5.5, 0),
    'C6': (113.0, 86.0, 0),
}
for banco, (xu, y0) in enumerate(((X_U4, Y_A), (X_U5, Y_A), (X_U6, Y_B))):
    for i in range(8):
        POSICOES['R%d' % (8 * banco + i + 1)] = (xu + 14.0, y0 - 1.0 + PASSO_R * i, 0)
for i in range(6):
    POSICOES['K%d' % (i + 1)] = (12.0 + 20.0 * i, Y_KA, 0)
    POSICOES['K%d' % (i + 7)] = (12.0 + 20.0 * i, Y_KB, 0)

FUROS = [(4.0, 4.0), (LARGURA - 4.0, 4.0), (4.0, ALTURA - 4.0), (LARGURA - 4.0, ALTURA - 4.0)]

ROTULOS = {
    'J2': ['IN12', 'IN13', 'IN14', 'IN15', 'GND'],
    'J6': ['+5V', 'AN_A', 'AN_B', 'AN_C', 'GND'],
}

CLASSES = {
    'Default': {'track_width': 0.8, 'clearance': 0.5, 'via_diameter': 2.0, 'via_drill': 0.8},
    'Power': {'track_width': 1.2, 'clearance': 0.5, 'via_diameter': 2.0, 'via_drill': 0.8},
}

ILHA = 1.9
ILHA_LARGA = 2.2


def so_embaixo(ref):
    return not (ref.startswith('R') and ref[1].isdigit()) and not (ref.startswith('C') and ref != 'C6')


def escrever_projeto():
    modelo = {'bus_width': 12, 'diff_pair_gap': 0.25, 'diff_pair_via_gap': 0.25, 'diff_pair_width': 0.2,
              'line_style': 0, 'microvia_diameter': 0.3, 'microvia_drill': 0.1,
              'pcb_color': 'rgba(0, 0, 0, 0.000)', 'schematic_color': 'rgba(0, 0, 0, 0.000)', 'wire_width': 6}
    projeto = {
        'meta': {'filename': NOME + '.kicad_pro', 'version': 1},
        'board': {'design_settings': {'rule_severities': {'lib_footprint_mismatch': 'ignore'}}},
        'net_settings': {
            'classes': [dict(modelo, name=n, **v) for n, v in CLASSES.items()],
            'meta': {'version': 3},
            'net_colors': None,
            'netclass_assignments': None,
            'netclass_patterns': [{'netclass': 'Power', 'pattern': '+5V'}, {'netclass': 'Power', 'pattern': 'GND'}],
        },
    }
    os.makedirs(PASTA, exist_ok=True)
    with open(PRO, 'w', encoding='utf-8') as f:
        json.dump(projeto, f, indent=2)
        f.write('\n')
    with open(os.path.join(PASTA, NOME + '.kicad_dru'), 'w', encoding='utf-8') as f:
        f.write('(version 1)\n(rule "um raio basta nos pads de GND"\n  (constraint min_resolved_spokes 1))\n')


def ajustar_ilhas(fp, ref):
    embaixo = pcbnew.LSET()
    embaixo.AddLayer(pcbnew.B_Cu)
    embaixo.AddLayer(pcbnew.B_Mask)
    for pad in fp.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_PTH:
            continue
        lado = ILHA_LARGA if ref.startswith('R') and ref[1].isdigit() or ref == 'C6' else ILHA
        pad.SetSize(pcbnew.VECTOR2I(mm(lado), mm(lado)))
        if pad.GetShape() == pcbnew.PAD_SHAPE_OVAL:
            pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        if so_embaixo(ref):
            pad.SetLayerSet(embaixo)


def montar(comps, nets):
    board = pcbnew.NewBoard(PCB)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(mm(1.6))
    ds.m_TrackMinWidth = mm(0.8)
    ds.m_MinClearance = mm(0.5)
    ds.m_ViasMinSize = mm(2.0)
    ds.m_MinThroughDrill = mm(0.8)
    ds.m_CopperEdgeClearance = mm(0.8)
    ds.m_HoleClearance = mm(0.5)
    ds.m_HoleToHoleMin = mm(0.5)
    ds.m_SilkClearance = mm(0.0)

    borda = pcbnew.PCB_SHAPE(board)
    borda.SetShape(pcbnew.SHAPE_T_RECT)
    borda.SetStart(pt(0, 0))
    borda.SetEnd(pt(LARGURA, ALTURA))
    borda.SetLayer(pcbnew.Edge_Cuts)
    borda.SetWidth(mm(0.15))
    board.Add(borda)

    netinfo = {}
    for nome in nets:
        ni = pcbnew.NETINFO_ITEM(board, nome)
        board.Add(ni)
        netinfo[nome] = ni
    net_do_pino = {(ref, pino): nome for nome, nos in nets.items() for ref, pino in nos}

    for ref, c in sorted(comps.items()):
        lib, nome = c['footprint'].split(':')
        fp = pcbnew.FootprintLoad(os.path.join(base.LIBS, lib + '.pretty'), nome)
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
        ajustar_ilhas(fp, ref)
        r = fp.Reference()
        if ref.startswith('R') and ref[1].isdigit():
            r.SetPosition(pt(x + 3.81, y))
            r.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
            r.SetTextThickness(mm(0.12))
        elif ref.startswith('RN'):
            r.SetPosition(pt(x, y - 3.3))
            r.SetTextAngleDegrees(0)
            r.SetTextSize(pcbnew.VECTOR2I(mm(0.9), mm(0.9)))
        elif ref.startswith('U'):
            r.SetPosition(pt(x + 3.81, y + 8.89))
            r.SetTextAngleDegrees(90)
            r.SetTextSize(pcbnew.VECTOR2I(mm(1.2), mm(1.2)))
        elif ref.startswith('K'):
            r.SetPosition(pt(x + 3.75, y + 1.7))
            r.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
            r.SetTextThickness(mm(0.12))
        elif ref.startswith('C') and ref != 'C6':
            r.SetPosition(pt(x + 2.5, y))
            r.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
            r.SetTextThickness(mm(0.12))
        elif ref == 'J1':
            r.SetPosition(pt(x + 1.27, y + 24.0))
        elif ref in ROTULOS:
            r.SetPosition(pt(x, y + 2.54 * (len(ROTULOS[ref]) - 1) + 2.6))

    for i, (x, y) in enumerate(FUROS):
        fp = pcbnew.FootprintLoad(os.path.join(base.LIBS, 'MountingHole.pretty'), 'MountingHole_3.2mm_M3')
        fp.SetFPID(pcbnew.LIB_ID('MountingHole', 'MountingHole_3.2mm_M3'))
        fp.SetReference('H%d' % (i + 1))
        fp.Reference().SetVisible(False)
        fp.SetPosition(pt(x, y))
        board.Add(fp)

    for ref, rotulos in ROTULOS.items():
        x0, y0, _ = POSICOES[ref]
        for k, s in enumerate(rotulos):
            texto(board, s, x0 + 2.0, y0 + 2.54 * k, tam=0.9, just=1)
    texto(board, 'ANALOG', POSICOES['J6'][0], Y_A - 4.0, tam=0.9)
    texto(board, 'BOTOES', POSICOES['J2'][0], Y_B - 3.4, tam=0.9)
    t = texto(board, 'BACKPLANE', POSICOES['J1'][0] + 9.0, Y_A + 9.0, tam=0.9)
    t.SetTextAngleDegrees(90)
    texto(board, 'ETIQUETA', POSICOES['SW1'][0] + 3.8, Y_B - 4.8, tam=0.9)
    texto(board, 'KSP COCKPIT  MODULO MEDIO  CASEIRA  REV 1', LARGURA / 2, 49.0, tam=1.2, grosso=0.18)
    texto(board, 'KORRY: 1 GND  2 BOTAO  3 LED CIMA  4 LED BAIXO', LARGURA / 2, 51.8, tam=0.9)
    texto(board, '220R: EVITE OS 8 LEDS DE UM 595 ACESOS JUNTOS', LARGURA / 2, 54.2, tam=0.9)
    board.SynchronizeNetsAndNetClasses(True)
    return board


def ajustar_dsn(caminho):
    dsn = open(caminho, encoding='utf-8').read()
    regras = ('    (autoroute_settings\n'
              '      (fanout off) (autoroute on) (postroute on) (vias on)\n'
              '      (via_costs 120) (plane_via_costs 5) (start_ripup_costs 100) (start_pass_no 1)\n'
              '      (layer_rule F.Cu (active on) (preferred_direction horizontal)\n'
              '        (preferred_direction_trace_costs 3.0) (against_preferred_direction_trace_costs 6.0))\n'
              '      (layer_rule B.Cu (active on) (preferred_direction vertical)\n'
              '        (preferred_direction_trace_costs 1.0) (against_preferred_direction_trace_costs 1.5))\n'
              '    )\n')
    i = dsn.index('\n  )\n  (placement') + 1
    open(caminho, 'w', encoding='utf-8').write(dsn[:i] + regras + dsn[i:])


def rotear_uma_vez(board):
    with tempfile.TemporaryDirectory() as tmp:
        dsn = os.path.join(tmp, 'placa.dsn')
        ses = os.path.join(tmp, 'placa.ses')
        if not pcbnew.ExportSpecctraDSN(board, dsn):
            sys.exit('falha ao exportar o DSN')
        ajustar_dsn(dsn)
        cmd = ['java', '-jar', base.FREEROUTING, '-de', dsn, '-do', ses, '-mp', '200', '-mt', '1']
        if not os.environ.get('DISPLAY') and shutil.which('xvfb-run'):
            cmd = ['xvfb-run', '-a'] + cmd
        subprocess.run(cmd, check=True, capture_output=True, timeout=5400, cwd=tmp)
        if not os.path.exists(ses):
            sys.exit('o Freerouting nao gerou o SES')
        for t in list(board.GetTracks()):
            board.Remove(t)
        base.importar_ses(board, open(ses, encoding='utf-8').read())


def rotear(board, tentativas=4):
    for _ in range(tentativas):
        rotear_uma_vez(board)
        if base.desconectados(board) == 0:
            return
    sys.exit('o Freerouting deixou %d ligacoes sem rotear' % base.desconectados(board))


def marcar_faces(board):
    cima = texto(board, 'CIMA  KSP MEDIO', 30.0, ALTURA - 2.6, tam=1.5, just=0, camada=pcbnew.F_Cu, grosso=0.3)
    cima.SetTextAngleDegrees(0)
    baixo = texto(board, 'BAIXO  KSP MEDIO', LARGURA - 30.0, ALTURA - 2.6, tam=1.5, just=0, camada=pcbnew.B_Cu, grosso=0.3)
    baixo.SetMirrored(True)


def preencher_gnd(board):
    z = pcbnew.ZONE(board)
    z.SetLayer(pcbnew.B_Cu)
    z.SetNet(board.FindNet('GND'))
    z.SetLocalClearance(mm(0.6))
    z.SetMinThickness(mm(0.6))
    z.SetThermalReliefGap(mm(0.6))
    z.SetThermalReliefSpokeWidth(mm(0.8))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    contorno = z.Outline()
    contorno.NewOutline()
    for x, y in ((1.0, 1.0), (LARGURA - 1.0, 1.0), (LARGURA - 1.0, ALTURA - 1.0), (1.0, ALTURA - 1.0)):
        contorno.Append(mm(x), mm(y))
    board.Add(z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def contar_vias(board):
    return sum(1 for t in board.GetTracks() if t.GetClass() == 'PCB_VIA')


def exportar():
    if os.path.isdir(IMPRESSAO):
        shutil.rmtree(IMPRESSAO)
    os.makedirs(IMPRESSAO)
    pdfs = [
        ('cobre_baixo.pdf', 'B.Cu,Edge.Cuts', []),
        ('cobre_cima_espelhado.pdf', 'F.Cu,Edge.Cuts', ['--mirror']),
        ('montagem.pdf', 'F.Silkscreen,F.Fab,Edge.Cuts', []),
    ]
    for nome, camadas, extra in pdfs:
        cmd = ['kicad-cli', 'pcb', 'export', 'pdf', '--layers', camadas, '--black-and-white', '--drill-shape-opt', '1',
               '-o', os.path.join(IMPRESSAO, nome), PCB] + extra
        subprocess.run(cmd, check=True, capture_output=True)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute',
                        '--excellon-units', 'mm', '--excellon-separate-th', '--generate-map', '--map-format', 'pdf',
                        '-o', tmp + '/', PCB], check=True, capture_output=True)
        for a in os.listdir(tmp):
            if a.endswith('.pdf'):
                shutil.copy(os.path.join(tmp, a), os.path.join(IMPRESSAO, 'furacao_' + a.split('-')[-1].lower()))
        subprocess.run(['kicad-cli', 'pcb', 'export', 'gerbers', '--layers', 'F.Cu,B.Cu,F.Silkscreen,F.Mask,B.Mask,Edge.Cuts',
                        '--no-x2', '--subtract-soldermask', '-o', tmp + '/', PCB], check=True, capture_output=True)
        with zipfile.ZipFile(os.path.join(IMPRESSAO, NOME + '_gerbers.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
            for a in sorted(os.listdir(tmp)):
                if a.endswith('.pdf'):
                    continue
                info = zipfile.ZipInfo(a, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, open(os.path.join(tmp, a), 'rb').read())
    return sorted(os.listdir(IMPRESSAO))


def furos_por_diametro(board):
    contagem = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            d = round(pcbnew.ToMM(pad.GetDrillSize().x), 2)
            if d > 0:
                contagem[d] = contagem.get(d, 0) + 1
    for t in board.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            d = round(pcbnew.ToMM(t.GetDrillValue()), 2)
            contagem[d] = contagem.get(d, 0) + 1
    return dict(sorted(contagem.items()))


def main():
    comps, nets = base.ler_netlist()
    faltando = sorted(set(comps) - set(POSICOES))
    if faltando:
        sys.exit('sem posicao: ' + ', '.join(faltando))
    escrever_projeto()
    board = montar(comps, nets)
    if len(sys.argv) == 3 and sys.argv[1] == '--ses':
        base.importar_ses(board, open(sys.argv[2], encoding='utf-8').read())
        if base.desconectados(board):
            sys.exit('o SES deixa %d ligacoes sem rotear' % base.desconectados(board))
    else:
        rotear(board)
    marcar_faces(board)
    board.Save(PCB)
    board = pcbnew.LoadBoard(PCB)
    preencher_gnd(board)
    board.Save(PCB)
    board = pcbnew.LoadBoard(PCB)
    print(base.drc(board))
    print('vias:', contar_vias(board))
    print('furos (mm: quantidade):', furos_por_diametro(board))
    print('\n'.join(exportar()))


if __name__ == '__main__':
    main()
