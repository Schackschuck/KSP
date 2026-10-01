# Desenhos dos painéis

Os painéis são desenhados em código, em SVG, com as peças no tamanho real (unidades em mm). Assim todos saem com a mesma [identidade visual](../identidade_visual.md), e o histórico dos desenhos fica legível no git.

| Arquivo | O que é |
|---|---|
| [`pecas.js`](pecas.js) | As peças: painel, grupo, korry, encoder, chave rotativa, tecla, botões, capas, barra de LEDs, alavanca, manche, cotas |
| [`paineis/`](paineis/) | Um arquivo por painel da [versão B](../construcao.md#cockpit-versão-b), que monta as peças nas posições certas, e o `cockpit.js`, que junta todos na vista de frente |
| [`antigos/`](antigos/) | Os painéis de 150 mm das propostas anteriores |
| [`desenhar.js`](desenhar.js) | Gera `hardware/img/<painel>.svg` a partir de cada arquivo de `paineis/` |

## Gerar

Precisa só do Node.js, sem instalar nada:

```
node hardware/desenho/desenhar.js                    # todos os painéis
node hardware/desenho/desenhar.js editor_manobras    # só um
node hardware/desenho/desenhar.js antigos            # os de 150 mm, em hardware/img/antigos/
```

Cada arquivo de `paineis/` exporta uma função que devolve `{ w, h, corpo, rotulo }`: a largura e a altura em mm, o SVG do painel e a descrição para leitores de tela. O `desenhar.js` põe as cotas em volta, e o `cockpit.js` usa o `corpo` de cada painel na vista de frente.

## Painel novo

1. Copiar `paineis/tempo.js` com o nome do painel, por exemplo `paineis/radar.js`.
2. Trocar o título, os grupos e as peças. As posições são em mm, a partir do canto de cima à esquerda do painel de 125 × 125 (ou 250 × 125).
3. Para pôr no cockpit, uma linha no `lugar` do `cockpit.js`, com a coluna e a fileira.
4. Gerar e abrir o SVG no navegador.
5. Pôr o desenho no documento do painel (por exemplo, uma seção em `hardware/construcao.md`).

Peça nova (um botão diferente, um display): uma função nova em `pecas.js`, no tamanho real, e uma linha na tabela de peças da [identidade visual](../identidade_visual.md#peças).
