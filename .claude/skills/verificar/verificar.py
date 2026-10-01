"""Verificação do projeto antes do merge: testes, pyflakes e compilação dos firmwares.

Uso, a partir de qualquer pasta do repositório:
    python .claude/skills/verificar/verificar.py           só o que mudou em relação ao origin/main
    python .claude/skills/verificar/verificar.py --tudo    tudo, mesmo o que não mudou
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
FQBN = "arduino:avr:mega:cpu=atmega2560"
ARDUINO_CLI_IDE = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe"


def rodar(comando, pasta=RAIZ, **kwargs):
    """Roda um comando (por padrão na raiz do repositório) e devolve (código, saída)."""
    r = subprocess.run(comando, cwd=pasta, capture_output=True, text=True, encoding="utf-8", errors="replace", **kwargs)
    return r.returncode, (r.stdout + r.stderr).strip()


def arquivos_mudados():
    """Arquivos diferentes do origin/main: commitados no branch, alterados ou novos."""
    _, base = rodar(["git", "merge-base", "HEAD", "origin/main"])
    _, diff = rodar(["git", "diff", "--name-only", base or "origin/main"])
    _, novos = rodar(["git", "ls-files", "--others", "--exclude-standard"])
    return {linha.strip() for linha in (diff + "\n" + novos).splitlines() if linha.strip()}


def testes_python():
    falhas = []
    for teste in sorted([*RAIZ.glob("bridge/tests/test_*.py"), *RAIZ.glob("scripts/tests/test_*.py")]):
        codigo, saida = rodar([sys.executable, str(teste)], timeout=600)
        if codigo != 0:
            falhas.append(f"{teste.relative_to(RAIZ).as_posix()}:\n{saida[-3000:]}")
    return falhas


def pyflakes():
    pastas = [p for p in ("bridge", "scripts", "firmware", "hardware", ".claude") if (RAIZ / p).exists()]
    codigo, saida = rodar([sys.executable, "-m", "pyflakes", *pastas])
    if "No module named pyflakes" in saida:
        return ["pyflakes não instalado: python -m pip install --user pyflakes"]
    return [saida] if codigo != 0 else []


def achar_arduino_cli():
    return shutil.which("arduino-cli") or (str(ARDUINO_CLI_IDE) if ARDUINO_CLI_IDE.exists() else None)


def compilar_sketch(cli, pasta):
    """Compila um sketch para o Mega; só os avisos dos arquivos do próprio sketch reprovam."""
    codigo, saida = rodar([cli, "compile", "--fqbn", FQBN, "--warnings", "all", str(pasta)], timeout=600)
    nome = pasta.relative_to(RAIZ).as_posix()
    if codigo != 0:
        return [f"{nome} não compilou:\n{saida[-3000:]}"]
    prefixo = str(pasta).replace("\\", "/").lower()
    avisos = [linha for linha in saida.splitlines()
              if "warning:" in linha and linha.replace("\\", "/").lower().startswith(prefixo)]
    if avisos:
        return [f"{nome} compilou com avisos:\n" + "\n".join(avisos)]
    memoria = [linha for linha in saida.splitlines() if linha.startswith(("Sketch uses", "Global variables"))]
    print("  " + nome + ": " + " ".join(memoria))
    return []


def firmware_painel(mudados, tudo):
    cli = achar_arduino_cli()
    if not cli:
        return ["arduino-cli não encontrado (nem no PATH nem no Arduino IDE)"]
    sketches = {RAIZ / "firmware/painel"}
    for ino in RAIZ.glob("firmware/passos/*/*.ino"):
        pasta = ino.parent
        if tudo or any(m.startswith(pasta.relative_to(RAIZ).as_posix() + "/") for m in mudados):
            sketches.add(pasta)
    falhas = []
    for pasta in sorted(sketches):
        falhas += compilar_sketch(cli, pasta)
    return falhas


def firmware_mfd():
    codigo, saida = rodar([sys.executable, "compilar.py"], pasta=RAIZ / "firmware/mfd", timeout=600)
    return [f"firmware/mfd não compilou:\n{saida[-3000:]}"] if codigo != 0 else []


def desenhos():
    if not shutil.which("node"):
        return ["node não encontrado: instale o Node.js para gerar os desenhos (winget install OpenJS.NodeJS.LTS)"]
    codigo, saida = rodar(["node", "hardware/desenho/desenhar.js"], timeout=300)
    return [f"desenhar.js falhou:\n{saida[-3000:]}"] if codigo != 0 else []


def main():
    parser = argparse.ArgumentParser(description="Verifica o projeto antes do merge.")
    parser.add_argument("--tudo", action="store_true", help="verifica tudo, mesmo o que não mudou")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    mudados = arquivos_mudados()
    mudou = lambda prefixo: args.tudo or any(m.startswith(prefixo) for m in mudados)

    etapas = [
        ("Testes Python", True, testes_python),
        ("pyflakes", True, pyflakes),
        ("Firmware do painel (ATmega2560)", True, lambda: firmware_painel(mudados, args.tudo)),
        ("Firmware da mikromedia (LPC2148)", mudou("firmware/mfd/"), firmware_mfd),
        ("Desenhos dos painéis", mudou("hardware/desenho/"), desenhos),
    ]

    reprovou = False
    for nome, rodar_etapa, funcao in etapas:
        if not rodar_etapa:
            print(f"[pulou] {nome}: nada mudou")
            continue
        print(f"[...] {nome}", flush=True)
        falhas = funcao()
        if falhas:
            reprovou = True
            print(f"[FALHOU] {nome}")
            for falha in falhas:
                print("  " + falha.replace("\n", "\n  "))
        else:
            print(f"[ok] {nome}")

    print("\nVERIFICACAO REPROVADA" if reprovou else "\nVERIFICACAO OK")
    sys.exit(1 if reprovou else 0)


if __name__ == "__main__":
    main()
