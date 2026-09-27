# Desenhos dos painéis

Os painéis são desenhados em código, em SVG, com as peças no tamanho real (unidades em mm). Assim todos saem com a mesma [identidade visual](../identidade_visual.md), e o histórico dos desenhos fica legível no git.

| Arquivo | O que é |
|---|---|
| [`pecas.js`](pecas.js) | As peças: painel, grupo, korry, encoder, chave rotativa, tecla, botões, cotas |
| [`paineis/`](paineis/) | Um arquivo por painel, que monta as peças nas posições certas |
| [`desenhar.js`](desenhar.js) | Gera `hardware/img/<painel>.svg` a partir de cada arquivo de `paineis/` |

## Gerar

Precisa só do Node.js, sem instalar nada:

```
node hardware/desenho/desenhar.js                    # todos os painéis
node hardware/desenho/desenhar.js editor_manobras    # só um
```

## Painel novo

1. Copiar `paineis/editor_manobras.js` com o nome do painel, por exemplo `paineis/sistemas.js`.
2. Trocar o título, os grupos e as peças. As posições são em mm, a partir do canto de cima à esquerda do painel de 150 × 150.
3. Gerar e abrir o SVG no navegador.
4. Pôr o desenho no documento do painel (por exemplo, uma seção em `hardware/construcao.md`).

Peça nova (um botão diferente, um display): uma função nova em `pecas.js`, no tamanho real, e uma linha na tabela de peças da [identidade visual](../identidade_visual.md#peças).
