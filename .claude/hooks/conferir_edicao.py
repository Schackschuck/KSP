"""Hook PostToolUse (Edit|Write): confere o arquivo que o Claude acabou de mexer.

- .py: roda o pyflakes no arquivo.
- .ino, .c, .cpp, .h em firmware/: acusa string ou caractere fora do ASCII (textos da serial e do LCD).

Sai com código 2 e a lista de problemas no stderr, para o Claude corrigir na hora.
"""

import json
import subprocess
import sys
from pathlib import Path

EXTENSOES_FIRMWARE = {".ino", ".c", ".cpp", ".h"}


def problemas_pyflakes(arquivo):
    r = subprocess.run([sys.executable, "-m", "pyflakes", str(arquivo)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    saida = (r.stdout + r.stderr).strip()
    if "No module named pyflakes" in saida:
        return []
    return saida.splitlines() if r.returncode != 0 else []


def literais(texto):
    """Devolve (linha, literal) de cada string ou caractere do código C, pulando os comentários."""
    i, linha, n = 0, 1, len(texto)
    while i < n:
        c = texto[i]
        if texto.startswith("//", i):
            fim = texto.find("\n", i)
            i = n if fim < 0 else fim
        elif texto.startswith("/*", i):
            fim = texto.find("*/", i + 2)
            fim = n if fim < 0 else fim + 2
            linha += texto.count("\n", i, fim)
            i = fim
        elif c in "\"'":
            inicio, i = i, i + 1
            while i < n and texto[i] not in (c, "\n"):
                i += 2 if texto[i] == "\\" else 1
            i += 1
            yield linha, texto[inicio:i]
        else:
            linha += c == "\n"
            i += 1


def problemas_ascii(arquivo):
    texto = arquivo.read_text(encoding="utf-8", errors="replace")
    return [f"{arquivo.name}:{numero}: texto fora do ASCII {literal} (serial e LCD sem acentos)"
            for numero, literal in literais(texto) if any(ord(c) > 127 for c in literal)]


def main():
    try:
        evento = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    caminho = (evento.get("tool_input") or {}).get("file_path")
    if not caminho:
        return 0
    arquivo = Path(caminho)
    if not arquivo.is_file():
        return 0

    problemas = []
    if arquivo.suffix == ".py":
        problemas = problemas_pyflakes(arquivo)
    elif arquivo.suffix in EXTENSOES_FIRMWARE and "firmware" in arquivo.resolve().parts:
        problemas = problemas_ascii(arquivo)

    if problemas:
        sys.stderr.reconfigure(encoding="utf-8")
        print("\n".join(problemas), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
