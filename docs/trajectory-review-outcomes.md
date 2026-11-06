# Resultado posterior à decisão: comparação observável e avaliação declarada

O laboratório local agora registra um resultado vinculado a uma decisão anterior. O evento referencia dois recibos completos: o da decisão e um recibo posterior escolhido explicitamente pelo chamador. Preserva separadamente a diferença na recuperação e a avaliação declarada pelo operador. Não incorpora exemplos, escolhe candidatas, reforça rotas ou verifica qualidade factual.

## Ciclo de uso

1. Abra a revisão com `open_review` e registre `select`, `defer` ou `reject_all`, conforme `trajectory-review-decisions.md`.
2. Se decidir incorporar exemplos, use operações explícitas `observe`. A decisão não executa esse passo automaticamente.
3. Abra outra revisão com a **mesma consulta e os mesmos conjuntos oferecidos, ordem e proveniência**. Guarde o novo `receipt_id`. Sem mudança de estado, `open_review` pode retornar o recibo original por idempotência; isso permite registrar ausência de mudança.
4. Registre o resultado usando o ID da decisão e o recibo que deseja comparar.

Substitua os IDs abaixo pelos retornados na sua sessão:

```json
{"op":"record_review_outcome","scope":"principal","decision_id":"decisao-1","after_receipt_id":"COPIE_O_RECEIPT_ID_POSTERIOR","outcome_id":"resultado-1","actor_id":"operador-1","judgement":"uncertain","reason":"Ainda não sei se o conteúdo recuperado atende à pergunta."}
```

`judgement` aceita `helped`, `unchanged`, `worsened` ou `uncertain`. O texto `reason` é obrigatório, não vazio e tem até 2000 caracteres. IDs de resultado e operador têm até 128 caracteres. A identidade declarada precisa coincidir com a da decisão, mas não é autenticada. Nenhum desses rótulos é inferido automaticamente dos contadores de candidatas.

```json
{"op":"review_outcomes","scope":"principal"}
```

O retorno conserva recibos, decisões e resultados, incluindo reavaliações posteriores com IDs novos. Não elege um resultado como verdade ou decisão atual.

## Diferença observável

`comparison` mantém três conjuntos separados: `raw`, `available` e `withheld`, correspondendo a candidatas brutas, disponíveis e suspensas por feedback. Cada um inclui contagens antes/depois, IDs acrescentados, removidos, preservados e IDs cujo pacote de evidências mudou. Os textos e testemunhos completos permanecem nos recibos referenciados; não são duplicados integralmente no evento de resultado.

Essa separação evita chamar suspensão por feedback de desaparecimento do conteúdo bruto. `learning_context_changed` compara o digest da região de aprendizagem, enquanto `full_review_changed` compara a revisão completa, que também pode mudar com feedback. IDs e contagens de recuperação não certificam a adequação das candidatas à pergunta.

O evento mantém:

- `retrieval_change_means_quality_improvement=false`;
- `causal_attribution=NOT_ESTABLISHED`;
- `offer_application_verified=false`;
- `factual_quality_status=NOT_EVALUATED`.

O recurso não verifica se os exemplos escolhidos foram realmente incorporados, se foram a causa da mudança ou se informações de outra origem interferiram. Uma candidata extra pode ser útil ou indevida. Um operador pode declarar `helped` mesmo sem mudança no conjunto; o sistema preserva o relato e a comparação, sem certificar ou corrigir esse julgamento.

## Referências, reenvio e integridade

O resultado referencia o ID e o digest integral da ocorrência exata da decisão. Os dois recibos precisam existir no mesmo escopo e corresponder à mesma consulta e conjunto oferecido. A sequência local do recibo usado como posterior não pode anteceder a do recibo da decisão; o mesmo recibo é permitido para uma comparação sem mudança. Essa ordem é do diário, não uma medição de tempo de parede.

As duas fotos já estão armazenadas. Por isso, o registro pode ser feito depois de novas observações: ele compara **os recibos explicitamente indicados**, não captura implicitamente o estado atual. Para avaliar o presente, abra um recibo atual antes de registrar o resultado.

Reenvio com mesmo ID e conteúdo integral retorna `EXACT_REPLAY`. Reutilizar ID com conteúdo diferente é rejeitado. Escopo indevido, decisão inexistente, recibo incompatível, outra identidade declarada, comparação adulterada ou história inválida de resultados são rejeitados antes de acrescentar evento. Histórias de resultados inválidas não produzem uma saída parcial.

Os eventos usam `operator-review-outcomes:<hash da região>` no armazenamento nativo BDR, fora da região de aprendizagem. Aplicam-se os limites existentes de **128 registros por campo** e **256 KiB por registro canônico**. `record_review_outcome` confirma flush antes de devolver `persisted=true`. `operator_judgement_recorded=true` indica somente o registro da declaração; `examples_incorporated_into_learning=false` descreve o efeito desta operação, não nega incorporações explícitas feitas anteriormente.

As operações e relatórios anteriores continuam preservados. Este incremento não altera o motor, a ABI, a UI ou o servidor de produto.

## Validação programada

O relatório percorre **16 tentativas programadas** nos catálogos de pressão e potência: para cada uma das oito situações, um contraste e uma demonstração adequada. A incorporação é feita explicitamente pelo avaliador através de `observe`; o registro da decisão e do resultado não a executa.

O relatório conserva oito comparações com uma candidata bruta adicional e oito com o conjunto bruto inalterado. Os rótulos `helped` e `unchanged` são atribuídos pelo programa do cenário e não são avaliações humanas. Testes separados exercitam os quatro rótulos declarados, inclusive `worsened` e `uncertain`, sem deduzir sua correção.

As verificações comparam referência exata da decisão, idempotência, histórico local e estrangeiro, revisão antes/depois do registro, ausência de promoção causal/factual e igualdade completa após fechar e reabrir o armazenamento. A comparação preservada é recalculada dos recibos ao ler o diário.

Relatório: `benchmark-results/trajectory-review-outcomes.json`. SHA-256 canônico sem o próprio campo de hash: `bd69ab6881593909f4bfc9396a5b927f6f3fba5b160c978a21f64f8d04e1036f`.

Passaram **43 testes locais**, dezenove novos e 24 regressões da sessão e do diário de decisões. Cobrem os quatro rótulos declarados, snapshots incompatíveis ou anteriores, referência histórica, suspensão por feedback separada da memória bruta, comparação adulterada, idempotência, reabertura e protocolo real no terminal com Unicode e quebras de linha. Passaram **160/160 verificações** nos 16 casos. O relatório repetiu byte a byte; o relatório anterior do diário de decisões também reproduziu integralmente. Compilação Python e `git diff --check` passaram. A CI do novo incremento fica pendente após publicação.

```sh
PYTHONPATH=src python scripts/trajectory_review_outcomes_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output /tmp/review-outcomes.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m pytest -q tests/test_trajectory_review_outcomes.py
```

`human_evaluation_status=NOT_PERFORMED` e `general_learning_status=NOT_ESTABLISHED` permanecem explícitos. A próxima etapa é usar o ciclo completo com escolhas e observações reais, preservando tanto a avaliação do operador quanto as evidências que permitam contestá-la.

O ciclo pode ser conduzido pelo [assistente de terminal](trajectory-review-wizard.md), que administra os IDs de recibos, separa escolha e incorporação e permite retomar decisões.
