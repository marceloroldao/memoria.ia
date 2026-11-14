# Observador separado em simulação controlada

Continuação opcional: [admissão com chave compartilhada e limites de autenticação](trajectory-authenticated-observer-proof.md). Os resultados e controles desta etapa permanecem válidos para a ponte sem autenticação.

Esta etapa liga a [auditoria de hipóteses congeladas](trajectory-prediction-audit.md) a um observador determinístico executado em outro processo. A solicitação fica registrada antes do resultado. Para uma solicitação fixa, o trabalhador recebe somente `world_seed`, `entity`, `tick` e `sensor_mode`: não recebe hipóteses, candidatas ou caminho do BDR. Campos extras são recusados.

Isso demonstra separação do fluxo de dados neste contrato controlado. O subprocesso não é uma sandbox de segurança, nem representa um sensor real ou uma fonte autenticada. O programa, o ambiente e o chamador continuam confiáveis no caminho normal de execução. Não há demonstração de independência causal geral.

## Fluxo implementado

`freeze_task()` exige que a entidade da consulta formal `Q[xx]?` corresponda à solicitação e congela esta solicitação, seu digest e o SHA256 do arquivo do trabalhador. `observe_task()` executa `controlled_symbol_observer.py` com a solicitação congelada; `ingest_result()` valida a estrutura, os digests, o texto e a correspondência com a tarefa antes de registrar a observação nativa e vinculá-la ao recibo.

O mundo tem uma regra determinística, implementada em `world_value()`, que muda o valor em uma unidade por tick. O modo `faithful` lê o tick solicitado; `lagged` lê o anterior. A ponte não consulta essa regra para decidir se aceita uma observação. O avaliador usa a regra somente depois da ingestão para medir concordância com a simulação. Um teste substitui a função no processo pai por uma exceção e confirma que o fluxo normal de observação continua funcionando no subprocesso.

A intervenção adicional altera os valores lembrados em 17 unidades, mantendo a solicitação fixa: as candidatas congeladas mudam, mas o pacote do trabalhador permanece igual. É um teste contrafactual do conteúdo da memória; não mede precisão preditiva nem prova não interferência sob ataque.

## Resultados preservados

As duas sementes, `20270119` e `20270120`, apresentam os mesmos estados:

| Cenário | Confronto | Concordância das observações vinculadas com o mundo simulado |
|---|---|---|
| Estado estável | `MATCHES_ONE_OF_MULTIPLE` | Sim |
| Estado mudou | `OUTSIDE_FROZEN_SET` | Sim |
| Leitura defasada | `MATCHES_ONE_OF_MULTIPLE` | Não, para o tick solicitado |
| Memória sem cobertura | `NO_CANDIDATES_AT_CUTOFF` | Sim |
| Resultado de outra tarefa | `PENDING`, recusado antes de escrever | Sem vínculo |
| Pacote alterado sem atualizar checksum | `PENDING`, recusado antes de escrever | Sem vínculo |
| Falsificação com checksum recalculado | `MATCHES_ONE_OF_MULTIPLE` | Não |
| Dois relatos incompatíveis | `DIVERGENT_LATER_OBSERVATIONS` | Um concorda, outro discorda |

A falsificação é injetada deliberadamente pela API de baixo nível. Passa porque um checksum comprova consistência dos bytes, não identidade da fonte. O caminho normal `observe_task()` chama o trabalhador local conhecido, mas não acrescenta assinatura, certificação de sensor ou autenticação geral. A leitura defasada e a falsificação demonstram que coincidir com uma candidata antiga não a torna verdadeira.

As candidatas congeladas continuam sendo valores já observados. A mudança de estado retorna um valor fora desse conjunto: esta etapa não implementa previsão de valores inéditos nem aprende uma lei de transição.

## Persistência e limites

O journal nativo aceita `observation_context` no recibo e `source_receipt` no vínculo. Ambos são opcionais, limitados a 4096 caracteres JSON e recusam valores não finitos. Quando ausentes, são omitidos: os dois relatórios anteriores da auditoria permanecem idênticos byte por byte. A solicitação não pode ser trocada em uma repetição do mesmo identificador.

O recibo completo do observador persiste no vínculo, inclusive após reabertura do BDR. A origem nativa usa o digest do pacote, independentemente dos identificadores de hipótese e resultado. Reenviar o mesmo pacote não cria uma ocorrência mais recente; mudar o identificador do vínculo ou congelar outra hipótese não permite fabricar posterioridade. Uma nova medição intencional exige uma solicitação diferente, como outro tick. Esta versão não possui nonce de aquisição.

A ponte pressupõe um escritor. A escrita da observação e a do vínculo são sequenciais, sem transação conjunta: interrupção entre elas pode deixar uma observação sem vínculo. A repetição exata permite retomar sem duplicar a ocorrência. Não se reivindica atomicidade ou segurança concorrente.

O confronto continua somente leitura: `answer=null`, `qualified=false`, `learning_applied=false`, `provenance_independence=NOT_ESTABLISHED`. A observação explícita entra pela ingestão normal e conserva os efeitos dessa ingestão; a comparação não adiciona aprendizado, feedback ou pesos. Hipóteses e resultados do avaliador não viram fatos automaticamente. O núcleo, a ABI móvel, o MVP e o console não foram alterados.

## Validação e reprodução

Foram aprovados 35 testes locais: 18 do observador e 17 da auditoria anterior. Os dois relatórios novos contêm 82/82 verificações de integridade cada, cobrindo oito cenários, persistência, repetição, leitura sem escrita e a intervenção. Esses números medem invariantes do protocolo, não taxa de acerto cognitivo.

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
  python -m pytest -q tests/test_trajectory_controlled_observer_probe.py tests/test_trajectory_prediction_audit.py
PYTHONPATH=src python scripts/trajectory_controlled_observer_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so --seed 20270119 \
  --output /tmp/controlled-observer-development.json.gz
```

Repetir com semente `20270120` para a amostra reservada. Os artefatos integrais estão em `benchmark-results/trajectory-controlled-observer-{development,reserved}.json.gz`, com entradas, recibos, recusas, resultados e verificações. O CI reconstrói o runtime com BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`, executa os testes e compara os relatórios completos descomprimidos.

| Amostra | SHA256 do conteúdo registrado no relatório |
|---|---|
| Desenvolvimento | `3a48a6cf745606b243d29a6387fdd26ad0d8b5b92ad7b71c0a72eef7bec77a62` |
| Reservada | `c6880ecd3da389f75792593bcb837c1b4a6ec883e04508e1f16b7dbbe9e62ccd` |

Próxima lacuna técnica: uma aquisição com identidade autenticada e política explícita de qualidade, seguida de experimentos de previsão e correção separados da simples recorrência. Nada nesta etapa comprova aprendizado geral, verdade externa ou AGI.
