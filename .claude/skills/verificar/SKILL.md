---
name: verificar
description: Roda a verificação do projeto KSP antes de publicar (testes Python, pyflakes, firmware do Mega compilado sem avisos, firmware da mikromedia e desenhos dos painéis, se mudaram). Use antes de qualquer commit que vá para o main, depois de cada etapa do implementador, ou quando o usuário pedir para verificar ou testar o projeto.
---

# Verificar o projeto

É o passo 2 do fluxo de merge automático do `CLAUDE.md`. Se reprovar, **não publique**: corrija primeiro ou explique o que falta.

## Rodar

Da raiz do repositório:

```
python .claude/skills/verificar/verificar.py
```

Com `--tudo`, verifica também as partes que não mudaram em relação ao `origin/main`. Use quando o argumento da skill for `tudo`.

## O que ele faz

| Etapa | Quando | Comando |
|---|---|---|
| Testes Python | sempre | cada `bridge/tests/test_*.py` e `scripts/tests/test_*.py`, um por vez |
| pyflakes | sempre | `python -m pyflakes bridge scripts firmware hardware .claude` |
| Firmware do painel | sempre (e os `firmware/passos/` que mudaram) | `arduino-cli compile --fqbn arduino:avr:mega:cpu=atmega2560 --warnings all` |
| Firmware da mikromedia | se `firmware/mfd/` mudou | `python compilar.py` (precisa do LLVM) |
| Desenhos dos painéis | se `hardware/desenho/` mudou | `node hardware/desenho/desenhar.js` (precisa do Node.js) |

Só os avisos nos arquivos do próprio sketch reprovam o firmware. Os avisos das bibliotecas instaladas (por exemplo, a `LiquidCrystal_I2C`) ficam de fora. O `arduino-cli` é procurado no PATH e, se não estiver lá, dentro do Arduino IDE.

## Depois

- **VERIFICACAO OK:** diga em uma linha o que passou, com o uso de flash e de RAM do Mega que o script mostra.
- **VERIFICACAO REPROVADA:** leia a falha, corrija na causa e rode de novo. Se faltar uma ferramenta (LLVM, Node.js, pyflakes), diga qual e como instalar, em vez de pular a etapa.
