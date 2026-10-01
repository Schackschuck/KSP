# Instruções para o Claude

## Fluxo de trabalho: plano e implementação

Para tarefas de programação que não sejam triviais, o agente principal (Opus) planeja e revisa, e o subagente `implementador` (Sonnet, definido em `.claude/agents/implementador.md`) escreve o código:

1. Escrever um plano detalhado em `PLANO.md`, com arquivos, funções, estruturas de dados, casos de borda e testes.
2. Delegar cada etapa do plano ao subagente `implementador`, uma de cada vez.
3. Revisar o diff ao final e corrigir os problemas encontrados. Se o diff mexe numa mensagem do protocolo, chamar o subagente `revisor-protocolo`; se mexe em `firmware/`, o `revisor-firmware`.

Para debug difícil ou mudanças que atravessam o projeto inteiro, o agente principal pode fazer direto, sem delegar.

Este fluxo vem antes do merge automático abaixo: a revisão do diff faz parte da verificação, e o `PLANO.md` é de trabalho, não vai para o commit.

## Fluxo de trabalho: merge automático

O dono do repositório **não revisa pull requests nem faz merge manualmente**. Toda alteração pronta deve ir para o `main` sem pedir confirmação:

1. Antes de começar, trazer o `main` para o branch de trabalho com `git merge origin/main`. Não usar rebase nem push forçado.
2. Fazer as alterações e **verificar antes de publicar** com a skill `/verificar` (`python .claude/skills/verificar/verificar.py`):
   - firmware: compilar para o ATmega2560, sem avisos;
   - Python: rodar os scripts ou testes que existirem e o `pyflakes`.
3. Fazer commit e push do branch de trabalho.
4. Abrir o PR contra o `main` e fazer o merge com **squash** logo em seguida.
5. Conferir que o `main` ficou igual ao código verificado e informar o link do PR.

Se a verificação falhar, não fazer o merge: corrigir primeiro ou explicar o que está faltando. Os passos de 1 a 5 estão na skill `/publicar`.

Um hook (`.claude/hooks/conferir_edicao.py`) roda o `pyflakes` em cada `.py` editado e acusa texto fora do ASCII nas strings de `firmware/`.

## Convenções

- Conversas, documentação e mensagens de commit em **português**.
- **Código gerado sem comentários:** todo código novo ou reescrito (Python, JavaScript, HTML, CSS, C/Arduino) vai sem comentários de linha ou de bloco. As docstrings do Python podem ficar. O que precisar de mais explicação vai para a documentação em `docs/` ou para o `README.md`. O código que já existe não é mexido só para tirar comentários.
- Textos do LCD e da serial em ASCII, sem acentos.
- A arquitetura, o roteiro das fases e as decisões ficam no `README.md`; o protocolo serial, em `docs/protocolo.md`.
- Todo painel segue a identidade visual de `hardware/identidade_visual.md`. Para propor o desenho de um painel, usar a skill `/desenhar-painel`; os desenhos são gerados por `node hardware/desenho/desenhar.js`.
