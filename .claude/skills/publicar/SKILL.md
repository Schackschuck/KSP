---
name: publicar
description: Publica no main o trabalho pronto do branch atual, seguindo o merge automático do CLAUDE.md (merge do origin/main, /verificar, commit em português, push, PR e merge com squash). Use quando a alteração estiver pronta e revisada, ou quando o usuário pedir para publicar, subir ou fazer o merge.
---

# Publicar no main

O dono do repositório não revisa PR nem faz merge na mão: quando a verificação passa, o trabalho vai para o `main` sem pedir confirmação. Nunca use rebase, push forçado, `--no-verify` nem `--amend` em commit publicado.

## 1. Branch de trabalho

- Se estiver no `main`, crie um branch com nome curto em português (por exemplo, `painel-tempo`). As alterações não commitadas vão junto.
- `git fetch origin` e `git merge origin/main`. Se houver conflito, resolva mantendo o trabalho dos dois lados.

## 2. Verificar

Rode a skill `/verificar`. Se reprovar, pare aqui: corrija ou explique o que falta.

## 3. Commit

- Rode `git status` e escolha os arquivos **pelo nome**. Fica fora do commit:
  - o `PLANO.md`, que é de trabalho;
  - a pasta `.history/` e o `*.kicad_prl` do KiCad;
  - os `__pycache__/`;
  - arquivos do usuário que não fazem parte desta tarefa, por exemplo um `.kicad_pro` que o KiCad regravou sozinho.
- A mensagem vai em português, no estilo do `git log`: um título que diz o que muda para o cockpit e, se precisar, um parágrafo com o porquê. No fim, a linha de coautoria da sessão.

## 4. PR e merge

- `git push -u origin <branch>`.
- Abra o PR contra o `main`. O título é o do commit. A descrição em português traz um resumo em tópicos, o resultado da verificação e a linha de atribuição da sessão.
- Faça o merge com **squash** logo em seguida. Use o GitHub MCP (`mcp__github__create_pull_request` e `mcp__github__merge_pull_request`) se estiver disponível; se não, use o `gh` (`gh pr create` e `gh pr merge --squash --delete-branch`).

## 5. Conferir

- `git fetch origin` e `git diff <branch> origin/main --stat`: o `main` tem que ter exatamente o código verificado.
- Volte para o `main` local e traga o merge (`git switch main` e `git merge --ff-only origin/main`), sem perder as alterações locais do usuário.
- Responda com o link do PR e uma linha sobre o que entrou.
