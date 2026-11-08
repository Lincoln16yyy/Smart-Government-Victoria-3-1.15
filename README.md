# Smart Government Advisor — Victoria 3 1.15

Conselheiro de leis para Victoria 3 1.15. Ele lê os efeitos **reais** das leis do
jogo, pontua as opções disponíveis e mostra as três melhores recomendações em um
registro de diário. O jogador decide: promulgar, ignorar, reavaliar ou desativar.

> **Status:** em desenvolvimento. A validação estática e o carregamento inicial
> do executável foram verificados; o teste interativo das ações do diário em um
> save ainda depende de uma sessão gráfica do jogo.

## O que ele faz

- Recomenda até três leis, com pontuação, benefício, risco, apoio do governo e
  explicação.
- Recomenda no máximo uma lei por grupo de leis. Variantes do mesmo grupo são
  alternativas mutuamente exclusivas, então o conselheiro escolhe a melhor de
  cada grupo antes de montar o top três.
- Usa o processo **normal** de promulgação (`start_enactment`). Não aprova leis
  automaticamente e não altera legitimidade, grupos de interesse ou oposição.
- Reavalia todo mês e também por um botão de atualização.
- Mostra o mês e o ano da última atualização das recomendações.
- Mostra quantas leis foram verificadas, ficaram disponíveis, foram filtradas
  por ignoradas, foram descartadas pela regra de um por grupo, entraram na
  comparação e foram exibidas no último ranking.
- Permite promulgar, ignorar até três leis, restaurar uma ignorada por vez,
  limpar a lista de ignoradas e desativar o conselheiro. Se a lei líder de um
  grupo for ignorada, a próxima melhor alternativa do grupo pode entrar no
  lugar.
- Mostra os efeitos e requisitos reais da lei ao passar o mouse sobre o nome.
- Interface em português do Brasil, com inglês como fallback.
- Não edita nenhum arquivo original do jogo.
- Inclui metadata local para evitar erro de leitura ao carregar o mod instalado.

## Requisitos

- Victoria 3 **1.15.x**.
- Nenhum DLC específico é necessário; o mod usa apenas leis e funções de script
  disponíveis na instalação base.
- Não é necessário iniciar uma nova campanha. O mod pode ser ativado em um save
  existente (veja abaixo).

## Instalação manual

O launcher precisa de **dois** itens: a pasta do mod (com `descriptor.mod`
dentro) e o arquivo `Smart Government Advisor.mod` ao lado dela.

1. Localize a pasta de mods do jogo. No Linux com Hydra/Wine, o caminho usado no
   desenvolvimento é:

   ```
   ~/.config/hydralauncher/wine-prefixes/529340/drive_c/users/steamuser/Documents/Paradox Interactive/Victoria 3/mod/
   ```

   Em uma instalação normal, é a pasta `mod` dentro de
   `Documents/Paradox Interactive/Victoria 3`.

2. Copie esta pasta para dentro de `mod/` com o nome
   `Smart Government Advisor`, de modo que exista:

   ```
   mod/Smart Government Advisor/descriptor.mod
   ```

3. Copie o arquivo `Smart Government Advisor.mod` (da raiz deste repositório)
   para `mod/`. Ele contém `path="mod/Smart Government Advisor"`, que é o que o
   launcher usa para registrar a pasta.

4. **Faça backup** de
   `.../Paradox Interactive/Victoria 3/content_load.json`.

5. Ative o mod no launcher do jogo (ou adicione-o ao `content_load.json`,
   preferindo o launcher).

6. Carregue um **save separado** para testar. Não use o único save da campanha.

> Alternativa: `python3 tools/install_mod.py` copia a pasta e cria o `.mod`
> correspondente. Use `--dry-run` para apenas mostrar o destino.

## Uso

- Em uma campanha nova, o conselheiro é ativado automaticamente após o lobby.
- Em um save existente, use a decisão **“Ativar Conselheiro de Governo
  Inteligente”**. Se você não a encontrar, aguarde o primeiro pulso mensal: o mod
  se inicializa sozinho uma vez.
- Abra o registro de diário **Smart Government**.
- Clique em **Promulgar** para iniciar a tramitação normal da lei recomendada.
  O botão fica desabilitado enquanto outra lei estiver sendo promulgada.
- Clique em **Ignorar** para tirar uma lei da lista até você limpar as ignoradas.
- Use o botão de atualização para reavaliar imediatamente.
- O registro mostra quando as recomendações foram atualizadas pela última vez.
- Se nenhuma lei puder ser recomendada, o estado vazio explica que as leis podem
  já estar ativas, bloqueadas pelos requisitos atuais ou ignoradas.

## Como a pontuação funciona

Cada lei recebe:

- **Benefício (0–100):** soma ponderada dos modificadores reais da lei
  (impostos, educação, saúde, burocracia, economia, estabilidade, forças
  armadas etc.), com ajustes situacionais leves.
- **Risco (0–60):** radicais, mortalidade, repressão, discriminação, restrições
  comerciais, custo orçamentário e pressão burocrática.
- **Apoio do governo (−50..50):** posição dos grupos de interesse **no governo**,
  ponderada por influência (`ig_clout`), mais a posição do governante.
- **Pontuação final:** `benefício + apoio − risco × 0,5 + chance estimada × 0,5`.

As três recomendações sempre vêm de grupos de leis diferentes. O conselheiro
elege primeiro a lei de maior pontuação de cada grupo (empates são resolvidos
pelo id estável) e só então compara essas líderes para formar o top três. Uma
lei ignorada deixa de concorrer como líder do grupo, permitindo que a próxima
melhor alternativa apareça.

Na linha de cada recomendação, o conselheiro mostra essa decomposição com os
valores calculados para a lei e a chance estimada de promulgação. A chance é
obtida do mesmo valor vanilla usado pelo jogo: leis com 0% de sucesso são
excluídas, enquanto leis difíceis mas possíveis recebem uma penalidade de
viabilidade. Isso não promete que uma lei será aprovada. As frases de
benefício e risco são resumos dos modificadores mensuráveis usados no cálculo;
passe o mouse sobre o nome para ver os efeitos e requisitos exatos fornecidos
pelo jogo.

Modificadores que apenas transferem poder entre grupos de interesse, poder de
voto ou “progressividade” ideológica são deliberadamente ignorados para evitar
viés ideológico. O que conta são efeitos reais de estabilidade, economia e
administração.

## Compatibilidade

O mod:

- usa apenas nomes com prefixo `sg_`;
- não sobrescreve arquivos originais;
- adiciona seus despachos mensais com a forma aditiva
  `on_actions = { ... }`;
- não toca nas variáveis nem nas decisões de outros mods.

Foi desenhado para coexistir com OGAS, Supply Chain Semi-Auto Builder,
Auto-Apply PMs, Auto-Apply Automation PMs, Auto-Diplomacy, Auto-Recruit e
Kuromi's AI. O teste de convivência em tempo de jogo ainda precisa ser feito.

## Desativar e remover

- Use a decisão **“Desativar Conselheiro de Governo Inteligente”** ou o botão
  **Desativar** no registro de diário.
- O registro é removido e todas as variáveis de execução são apagadas.
  Promulgações em andamento não são alteradas.
- Depois de desativar, o mod não se reativa sozinho.
- Para remover de vez, desative o mod no launcher e remova a pasta. O save fica
  limpo porque o estado de execução já foi apagado.

## Desenvolvimento

Os dados são gerados a partir da instalação do jogo. O caminho é descoberto
automaticamente (Steam, Hydra/Wine e instalações comuns) ou pode ser informado
de forma portátil:

```bash
python3 tools/build_law_data.py --game "/caminho/para/Victoria 3/game"
# ou:
VICTORIA3_GAME="/caminho/para/Victoria 3/game" python3 tools/build_law_data.py
python3 tools/build_gui.py
```

Não há caminho de máquina fixo no gerador. Se a descoberta falhar, ele para com
uma mensagem pedindo `--game` ou `VICTORIA3_GAME`.

Validação automatizada (somente biblioteca padrão):

```bash
python3 tools/build_law_data.py
python3 tools/build_gui.py
python3 -m unittest discover -s tests -v
python3 tools/validate.py
python3 -m py_compile tools/*.py tests/*.py
git diff --check
```

Os testes verificam os dados reais gerados, os 148 IDs estáveis, o ranking e
seus sentinelas, a fórmula de pontuação, a eleição de uma lei por grupo, datas
de atualização, limpeza ao desativar, estado vazio, explicações, ausência de
propriedades de GUI rejeitadas pela engine, codificação UTF-8 com BOM,
referências a defines com namespace e consistência entre scripts, GUI e
localização. Eles não substituem o teste interativo no jogo: o motor Clausewitz
e os cliques do diário continuam cobertos pelo procedimento manual abaixo.

Arquivos gerados (não edite à mão):

- `common/scripted_triggers/sg_law_availability.txt`
- `common/scripted_triggers/sg_law_groups.txt`
- `common/script_values/sg_law_scores.txt`
- `common/scripted_effects/sg_law_rank.txt`
- `common/scripted_effects/sg_law_actions.txt`
- `common/scripted_guis/sg_law_sguis.txt`
- `gui/journal_entry_widgets/sg_law_advisor.gui`
- `localization/english/sg_generated_l_english.yml`
- `localization/braz_por/sg_generated_l_braz_por.yml`
- `data/law_data.json`
- `data/law_ids.json` (stable numeric law ids; commit it)

O contexto completo para outro desenvolvedor ou IA está em
[`docs/AI_CONTEXT.md`](docs/AI_CONTEXT.md). O histórico de fases está em
[`docs/PHASE_LOG.md`](docs/PHASE_LOG.md).

## Diagnóstico

- Ative a variável de país `sg_debug` para registrar mensagens de ciclo de vida
  no `error.log`/log de script.
- O botão **Diagnóstico** no registro de diário grava uma mensagem e reavalia.
- A linha de diagnóstico do registro mostra os contadores do último ciclo de
  ranking, incluindo quantas leis disponíveis foram descartadas por já haver
  outra do mesmo grupo; isso ajuda a distinguir ausência real de leis de
  filtragem por requisitos, pela lista de ignoradas ou pela regra de um por
  grupo.
- Logs do jogo (Hydra/Wine):

  ```
  ~/.config/hydralauncher/wine-prefixes/529340/drive_c/users/steamuser/Documents/Paradox Interactive/Victoria 3/logs/
  ```

## Teste manual de runtime

O procedimento reproduzível para testar as ações do diário em um save separado
está em [`docs/MANUAL_RUNTIME_TEST.md`](docs/MANUAL_RUNTIME_TEST.md). Ele cobre
ativação, atualização, tooltip, promulgação normal, ignorar, limpar ignoradas,
desativar, reativar e pulso mensal, além da verificação dos logs.

## Limitações conhecidas

- A inicialização em Wine foi verificada e o log de runtime mais recente não
  contém erros do mod. Este ambiente ainda não permite conduzir de forma
  confiável a interface gráfica para carregar o save de teste e clicar nas ações
  do diário; restam apenas avisos benignos de variáveis legadas da migração e do
  interruptor opcional `sg_debug`.
- Algumas funções de GUI e de posição política ainda precisam de confirmação em
  runtime; os fallbacks estão documentados em `docs/AI_CONTEXT.md`.
- O texto de benefício/risco é temático (derivado dos modificadores), enquanto os
  efeitos exatos aparecem no tooltip da lei, direto do jogo.
- O mod não recomenda leis cuja disponibilidade não consiga modelar; ele nunca
  inventa um requisito.
