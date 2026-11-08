# Smart Government Advisor — Victoria 3 1.15

Conselheiro de leis para Victoria 3 1.15. Ele lê os efeitos **reais** das leis do
jogo, pontua as opções disponíveis e mostra as três melhores recomendações em um
registro de diário. O jogador decide: promulgar, ignorar, reavaliar ou desativar.

> **Status:** em desenvolvimento (fase 2). O código-fonte e os dados gerados já
> estão no repositório, mas o teste em tempo de jogo ainda não foi executado.
> Não trate o mod como pronto para uso público antes da validação e do teste em
> um save separado.

## O que ele faz

- Recomenda até três leis, com pontuação, benefício, risco, apoio do governo e
  explicação.
- Usa o processo **normal** de promulgação (`start_enactment`). Não aprova leis
  automaticamente e não altera legitimidade, grupos de interesse ou oposição.
- Reavalia todo mês e também por um botão de atualização.
- Permite promulgar, ignorar até três leis, limpar a lista de ignoradas e
  desativar o conselheiro.
- Mostra os efeitos e requisitos reais da lei ao passar o mouse sobre o nome.
- Interface em português do Brasil, com inglês como fallback.
- Não edita nenhum arquivo original do jogo.

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

> Alternativa: `python3 tools/install_mod.py` copia a pasta e cria o `.mod` com
> o caminho absoluto correto. Use `--dry-run` para apenas mostrar o destino.

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

## Como a pontuação funciona

Cada lei recebe:

- **Benefício (0–100):** soma ponderada dos modificadores reais da lei
  (impostos, educação, saúde, burocracia, economia, estabilidade, forças
  armadas etc.), com ajustes situacionais leves.
- **Risco (0–60):** radicais, mortalidade, repressão, discriminação, restrições
  comerciais, custo orçamentário e pressão burocrática.
- **Apoio do governo (−50..50):** posição dos grupos de interesse **no governo**,
  ponderada por influência (`ig_clout`), mais a posição do governante.
- **Pontuação final:** `benefício + apoio − risco × 0,5`.

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

Arquivos gerados (não edite à mão):

- `common/scripted_triggers/sg_law_availability.txt`
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
- Logs do jogo (Hydra/Wine):

  ```
  ~/.config/hydralauncher/wine-prefixes/529340/drive_c/users/steamuser/Documents/Paradox Interactive/Victoria 3/logs/
  ```

## Limitações conhecidas

- O teste em tempo de jogo ainda não foi executado.
- Algumas funções de GUI e de posição política ainda precisam de confirmação em
  runtime; os fallbacks estão documentados em `docs/AI_CONTEXT.md`.
- O texto de benefício/risco é temático (derivado dos modificadores), enquanto os
  efeitos exatos aparecem no tooltip da lei, direto do jogo.
- O mod não recomenda leis cuja disponibilidade não consiga modelar; ele nunca
  inventa um requisito.
