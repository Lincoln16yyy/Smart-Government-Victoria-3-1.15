# Smart Research — recomendação de tecnologias

## Escopo

Relação direta ao solicitado: um módulo que, como o advisor de leis, analisa o estado do país e **recomenda as 3 melhores tecnologias** a serem pesquisadas, sem selecionar nem iniciar pesquisa nenhuma. O jogador lê e decide. A interação é toda manual, pelo diário, igual ao fluxo de leis.

## Por que começa com pesquisa e não com algo mais

O advisor de leis já serve de base: mesmo pipeline de build — gerador Python que lê um único fonte `data/tech_data.json` e produz scripts `common/scripted_*`, GUI `sg_research_advisor.gui`, localização bilíngue e teste — e mesmo padrão de nomenclatura `sg_`. Começar por pesquisa é o menor passo que entrega valor visível no diário, sem tocar em econômica ou política externa, e sem inventar qualquer fluxo automático.

## Comportamento pretendido

- Um novo entry widget no diário, de uso opcional.
- Cada análise:
  - lista as tecnologias pesquisáveis (sem grupo, sem pós-requisitos não satisfeitos) com progresso atual e benefício, e
  - indica as 3 com melhor contribuição esperada ao país naquele momento, ordenadas por plausível impacto, não por “potência bruta”;
- se alguma das 3 recomendações já estiver em pesquisa ou promulgada (pesquisa concluída), ela é substituída pela melhor alternativa disponível para o ranking não mostrar repetidos;
- se não houver tecnologia pesquisável que realmente ajude o rumo do país naquele momento, o advisor não força recomendação; ele diz que as recomendações não adicionam ao rumo atual e sugere esperar — nunca inventa uma recomendação só para preencher o espaço.
- nenhuma ação no jogo é tomada automaticamente: nenhuma research start, nenhum research awake, nenhum research queue. Tudo fica para o jogador.
- os mesmos detalhes de apoio, oposição/riscos e chance do advisor de leis aparecem para cada recomendação, com o significado que já existe para pesquisa: custo de CP, tempo estimado, efeito atual e efeito após conclusão.

## Interface

Mesmo estilo do advisor de leis: cabeçalho curto com tooltip, blocos de recomendação em português com fallback em inglês, avisos de risco/apoio quando relevantes. Se o país já tem uma pesquisa ativa e o advisor acha que mudar de rumo faz sentido, ele avisa, mas não executa a troca.

## Fontes e dados

Dados reais das tecnologias vêm do jogo em runtime; aqui usamos a mesma fonte de verdade usada para leis — um único JSON `data/tech_data.json` alimentado pelo gerador, validado pelo mesmo `validate.py`. Os scripts gerados seguem a mesma estrutura do `sg_law_rank` e `sg_effects`, para que as recomendações sejam consultáveis pelo GUI com `sg_top_N_*`.

## Regras de não fazer

- não toca em qualquer outro advisor, em econômica, política externa ou em IA do jogo;
- não inicia, acorda ou fila pesquisa alguma;
- não recomenda tecnologias fora do que o país pode pesquisar agora;
- não inventa recomendação quando não há vantagem real ao rumo do país;
- não adiciona UI, sound ou efeito visual fora do estilo do advisor de leis já pronto.

## Validação

Mesmo pipeline do advisor de leis: build, testes unitários, `validate.py`, `py_compile` e `git diff --check`. Toda mudança vai para `origin/main`.

## Próximos passos

- 1. Gerador de dados e scripts básico da pesquisa (fontes, ranking, aviso de vazio e de repetidos).
- 2. GUI e localização.
- 3. Testes e validação.
- 4. Feedback no jogo, ajuste de pesos ou de critério de “ajuda ao rumo” se necessário.
