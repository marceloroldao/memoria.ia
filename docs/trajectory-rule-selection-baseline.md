# Escolha de regra por perdas anteriores emparelhadas

Fluxo local utilizável: [laboratório de observações, previsão e confronto](trajectory-forecast-lab.md), com JSON por linha, persistência e retomada. As baselines desta etapa permanecem preservadas.

Continuação da [baseline de trecho recente](trajectory-recent-regime-baseline.md). O experimento acrescenta uma decisão anterior à próxima medição: escolher entre duas regras já fornecidas pelo programador, usando apenas resultados nativos anteriores que possam ser comparados em condições iguais.

O catálogo continua fixo: `whole_history` e `recent_suffix`. A aritmética, o catálogo, os custos e o suporte mínimo são programados. Os dados determinam a pontuação e, quando há suporte, o vencedor. Isso não demonstra descoberta de operadores ou modelos pelo núcleo, aprendizado de veracidade das fontes ou atualização de pesos cognitivos.

## Ensaios anteriores comparáveis

Um alvo anterior só contribui se houver exatamente uma previsão de cada regra para a mesma entidade e tick. Ambas devem:

- Ter sido congeladas com a mesma consulta, o mesmo digest de observações, a mesma quantidade de linhas e o mesmo corte de sequência.
- Ter seus modelos reproduzidos a partir desse prefixo.
- Possuir exatamente um vínculo de resultado cada, referente à mesma ocorrência nativa completa.
- Usar uma medição da entidade e do tick previstos, presente no prefixo conhecido pelo seletor.
- Referir-se a um tick anterior ao alvo atual.

Mesmo texto em ocorrências diferentes não constitui um ensaio emparelhado. Previsões com passados diferentes, pares incompletos, múltiplas versões da mesma regra, resultados conflitantes ou alvo incorreto não recebem pontuação; a razão aparece em `skipped_trials`. Repetir exatamente o mesmo identificador não cria outro ensaio. Acrescentar identificadores distintos para o mesmo alvo torna o grupo ambíguo em vez de inflar o suporte.

Os candidatos do alvo atual também devem compartilhar todo o prefixo atual e ainda não ter resultado vinculado. Registrar a medição atual antes de congelar a decisão faz a verificação falhar, mesmo que ela ainda não tenha vínculo.

## Custos e decisão explícitos

Para cada ensaio anterior elegível e cada regra:

| Resultado sobre a medição declarada | Custo |
|---|---:|
| Proposta coincide exatamente | 0 |
| Regra se absteve | 1 |
| Proposta diverge | 2 |

A pontuação é a soma dos custos. O denominador de ensaios é o mesmo para ambas as regras. Os custos e o mínimo de dois ensaios são escolhas do experimento, não parâmetros cuja optimalidade tenha sido comprovada.

Com pelo menos dois ensaios e uma pontuação estritamente menor, a regra vence. Se ela não tem proposta para o alvo atual, o seletor se abstém; não troca silenciosamente para a outra. Sem vencedor sustentado, permite apenas uma proposta idêntica já emitida por ambas, como `CONSENSUS_WITHOUT_LEADER`. Esse consenso entre regras correlacionadas não é confirmação independente. Se não há consenso, retorna `ABSTAIN_NO_SUPPORTED_LEADER`.

A saída registra custos, contagens, identificadores de candidatos, recibos, ensaios, exclusões e regra escolhida. O confronto final continua devolvendo uma hipótese sem resposta factual qualificada.

## Dois cortes congelados

A decisão fica em `observation_context` do journal de auditoria, com:

1. O prefixo de observações da auditoria anterior.
2. A quantidade e o digest dos eventos do próprio journal que já existiam antes da decisão.

`compare()` reconstrói a escolha usando esses dois prefixos, não o journal completo atualizado. Assim, medições e rótulos posteriores podem orientar decisões novas, mas não reescrevem a pontuação antiga. Um teste acrescenta um resultado conflitante para um alvo anterior depois do congelamento: a leitura atual passa a excluir esse ensaio, enquanto a decisão antiga continua reproduzindo seu corte original.

Repetir o identificador de uma decisão recupera seu conteúdo anterior. Alterar os identificadores dos candidatos nessa repetição é recusado. Hipóteses, candidatos e resultados são registros separados. Nenhuma proposta é automaticamente inserida como medição ou fato.

## Resultado na quebra de padrão

Em cada tick de 3 a 7, os dois candidatos e o seletor são congelados antes da nova medição. A previsão da regra recente também é acompanhada quando o seletor se abstém, para que um resultado posterior possa orientar a escolha seguinte.

| Alvo | Ensaios anteriores | Custo histórico completo | Custo trecho recente | Decisão do seletor |
|---|---:|---:|---:|---|
| 3 | 0 | 0 | 0 | Consenso; erra a primeira quebra |
| 4 | 1 | 2 | 2 | Abstém-se |
| 5 | 2 | 3 | 3 | Abstém-se |
| 6 | 3 | 4 | 4 | Abstém-se; só a regra recente possui proposta |
| 7 | 4 | 5 | 4 | Escolhe a regra recente; coincide com o mundo |

A medição do tick 6 confirma a proposta da regra recente, mas só entra na decisão do tick 7. O seletor deliberadamente espera um resultado adicional em comparação com usar sempre o trecho recente. Isso demonstra escolha baseada em desempenho anterior, não superioridade geral sobre uma regra fixa ou previsão da primeira quebra.

Na série estável, as duas regras mantêm custos iguais e propostas iguais: o seletor usa consenso sem inventar um vencedor. Na aceleração, as duas continuam sem propostas e o seletor se abstém.

## Controles negativos

No cenário de rótulos falsos, o chamador acrescenta dez unidades às medições declaradas a partir da quebra aparente. A regra recente passa a coincidir com essas entradas, ganha na pontuação e é selecionada no tick 7, mas seu valor discorda do mundo sintético. Uma pontuação melhor contra rótulos falsos não torna a fonte verdadeira.

No controle de autocópia, as próprias hipóteses são reinseridas pelo chamador como medições. Os custos aparentes permanecem bons e o confronto coincide em todos os cinco alvos; o mundo discorda em todos eles. O avaliador conhece o mundo apenas para preservar esse diagnóstico posterior. Seu valor esperado não é passado ao seletor ou ao ajuste das regras.

As medições continuam declaradas e os vínculos explícitos, sem integração automática com HMAC/freshness. Nem o consenso nem a pontuação reivindicam independência. Permanecem `answer=null`, `qualified=false`, `learning_applied=false` e `provenance_independence=NOT_ESTABLISHED`. As pontuações são recalculadas de registros antigos; `learning_applied=false` indica que a rotina não atualiza pesos do núcleo nem promove conteúdo a fato. A ingestão normal das medições conserva seus efeitos anteriores.

## Evidência reproduzível

- 171 testes locais aprovados: 22 novos e 149 anteriores, executados nas verificações completas e focadas da mudança.
- Sementes `20270131` e `20270132`: 230/230 verificações de integridade por semente, distintas de acertos ou confiabilidade factual.
- Decisões, pontuações, modelos candidatos, observações e journal reproduzidos em dois processos sucessivos.
- Cobertos emparelhamento por prefixo e ocorrência, suporte insuficiente, empates, líder sem proposta, duplicação, resultados ausentes/conflitantes, alvo futuro, rótulo atual antes do corte, rótulo anterior acrescentado depois do corte e prefixo adulterado.
- Os dois relatórios anteriores de trecho recente foram reproduzidos byte por byte.

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
  python -m pytest -q tests/test_trajectory_rule_selection_probe.py \
  tests/test_trajectory_recent_regime_probe.py tests/test_trajectory_transition_forecast_probe.py \
  tests/test_trajectory_observer_rejection_probe.py tests/test_trajectory_observer_freshness_probe.py \
  tests/test_trajectory_authenticated_observer_probe.py \
  tests/test_trajectory_controlled_observer_probe.py tests/test_trajectory_prediction_audit.py
PYTHONPATH=src python scripts/trajectory_rule_selection_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so --seed 20270131 \
  --output /tmp/rule-selection-development.json.gz
```

Repetir com `20270132` para a amostra reservada. Relatórios em `benchmark-results/trajectory-rule-selection-{development,reserved}.json.gz` preservam entradas iniciais, decisões por tick, medições genuínas e fornecidas, avaliação, linhas finais e journal completo com os modelos de todos os candidatos. As sementes variam entidade e nível numérico no mesmo desenho, sem avaliação cega.

O CI dedicado reconstrói o runtime com BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a` e compara os relatórios integrais descomprimidos. O limite de 4096 caracteres de metadados, o escritor único e a ausência de transação conjunta permanecem. Esta prova não valida escala de históricos longos, segurança de produção ou adaptação causal do ambiente.

Núcleo, ABI móvel, MVP e console não foram alterados. O incremento é uma baseline auditável de escolha entre regras fornecidas, preservando erros e resultados contrários às hipóteses.
