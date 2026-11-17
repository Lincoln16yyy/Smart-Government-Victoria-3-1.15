# Smart Military Advisor

O Conselheiro Militar aparece no fim do registro **Smart Government**. Lê o
país do jogador ao ativar o conselheiro e a cada mês. O botão da seção atualiza
somente a análise militar. A primeira atualização mensal popula a seção em
saves anteriores. Desativar o conselheiro limpa as variáveis militares.

## Seleção

A seção mostra uma ação com prioridade, motivo e instrução de interface.

| Situação observada | Conselho |
| --- | --- |
| Escassez de armas leves, munição ou artilharia | Abrir o bem afetado no mercado, revisar oferta e demanda e adiar encomendas. |
| Margem fiscal, reservas ou dívida fora da guarda | Rever gastos militares no orçamento e adiar despesas dispensáveis. |
| Guerra ou jogada diplomática | Conferir mobilização e custos. Se um exército tiver um general numa frente e organização-alvo abaixo de 80, revisar aquela formação. |
| Infantaria irregular e infantaria de linha disponível | Revisar a atualização na formação indicada. Exige oferta de armas leves e guarda fiscal suficiente. |
| Exército não mobilizado com pelo menos quatro unidades e sem general | Recrutar um general para a formação indicada. |
| Menos de dez batalhões regulares em paz | Recrutar até quatro batalhões de infantaria de linha. O lote cobre até o déficit do piso de dez e a folga dos generais da formação. O estado sugerido tem quartel, incorporação, acesso ao mercado de 95% ou mais e folga de infraestrutura. |
| Menos de três navios e rival formal com maior força naval | Construir uma fragata para a frota indicada se o casco ainda for pertinente, houver insumos e existir um estado costeiro incorporado com estaleiro e administração naval. Estaleiro com ocupação de pelo menos 50% e frota com almirante e tripulação de pelo menos 50%. |
| Rival formal com fronteira terrestre e mais batalhões | Revisar a defesa da fronteira com o rival identificado. |

Os pisos de efetivo e os limites de triagem são critérios do conselheiro. A
inferência de risco usa rivalidade formal e comparação de efetivo. Na marinha,
`navy_size` serve à comparação de força entre países e o painel conta navios
somando `num_ships` das frotas. A 1.15 dispõe de construção de navios individuais.

### Exemplos de saída

Estes exemplos substituem os campos dinâmicos por nomes ilustrativos.

- Com 6 batalhões, 4 vagas de comando e os requisitos satisfeitos, **Recrutar
  4 de infantaria de linha** orienta a abrir a formação indicada, selecionar
  infantaria de linha e verificar se o estado sugerido aceita o lote.
- Com 2 navios, rival mais forte e capacidade compatível, **Construir 1
  fragata de escolta** aponta a frota e um estado candidato.
- Em escassez de munição, **Resolver a escassez de munição** leva o jogador
  ao bem no Mercado antes de recomendar uma expansão.

## Acompanhamento

As propostas de expansão preservam estado, formação, referência e meta no
save enquanto estão pendentes. O recrutamento acompanha o total nacional e a
infantaria de linha da formação indicada por até 180 dias. O plano naval
acompanha as fragatas da frota indicada por até 365 dias. Se a meta for
atingida, o histórico passa para **Possivelmente atendida**. Transferência,
modernização e outras alterações podem produzir parte desses mesmos sinais.

Uma proposta expirada ou cujas condições deixem de valer passa para
**Desatualizada**. Cada categoria espera 90 dias após encerrar um plano para
sugerir nova expansão. Alertas e orientações sem plano desaparecem quando
perdem prioridade ou quando a condição deixa de ocorrer. O painel não usa
eventos de notificação.

## Leitura econômica

O [Smart Economy Director](https://github.com/Lincoln16yyy/SMART-ECONOMY-DIRECTOR)
foi consultado no commit `c3e49be`. Seus filtros de recuperação salarial militar
combinam `net_total_income`, `net_fixed_income`, despesas militares,
`principal` e reservas. O Director também usa previsões de caixa da fila,
preços e demanda não atendida para ordenar recuperação, insumos e investimento.

O Conselheiro Militar lê os dados vanilla de forma independente. Exige saldo
total positivo, saldo fixo não negativo, ausência de dívida e moratória,
reservas equivalentes a doze semanas de despesa fixa e saldo total de pelo
menos metade da despesa militar corrente. Confere ordens de venda e escassez dos
insumos aplicáveis antes de propor expansão. A regra é conservadora e se aplica
também quando o Director está indisponível. Ela não calcula o custo marginal
das obras nem usa decisões, efeitos ou variáveis privadas do Director.

## Evidência e limites

As referências de 1.15.0 incluem a expansão e mobilização do tutorial
(`00_tutorial.txt` e `00_subgoals_tutorial.txt`), as listas de formações,
personagens e unidades em `00_ep1_kazakh_events.txt` e `je_values.txt`,
os limites em `command_values.txt`, os alertas navais em
`00_alert_types.txt` e o casco em `00_ship_types.txt`.

A perda de capacidade de construção ao enfileirar um projeto, a ocupação
futura dos quartéis, as vagas exatas do diálogo de recrutamento e o custo
marginal do lote ficam para confirmação do jogador nos menus indicados. A
frigata é a opção modelada pela versão inicial. O painel não propõe cascos
posteriores, ordens automáticas, desmobilização automática ou uma localização
de frente inferida a partir da diplomacia.

Foram executados cinco testes direcionados do módulo e seis regressões de
GUI, atualização e desativação. O `vic3-tiger` v1.19.0 verificou os scripts
contra a instalação 1.15.0 sem diagnóstico nas superfícies militares. O
`tools/validate.py` reproduziu os mesmos 178 diagnósticos de `origin/main`
no protótipo de pesquisa. Nas tentativas isoladas sob Wine, o jogo reconheceu
os dois mods e a versão, mas a sessão não chegou à campanha. Renderização,
execução em partida, comportamento mensal e persistência via recarga
continuam pendentes de teste interativo.

### Roteiro em campanha

1. Abra uma cópia de teste em 1920×1080. Ative o conselheiro, role o diário e
   confira os números com os painéis Militar e Orçamento.
2. Em paz, com uma economia apta e um pequeno exército, compare a quantidade,
   o nome do exército e o estado indicado com o diálogo de recrutamento.
   Enfileire o lote e atualize antes e depois de concluído. Confira o
   histórico após a formação atingir a meta e recarregue o save.
3. Com uma frota pequena e um rival naval, faça o mesmo com uma fragata.
   Confira se a caixa de construção aceita a frota e o estado propostos.
4. Em guerra ou sob escassez e déficit, confira a precedência dos alertas.
   Deixe passar um mês e compare com a atualização manual.
5. Desative e reative o conselheiro. Confira a limpeza do histórico, a
   ausência de entradas duplicadas e `error.log` para mensagens
   `sg_military` ou `sg_law_advisor`.
