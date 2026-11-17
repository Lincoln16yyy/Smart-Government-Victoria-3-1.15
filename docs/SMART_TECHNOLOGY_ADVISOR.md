# Smart Technology Advisor

Abra o diário **Smart Government** e role até **Conselheiro Tecnológico**. A
primeira proposta é a mais prioritária entre as pesquisas disponíveis; a segunda
é o próximo passo sugerido para as condições atuais. O painel usa os nomes da
árvore do jogo, mostra progresso e custo em pontos de pesquisa e sinaliza
tecnologias já na fila. Durante uma pesquisa ativa, as sugestões servem para
planejar o próximo passo.

A reavaliação ocorre na ativação, no início e ao adquirir tecnologias, na
atualização mensal do país e pelo botão da seção. O painel filtra tecnologias
concluídas e a pesquisa em curso. O módulo só armazena as recomendações
ordenadas e não altera a pesquisa. Também não emite notificações.

## Priorização

| Leitura do país | Exemplos de recomendação |
| --- | --- |
| Infraestrutura excedida em um estado incorporado | **Ferrovias**, se os requisitos estiverem satisfeitos. Se o caminho estiver bloqueado, uma das etapas diretas já disponíveis pode aparecer com os requisitos que faltam para Ferrovias. |
| Infraestrutura excedida onde já há ferrovia e oferta local de eletricidade | **Ferrovias Elétricas**, para desbloquear trens elétricos. |
| Grãos ou minérios em escassez com prédios relevantes e insumos disponíveis | Métodos de produção como fertilização ou bombas de condensação. |
| Guerra ou jogada diplomática envolvendo o país | Tecnologias defensivas como `field_works` ganham precedência. Com infantaria irregular e armas leves disponíveis, pode aparecer infantaria de linha. |
| Escassez de armas leves, fábrica de armas e disponibilidade dos insumos | Métodos de rifles, conforme os pré-requisitos. |
| Alfabetização abaixo de 60% ou inovação abaixo do limite | Educação, acesso a universidades ou métodos universitários. Métodos que consomem papel exigem oferta desse insumo. |
| Dívida com saldo negativo ou insuficiência de capacidade tributária | Tecnologias de redução dos juros ou aumento da capacidade tributária. |

Os pesos são escolhas de política do conselheiro. Cada tecnologia só disputa
uma posição quando seu contexto está presente e todos os requisitos diretos
foram pesquisados. Em cenários com múltiplos gargalos, o ranking considera o
conjunto das três árvores. Se nenhuma das regras produzir uma tecnologia
disponível, a seção exibe o estado vazio.

O módulo lê sinais vanilla semelhantes aos do
[Smart Economy Director](https://github.com/Lincoln16yyy/SMART-ECONOMY-DIRECTOR)
no commit `c3e49be`, incluindo saldo observado, ordens de venda, escassez,
capacidade tributária e oferta local. O Director é opcional.

## Fontes e regeneração

A versão de referência é a instalação 1.15.0, indicada por
`caligula_branch.txt`. Os pré-requisitos, a categoria e `can_research` vêm de
`common/technology/technologies/`. Os benefícios são curados a partir dos
modificadores, prédios, métodos de produção e tipos de unidades vanilla. Os
eventos de início e aquisição vêm de `common/on_actions/00_code_on_actions.txt`.
Nomes, pontos atuais, custo e posição na fila usam as funções observadas em
`gui/tech_tree.gui` e na localização vanilla.

Os pesos e os textos editáveis ficam em `tools/research_policy.py` e os sinais
de jogo em `common/scripted_triggers/sg_research_context.txt`. A compilação
confere os identificadores e extrai os requisitos antes de gerar scripts e
localização. O inventário operacional é `data/tech_advisor_candidates.json`.

```bash
python3 tools/build_research_data.py --game "/caminho/para/Victoria 3/game"
python3 tools/build_gui.py
python3 tools/validate.py
python3 -m unittest discover -s tests -p test_technology_advisor.py -v
```

O primeiro conjunto cobre 18 tecnologias com benefícios e sinais verificados
nos arquivos, incluindo três árvores. A pesquisa percorre esse conjunto
curado. O caminho de Ferrovias explica pré-requisitos diretos pendentes. Outros
caminhos aprofundados, valor previsto por tecnologia, tempo restante e
disponibilidade de recursos naturais ainda inexplorados ficam fora do modelo.

## Validação e roteiro em campanha

- Os testes direcionados exercitam o efeito de ranking gerado com cenários
  simulados de paz, guerra, falta de requisitos, início e conclusão de
  pesquisas. Conferem também limpeza de estado, integração com o diário e
  referência de interface nos dois idiomas.
- Passaram seis testes novos, seis regressões selecionadas da interface e
  ciclo de vida, e o validador estático do repositório. O Tiger v1.19.0
  não sinalizou scripts do conselheiro tecnológico.
- O executável reconheceu a instalação isolada do Smart Government Advisor
  como compatível com 1.15.0. A sessão sob Wine não chegou à campanha. A
  renderização e o acionamento dos eventos em partida permanecem pendentes.
- A edição para Better Politics foi empacotada e passou pelo validador. Os
  arquivos tecnológicos da instalação local do Better Politics foram
  conferidos quanto a alterações nas 18 candidatas.
- Em uma campanha de teste, abra o diário e confira as sugestões contra as
  árvores tecnológicas. Em um país com pressão de infraestrutura, verifique
  Ferrovias e seus dois pré-requisitos. Em um país sob ameaça confirmada,
  confira se uma tecnologia defensiva disponível sobe na ordem.
- Inicie uma das pesquisas mostradas, complete uma pesquisa e confira as
  atualizações sem precisar usar o botão. Compare os pontos e a fila com a
  árvore, avance um mês e confira o diário após salvar e recarregar.
