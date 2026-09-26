# Instruções para o Claude

## Fluxo de trabalho: merge automático

O dono do repositório **não revisa pull requests nem faz merge manualmente**. Toda alteração pronta deve ir para o `main` sem pedir confirmação:

1. Antes de começar, trazer o `main` para o branch de trabalho com `git merge origin/main`. Não usar rebase nem push forçado.
2. Fazer as alterações e **verificar antes de publicar**:
   - firmware: compilar para o ATmega2560, sem avisos;
   - Python: rodar os scripts ou testes que existirem e o `pyflakes`.
3. Fazer commit e push do branch de trabalho.
4. Abrir o PR contra o `main` e fazer o merge com **squash** logo em seguida.
5. Conferir que o `main` ficou igual ao código verificado e informar o link do PR.

Se a verificação falhar, não fazer o merge: corrigir primeiro ou explicar o que está faltando.

## Convenções

- Conversas, comentários de código, documentação e mensagens de commit em **português**.
- Textos do LCD e da serial em ASCII, sem acentos.
- A arquitetura, o roteiro das fases e as decisões ficam no `README.md`; o protocolo serial, em `docs/protocolo.md`.
