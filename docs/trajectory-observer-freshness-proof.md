# Política congelada de atraso declarado

Continuação da [admissão com chave compartilhada](trajectory-authenticated-observer-proof.md). Esta etapa acrescenta uma regra opcional sobre a diferença entre o tick solicitado e o tick declarado no pacote autenticado. Ela pode impedir a ingestão de uma leitura explicitamente defasada. Não verifica o relógio físico, a honestidade da declaração ou o valor medido.

## Fluxo e persistência

1. Congelar a hipótese/tarefa com `auth.freeze_task()`.
2. Congelar `{'max_tick_lag': 0}` com `freeze_policy()` para exigir o tick solicitado, ou declarar uma tolerância inteira entre 0 e 1000.
3. Obter o envelope autenticado do observador.
4. Chamar `admit()` para avaliar a regra antes da ingestão normal.

O registro de política fica no BDR, na região de controle `observer-freshness:<hash da região>`, separado das observações e do journal de hipóteses. Ele contém versão de formato, região, identificador da hipótese, identificador do recibo congelado, política e digest. Não contém a chave, as candidatas ou o valor esperado do mundo. A política é do chamador e não é assinada pelo sensor; o ambiente local e o escritor continuam confiáveis.

Uma política nova só pode ser acrescentada se as linhas principais ainda corresponderem integralmente ao prefixo congelado, sem ocorrências posteriores ou vínculos de resultado. A repetição exata reutiliza a política; tentar trocar sua tolerância é recusado. Este controle demonstra precedência sobre a ingestão nativa: não prova que o chamador ainda não tenha visto um resultado fora da memória. No fluxo normal do experimento, a política é registrada antes de executar o trabalhador.

`assess()` é somente leitura: verifica a política vinculada, a tarefa, a confiança atual na chave, o MAC, a estrutura do pacote e o prefixo congelado. Calcula `declared_tick_lag = requested_tick - reported_tick` e retorna:

| Estado | Significado |
|---|---|
| `MEETS_DECLARED_TICK_POLICY` | A diferença declarada está dentro da tolerância congelada |
| `STALE_DECLARED_TICK` | A diferença declarada excede a tolerância |

Pacotes inconsistentes, sem autenticação válida ou de uma chave retirada da política de confiança geram erro antes da ingestão. O esquema anterior já verifica que o tick declarado corresponde ao modo de sensor informado; esta etapa não relaxa esse esquema.

`admit()` retorna `NOT_ADMITTED` e `link=null` para um pacote defasado. Nenhuma observação ou vínculo é gravado nesse caso. O recibo devolvido preserva os digests do envelope, da política e do recibo congelado, além da diferença e do estado. O envelope recusado não é persistido no BDR por esta ponte: o chamador deve preservá-lo se precisar de um histórico operacional das recusas. Os relatórios deste experimento preservam todos os envelopes e decisões, inclusive as recusas.

Para um pacote que atende à regra, `admit()` chama a ponte autenticada anterior. A deduplicação continua usando a identidade do pacote: mudar MAC, desafio ou identificador não fabrica posterioridade. Repetição exata volta a verificar a confiança atual, inclusive revogação.

## Releitura e controles negativos

`assess_history()` combina autenticação dos envelopes persistidos, verificação do histórico pela auditoria e avaliação de cada resultado sob a política congelada. Funciona após reabertura nativa e em outro processo. Não altera políticas, ocorrências, pesos ou resultados.

As APIs anteriores continuam disponíveis. Um chamador pode ingerir diretamente uma observação defasada pela ponte autenticada; a releitura da nova política a identifica como `STALE_DECLARED_TICK` e mantém a ocorrência histórica. Portanto este é um contrato opcional, não uma fronteira global de segurança ou um filtro de todas as entradas do produto.

| Cenário | Resultado |
|---|---|
| Leitura fiel, tolerância zero | Admitida; valor novo permanece fora das candidatas antigas |
| Leitura defasada em um tick, tolerância zero | Não admitida; hipótese permanece pendente |
| Mesma defasagem, tolerância de um tick | Admitida; coincide com candidata antiga, mas está errada para o tick solicitado |
| Modo defasado no tick zero | Admitida: o próprio simulador limita a leitura a zero, sem atraso declarado |
| Valor falso, tick atual e MAC válido do detentor da chave | Admitido; atende à regra e está errado no mundo simulado |
| Alteração sem MAC válido | Erro antes de escrever |
| Chave retirada da confiança atual | Erro antes de escrever |
| Tentativa de congelar política após ingestão direta | Erro, sem acrescentar política |

A regra não consulta `world_value()`. O avaliador usa a lei da simulação somente depois das decisões, para conservar os resultados positivos e negativos. Um teste faz a função lançar uma exceção no processo pai e confirma que a avaliação de atraso não depende dela.

Os campos `truth_established=false` e `learning_applied=false` continuam explícitos. O confronto mantém `answer=null`, `qualified=false` e `provenance_independence=NOT_ESTABLISHED`. A ingestão normal de um pacote admitido conserva seus efeitos anteriores; a avaliação não aplica aprendizado adicional. Um relato falso autenticado com tick atual passa pela regra e não vira fato automaticamente.

## Evidência e reprodução

- 78 testes locais aprovados: 20 novos e 58 anteriores.
- Sementes `20270123` e `20270124`: 86/86 verificações de integridade por semente.
- Política e histórico reproduzidos integralmente em dois processos sucessivos.
- Cobertos: política ausente, tolerância inválida, mudança após recusa, congelamento tardio após linha bruta ou vínculo, desvio pelas APIs anteriores, corrupção do registro, revogação na repetição e escopo de outra hipótese.
- Os dois relatórios da etapa de autenticação foram reproduzidos byte por byte.

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
  python -m pytest -q tests/test_trajectory_observer_freshness_probe.py \
  tests/test_trajectory_authenticated_observer_probe.py \
  tests/test_trajectory_controlled_observer_probe.py tests/test_trajectory_prediction_audit.py
PYTHONPATH=src python scripts/trajectory_observer_freshness_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so --seed 20270123 \
  --output /tmp/observer-freshness-development.json.gz
```

Repetir com `20270124` para a amostra reservada. Artefatos integrais em `benchmark-results/trajectory-observer-freshness-{development,reserved}.json.gz`. O CI dedicado reconstrói o runtime com BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a` e compara os relatórios completos descomprimidos.

A ponte pressupõe um escritor. Congelamento da tarefa, política, observação e vínculo são operações separadas, sem transação conjunta. A rotina não implementa chaves de produção, qualidade geral de sensores, detecção de mentira, previsão inédita ou aprendizado por erro. Núcleo, ABI móvel, MVP e console permanecem preservados.
