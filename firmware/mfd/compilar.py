"""Compila o firmware da tela multifunção e gera mfd.hex, pronto para o Flash Magic.

Usa o LLVM (clang, ld.lld e llvm-objcopy), que compila para o ARM7 do
LPC2148 sem instalar mais nada. No Windows: winget install LLVM.LLVM.

O .hex já sai com a soma de verificação dos vetores, que o bootloader do
LPC2148 confere antes de rodar o programa.

Uso, a partir desta pasta:
    python compilar.py
    python compilar.py --llvm "C:\\Program Files\\LLVM\\bin"
"""

import argparse
import os
import shutil
import struct
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
FONTES = [
    "inicio.s",
    "main.c",
    "mfd.c",
    "navball.c",
    "desenho.c",
    "lcd.c",
    "serial.c",
    "toque.c",
    "ajuste.c",
    "relogio.c",
    "texto.c",
    "tabelas.c",
    "suporte.c",
]
ALVO = ["--target=armv4t-none-eabi", "-mcpu=arm7tdmi", "-marm", "-mfloat-abi=soft"]
AVISOS = ["-Wall", "-Wextra", "-Werror"]
OTIMIZACAO = ["-O2", "-ffreestanding", "-ffunction-sections", "-fdata-sections"]
RAM_FIM = 0x40007FE0
PILHA_MINIMA = 3072
PASTA_LLVM_WINDOWS = r"C:\Program Files\LLVM\bin"


def achar(programa, pasta):
    """O caminho do programa do LLVM, na pasta dada, no PATH ou na pasta padrão do Windows."""
    candidatos = [pasta] if pasta else []
    candidatos.append(None)
    candidatos.append(PASTA_LLVM_WINDOWS)
    for lugar in candidatos:
        caminho = shutil.which(programa, path=lugar)
        if caminho:
            return caminho
    sys.exit(f"Não achei o {programa}. Instale o LLVM (winget install LLVM.LLVM) ou use --llvm <pasta>.")


def rodar(comando, mostrar=True):
    resultado = subprocess.run(comando, capture_output=True, text=True)
    saida = (resultado.stdout + resultado.stderr).strip()
    if resultado.returncode != 0:
        print(saida)
        sys.exit("A compilação falhou.")
    if saida and mostrar:
        print(saida)
    return saida


def simbolos(nm, elf):
    tabela = {}
    for linha in rodar([nm, elf], mostrar=False).splitlines():
        partes = linha.split()
        if len(partes) == 3:
            tabela[partes[2]] = int(partes[0], 16)
    return tabela


def com_soma_dos_vetores(binario):
    """Grava na posição 0x14 o valor que faz os 8 vetores somarem zero."""
    vetores = list(struct.unpack_from("<8I", binario, 0))
    vetores[5] = 0
    vetores[5] = (-sum(vetores)) & 0xFFFFFFFF
    return struct.pack("<8I", *vetores) + binario[32:]


def registro(tipo, endereco, dados):
    corpo = bytes([len(dados), (endereco >> 8) & 0xFF, endereco & 0xFF, tipo]) + dados
    return ":" + corpo.hex().upper() + f"{(-sum(corpo)) & 0xFF:02X}"


def intel_hex(binario):
    linhas = []
    bloco_atual = -1
    for inicio in range(0, len(binario), 16):
        bloco = inicio >> 16
        if bloco != bloco_atual:
            linhas.append(registro(4, 0, struct.pack(">H", bloco)))
            bloco_atual = bloco
        linhas.append(registro(0, inicio & 0xFFFF, binario[inicio:inicio + 16]))
    linhas.append(registro(1, 0, b""))
    return "\n".join(linhas) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Compila o firmware da tela multifunção (LPC2148).")
    parser.add_argument("--llvm", help="pasta com clang, ld.lld e llvm-objcopy")
    args = parser.parse_args()

    clang = achar("clang", args.llvm)
    objcopy = achar("llvm-objcopy", args.llvm)
    nm = achar("llvm-nm", args.llvm)
    obra = os.path.join(AQUI, "obra")
    os.makedirs(obra, exist_ok=True)

    objetos = []
    for fonte in FONTES:
        objeto = os.path.join(obra, os.path.splitext(fonte)[0] + ".o")
        opcoes = [] if fonte.endswith(".s") else [*AVISOS, *OTIMIZACAO]
        rodar([clang, *ALVO, *opcoes, "-c", os.path.join(AQUI, fonte), "-o", objeto])
        objetos.append(objeto)

    elf = os.path.join(obra, "mfd.elf")
    rodar([
        clang, *ALVO, "-nostdlib", "-fuse-ld=lld",
        f"-Wl,-T,{os.path.join(AQUI, 'lpc2148.ld')}", "-Wl,--gc-sections",
        *objetos, "-o", elf,
    ])

    tabela = simbolos(nm, elf)
    pilha = RAM_FIM - tabela["_bss_fim"]
    if pilha < PILHA_MINIMA:
        sys.exit(f"Sobram só {pilha} bytes de RAM para a pilha (mínimo {PILHA_MINIMA}).")

    binario_caminho = os.path.join(obra, "mfd.bin")
    rodar([objcopy, "-O", "binary", elf, binario_caminho])
    with open(binario_caminho, "rb") as f:
        binario = com_soma_dos_vetores(f.read())
    with open(os.path.join(AQUI, "mfd.hex"), "w", encoding="ascii", newline="\n") as f:
        f.write(intel_hex(binario))

    print(f"mfd.hex gerado: {len(binario)} bytes de flash, {pilha} bytes de RAM livres para a pilha.")


if __name__ == "__main__":
    main()
