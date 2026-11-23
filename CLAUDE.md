# Instruções para o Claude

## Fluxo de trabalho: plano e implementação

Para tarefas de programação que não sejam triviais, o agente principal (Opus) planeja e revisa, e o subagente `implementador` (Sonnet, definido em `.claude/agents/implementador.md`) escreve o código:

1. Escrever um plano detalhado em `PLANO.md`, com arquivos, funções, estruturas de dados, casos de borda e testes.
2. Delegar cada etapa do plano ao subagente `implementador`, uma de cada vez.
3. Revisar o diff ao final e corrigir os problemas encontrados. Se o diff mexe numa mensagem do protocolo, chamar o subagente `revisor-protocolo`; se mexe em `firmware/`, o `revisor-firmware`.

Para debug difícil ou mudanças que atravessam o projeto inteiro, o agente principal pode fazer direto, sem delegar.

Este fluxo vem antes do merge automático abaixo: a revisão do diff faz parte da verificação, e o `PLANO.md` é de trabalho, não vai para o commit.

## Branch de trabalho: `dev`

Todo trabalho é feito no branch **`dev`**, e só nele. Isso vale mesmo quando o ambiente da sessão indica outro branch: as sessões na nuvem recebem um branch `claude/...` próprio, mas o dono do repositório autoriza o push no `dev`, e o branch `claude/...` não é usado nem enviado ao GitHub.

No começo de cada sessão, antes de mexer em qualquer arquivo:

1. `git fetch origin`.
2. Se o `dev` não existe no GitHub, que é o normal, criar a partir do `main`: `git switch -c dev origin/main`. O GitHub apaga o `dev` sozinho depois de cada merge (*Automatically delete head branches*, nas configurações do repositório).
3. Se o `dev` existe: `git switch dev` (numa sessão nova, `git switch -c dev origin/dev`) e `git merge origin/main`. Depois disso:
   - se o `dev` ficou igual ao `main` (`git diff origin/main` vazio), é um `dev` antigo que já entrou, e o trabalho segue normalmente;
   - se ficou diferente, é trabalho de outro chat que ainda não foi publicado: avisar o usuário e perguntar antes de continuar em cima dele, sem descartar nada.

Durante o trabalho:

- Nunca usar rebase, push forçado nem apagar o `dev`.
- Se o push for recusado porque o `dev` andou (outro chat mandou commits), fazer `git fetch origin` e `git merge origin/dev`, verificar de novo e mandar outra vez.
- O PR é sempre do `dev` contra o `main`. Se já houver um PR aberto do `dev`, usar o mesmo.
- Dois chats ao mesmo tempo dividem o mesmo `dev`. Por isso o merge confere que o PR ainda está no commit verificado (veja a skill `/publicar`).

## Fluxo de trabalho: merge automático

O dono do repositório **não revisa pull requests nem faz merge manualmente**. Toda alteração pronta deve ir para o `main` sem pedir confirmação:

1. Antes de começar, preparar o `dev` como na seção acima, com o `main` trazido por `git merge origin/main`. Não usar rebase nem push forçado.
2. Fazer as alterações e **verificar antes de publicar** com a skill `/verificar` (`python .claude/skills/verificar/verificar.py`):
   - firmware: compilar para o ATmega2560, sem avisos;
   - Python: rodar os scripts ou testes que existirem e o `pyflakes`.
3. Fazer commit e push do `dev`.
4. Abrir o PR do `dev` contra o `main` e fazer o merge com **squash** logo em seguida.
5. Conferir que o `main` ficou igual ao código verificado e informar o link do PR.

Se a verificação falhar, não fazer o merge: corrigir primeiro ou explicar o que está faltando. Os passos de 1 a 5 estão na skill `/publicar`.

Um hook (`.claude/hooks/conferir_edicao.py`) roda o `pyflakes` em cada `.py` editado e acusa texto fora do ASCII nas strings de `firmware/`.

## Convenções

- Conversas, documentação e mensagens de commit em **português**. A exceção é o `README.md`, a vitrine do repositório em inglês: ele e o `README.pt-BR.md` têm o mesmo conteúdo, e o que muda num muda também no outro.
- **Código gerado sem comentários:** todo código novo ou reescrito (Python, JavaScript, HTML, CSS, C/Arduino) vai sem comentários de linha ou de bloco. As docstrings do Python podem ficar. O que precisar de mais explicação vai para a documentação em `docs/` ou para o `README.md`. O código que já existe não é mexido só para tirar comentários.
- Textos do LCD e da serial em ASCII, sem acentos.
- A arquitetura fica em `docs/arquitetura.md`, as decisões em `docs/decisoes.md`, o roteiro das fases em `docs/roteiro.md`, os scripts de voo em `docs/scripts-de-voo.md`, a lista de compras em `docs/compras.md` e o protocolo serial em `docs/protocolo.md`. O `README.md` (e o `README.pt-BR.md`) é só a vitrine: o que é o projeto, o que já funciona, como testar e o mapa das pastas. Documento novo entra no índice, `docs/README.md`.
- Todo painel segue a identidade visual de `hardware/identidade_visual.md`. Para propor o desenho de um painel, usar a skill `/desenhar-painel`; os desenhos são gerados por `node hardware/desenho/desenhar.js`.
