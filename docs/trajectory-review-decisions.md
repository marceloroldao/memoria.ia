# Recibo de revisão e decisão explícita do operador

A sessão local agora permite registrar o que foi apresentado e a decisão declarada pelo operador. O fluxo usa três operações: `open_review`, `record_review_decision` e `review_decisions`. Escolher, adiar ou rejeitar não incorpora demonstrações, não altera rotas e não estabelece a verdade dos textos. A avaliação com pessoas reais continua pendente.

## Executar o ciclo

Use o lançador de `trajectory-feedback-session.md`. Para abrir uma revisão persistente:

```json
{"op":"open_review","scope":"principal","text":"Qual é a cor do FIESTA?","offers":[{"offer_id":"exemplo-1","provenance":"Origem declarada a conferir","examples":[{"source_text":"Qual é a cor do FORTE?","target_text":"A cor do Forte é verde."}]}]}
```

`result.event` contém o recibo completo, com `receipt_id`, digest da região de aprendizagem, consulta e `reviewed_result`. Este último preserva a leitura, recibos de candidatas, diagnóstico, exemplos oferecidos, sua ordem e proveniência declarada. O SHA-256 liga esses dados ao identificador. É verificação de consistência de conteúdo, não assinatura, autenticação de origem ou proteção contra um escritor malicioso com acesso direto ao armazenamento.

Copie o `receipt_id` retornado. No exemplo abaixo, substitua o texto `COPIE_O_RECEIPT_ID` pelo identificador real:

```json
{"op":"record_review_decision","scope":"principal","receipt_id":"COPIE_O_RECEIPT_ID","decision_id":"decisao-1","actor_id":"operador-1","choice":"defer","offer_id":null,"reason":"Ainda preciso conferir a origem e a adequação do exemplo."}
```

| `choice` | `offer_id` | Significado registrado |
|---|---|---|
| `select` | ID de um conjunto presente no recibo exato | O chamador declara a escolha desse conjunto, marcado ou não pela revisão |
| `defer` | `null` | O chamador preserva dúvida e adia a escolha |
| `reject_all` | `null` | O chamador declara rejeição de todos os conjuntos apresentados |

`reason` é obrigatória, não vazia e limitada a 2000 caracteres. `actor_id` e `decision_id` são textos não vazios de até 128 caracteres. A identidade é fornecida pelo chamador e não autenticada. Registrar uma escolha não prova que uma pessoa real a fez, que conferiu a origem ou que escolheu corretamente.

Para consultar os registros:

```json
{"op":"review_decisions","scope":"principal"}
```

O retorno preserva todos os recibos e eventos em sequência de gravação. Não há um mecanismo que eleja automaticamente uma decisão como atual ou transforme o último evento em comando de aprendizagem. Uma nova decisão usa ID novo; eventos anteriores não são apagados ou reescritos.

## Recibos, reenvios e mudança de contexto

- Abrir novamente a mesma revisão no mesmo estado devolve `EXACT_REPLAY`, sem acrescentar recibo.
- Reenviar uma decisão com mesmo ID e conteúdo integral devolve `EXACT_REPLAY`, sem novo evento.
- Reutilizar o ID com decisão, justificativa, identidade ou recibo diferente é rejeitado.
- Um recibo de outro escopo ou um conjunto que não conste no recibo é rejeitado.
- Para uma decisão nova, a revisão é reconstruída e precisa coincidir integralmente com a preservada. O digest da região também precisa coincidir.
- Acrescentar observações invalida o recibo para decisões novas, mesmo se a resposta visível permanecer igual. Alterar o estado de feedback também pode invalidá-lo. Deve-se abrir nova revisão.
- Uma decisão já registrada pode ser reenviada exatamente depois da mudança de contexto; continua sendo um evento histórico idempotente.

Abrir a revisão e gravar uma decisão são duas operações separadas. Abrir um recibo não exige que uma decisão seja feita depois. O laboratório exige um único escritor serializado por diretório; não oferece transação entre a região de aprendizagem e os campos de controle para escritores que ignorem o lock.

## Separação entre auditoria e aprendizagem

Recibos são armazenados uma vez por digest em `operator-review-receipts:<hash da região>`. Decisões ficam em `operator-review-decisions:<hash da região>` e referenciam o recibo, evitando repetir a revisão completa em cada evento. Ambos usam o armazenamento nativo BDR e envelope versionado JSON/UTF-8/Base64.

`open_review` **persiste os textos oferecidos no recibo de auditoria**. Por isso, informa `audit_contains_offered_texts=true`. O `offers_recorded=false` dentro da revisão preservada descreve a operação de revisão somente leitura que está sendo fotografada; não significa ausência de cópia de auditoria. O campo explícito `examples_incorporated_into_learning=false` informa o efeito sobre a aprendizagem. A região consultada por `query`, `diagnose` e `review_examples` não incorpora esses controles.

`record_review_decision` confirma `operator_choice_recorded=true`, mas mantém `examples_incorporated_into_learning=false` e `learning_performed=false`. O `selection_used=false` do envelope se refere à seleção factual do motor; a escolha declarada está no evento `choice`/`offer_id` e não é aplicada automaticamente.

Se o operador decidir incorporar um exemplo, deve registrá-lo explicitamente por `observe`, com origem apropriada. Esse passo é separado do registro da decisão. O recurso atual não registra automaticamente o efeito posterior de uma incorporação nem interpreta justificativas como fatos ou instruções.

## Integridade e limites

O laboratório admite até **128 recibos e 128 decisões por escopo**, com limite de **256 KiB por registro canônico antes de Base64**. Um recibo muito grande é rejeitado antes de gravar; reduza o histórico ou os conjuntos oferecidos. Não se salva uma revisão parcial silenciosamente. Histórias com codec inválido, referência ausente, digest de recibo inconsistente ou identidades duplicadas são rejeitadas. Esses limites não são garantias de desempenho em produção.

`open_review` e `record_review_decision` confirmam flush nativo antes de devolver `persisted=true`. As operações anteriores permanecem preservadas. Não há migração da ABI, autenticação de operadores, UI ou integração ao servidor de produto neste incremento.

O avaliador percorre oito fixtures programadas, preservando uma revisão por fixture e registrando as três modalidades: **oito recibos e 24 decisões**. Os registros usam `actor_id=scripted-operator` e justificativa explícita de teste; não são apresentados como decisões humanas. Compara a leitura completa e os históricos local e estrangeiro antes/depois, reenvios, persistência e igualdade após fechar/reabrir o armazenamento.

Relatório: `benchmark-results/trajectory-review-decisions.json`. SHA-256 canônico sem o próprio campo de hash: `ae50cd67b7eba42ba78e5f217da701bf99717301a57a107477a81c5b7da5b138`.

Passaram **39 testes locais**, catorze novos e 25 regressões da revisão de exemplos e da sessão. Os testes incluem recibo obsoleto, reenvio histórico, ordem e proveniência distintas, mudança de feedback, recusa de decisões inválidas sem gravação, rejeição de história de controle corrompida e protocolo real pelo terminal com Unicode e quebras de linha. Passaram **96/96 verificações** nos oito casos; o relatório completo repetiu byte a byte. O relatório anterior de revisão de demonstrações também reproduziu sem alterações. Compilação Python e `git diff --check` passaram. A CI do novo incremento fica pendente após publicação.

```sh
PYTHONPATH=src python scripts/trajectory_review_decisions_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output /tmp/review-decisions.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m pytest -q tests/test_trajectory_review_decisions.py
```

`human_evaluation_status=NOT_PERFORMED` e `general_learning_status=NOT_ESTABLISHED` permanecem explícitos. O próximo passo é usar esse registro com escolhas reais e medir separadamente o efeito de exemplos incorporados depois, preservando decisões adiadas e tentativas sem melhora.
