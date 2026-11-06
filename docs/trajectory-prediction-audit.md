# Hipóteses registradas antes de observações posteriores

`scripts/trajectory_prediction_audit.py` acrescenta um journal nativo experimental para congelar um conjunto de hipóteses recuperadas e compará-lo com ocorrências registradas depois. O registro preserva a consulta, o prefixo de memória, o corte de sequência e todas as candidatas observadas pelo leitor bruto de molduras. Não escolhe uma candidata automaticamente.

As candidatas são conteúdos já observados antes do corte. O recurso audita sua recorrência posterior; não implementa previsão de valores inéditos, modelo causal ou julgamento de verdade. Uma observação fora do conjunto congelado permanece fora dele, mesmo se sua ingestão normal a tornar recuperável pela memória atual.

## Contrato e separação de espaços

```python
first = forecast(native, region, query, "hipotese-1", "operador")

# O fluxo normal de ingestão registra uma observação posterior.
# O auditor recebe seu endereço, não recebe uma resposta esperada.
observe_outcome(native, region, "hipotese-1", "observacao-1", "observador",
                [region, source_id, sequence])

result = reconcile(native, region, "hipotese-1")
```

`forecast()` grava a hipótese somente no campo separado `prediction-audit:<hash da região>`. A consulta e as candidatas não são inseridas na trilha de aprendizado. O recibo contém o digest das observações, quantidade de entradas, maior sequência e leitura integral com seus candidatos, molduras e origens. A política de origem é explicitamente `RAW_OBSERVED_FRAME_CANDIDATES`; não é uma captura do seletor filtrado por feedback.

`observe_outcome()` referencia uma ocorrência que já existe na região principal. A observação entra pelo fluxo normal de ingestão, sob responsabilidade do chamador; o auditor não a cria ou copia. O endereço deve corresponder exatamente a uma entrada nativa de `user_turn`/`user_assertion`, com sequência estritamente maior que o corte do recibo. Entradas antigas, geradas, inexistentes ou de outra região são recusadas antes de escrever um vínculo.

O vínculo entre a pergunta e a observação é fornecido pelo chamador, não descoberto semanticamente. Uma observação nova sem vínculo explícito deixa o registro pendente. A verificação temporal usa ordem lógica de ingestão, não autentica a hora do acontecimento no mundo.

`reconcile()` reconstrói o prefixo anterior, verifica seu digest e reproduz a leitura congelada. Também verifica que cada observação vinculada continua presente com os mesmos cinco campos de origem. O confronto compara textos exatamente; não normaliza linguagem nem infere equivalência semântica. Essa leitura não grava feedback, pesos, fatos ou novas observações. `learning_applied=false` refere-se ao confronto: a ingestão normal da observação, realizada antes pelo chamador, continua tendo seus efeitos normais.

## Estados observáveis

| Estado | Significado |
|---|---|
| `PENDING` | Nenhuma ocorrência posterior válida foi explicitamente vinculada |
| `MATCHES_ONLY_CANDIDATE` | Um conteúdo posterior coincide com a única candidata congelada |
| `MATCHES_ONE_OF_MULTIPLE` | Coincide com uma das alternativas congeladas; não promove essa alternativa a fato |
| `OUTSIDE_FROZEN_SET` | O conteúdo posterior não pertence ao conjunto registrado |
| `DIVERGENT_LATER_OBSERVATIONS` | Há mais de um conteúdo posterior distinto; pode ser mudança de estado ou divergência de fontes |
| `NO_CANDIDATES_AT_CUTOFF` | Não havia candidatas antes da observação vinculada |
| `UNVERIFIABLE_HISTORY` | O prefixo ou uma ocorrência vinculada não pode mais ser verificado |

Repetições não resolvem divergência por maioria. Uma observação nativa não pode ser contada duas vezes no mesmo registro por meio de IDs de resultado diferentes. Ocorrências diferentes com texto idêntico mantêm suas proveniências, sem aumento de confiança factual. Se uma observação for vinculada a mais de um registro anterior elegível, isso representa evidência compartilhada, não ensaios independentes.

Todas as respostas mantêm `answer=null`, `qualified=false`, `selection_used=false`, `selected_target=null`, `proposal_payload_id=null`, qualidade factual `NOT_EVALUATED` e independência `NOT_ESTABLISHED`. Não existe ação automática de aprender ou penalizar uma trajetória a partir desse estado.

## Persistência, identidade e reabertura

O journal append-only usa operações versionadas `FORECAST` e `OUTCOME` em JSON/UTF-8/Base64, preservando strings literais sem mudar a ABI. Cada resultado vincula endereço e digest integral de um registro anterior. A leitura valida schemas, digests, identidades e ordem dos vínculos. Alterações inconsistentes são recusadas; a ausência do prefixo nativo produz histórico não verificável.

Reenvios exatos não acrescentam operações. Reutilizar um ID de hipótese com outra consulta/origem declarada, ou um ID de resultado com outro vínculo/observador, falha. Reenviar a mesma hipótese depois de novas entradas devolve o recibo original: não desloca o corte, não atualiza candidatas antigas e não transforma retrospectivamente novidade em previsão. É preciso outro ID para uma nova captura. O reenvio reconhece uma operação histórica; a verificação atual é feita por `reconcile()`.

As gravações e reenvios confirmam `flush` antes de retornar sucesso. Uma falha de flush deixa o resultado incerto e exige conferência antes de continuar. As funções pressupõem um único escritor; não há transação entre registrar a hipótese, ingerir a observação e vinculá-la, nem autenticação dos atores. Os consumidores atuais e seus seletores não foram integrados a esse journal.

## Controles positivos e negativos

Os seeds `20270117` e `20270118` usam o workload simbólico de colchetes da etapa anterior, com alfabeto/transformação sorteados e os mesmos templates. São oito cenários pequenos e correlacionados por seed, não uma amostra independente de fenômenos reais.

| Cenário | Resultado registrado |
|---|---|
| Cópia literal como único caminho, nova ocorrência igual | `MATCHES_ONLY_CANDIDATE` |
| Duas candidatas e nova ocorrência igual a uma delas | `MATCHES_ONE_OF_MULTIPLE` |
| Novo valor posteriormente recuperável, ausente no corte | `OUTSIDE_FROZEN_SET` |
| Duas ocorrências posteriores com conteúdos diferentes | `DIVERGENT_LATER_OBSERVATIONS` |
| Ocorrência marcada como gerada | Vínculo recusado; permanece `PENDING` |
| Tentativa de vincular ocorrência anterior ao corte | Vínculo recusado; permanece `PENDING` |
| Memória vazia no registro, depois nova observação | `NO_CANDIDATES_AT_CUTOFF` |
| Hipótese copiada e declarada como nova entrada de usuário | `MATCHES_ONE_OF_MULTIPLE`, com independência não estabelecida |

O último caso produz **exatamente os mesmos dados e comparação** que a ocorrência declarada normal do segundo cenário. O avaliador interpreta a origem de forma diferente, mas essa informação não está presente no contrato nativo. Portanto, coincidência e posterioridade não comprovam independência, autenticidade ou verdade. Os observadores dos testes são programados; nenhuma confirmação externa independente foi realizada.

Os controles também mostram que quatro repetições de um conteúdo não vencem uma ocorrência diferente; o estado permanece divergente, sem seleção factual. Conteúdos posteriores novos podem ser recuperados pela memória atual sem alterar o conjunto anterior. O auditor conserva a diferença entre saber antes e incorporar informação depois.

## Validação e reprodução

**17 testes locais passaram**, incluindo persistência em três processos Python separados: o primeiro registra as hipóteses, o segundo ingere e vincula a observação, e o terceiro recupera a comparação integral idêntica. Os outros testes cobrem corte temporal, estado pendente sem vínculo, candidatos congelados, falta de cobertura, divergência sem votação, reenvios, identidades conflitantes, regiões de controle, prefixo indisponível, recibo adulterado e IDs com Unicode/aspas/quebras de linha.

Ambos os seeds passaram em **67/67 verificações de integridade**. Os dois relatórios completos foram repetidos e coincidiram byte a byte, preservando observações iniciais/posteriores, hipóteses, vínculos e comparações completas. Compilação Python e `git diff --check` passaram. Sem biblioteca implícita, os 17 testes nativos foram pulados; o job dedicado exige caminho explícito.

| Relatório em `benchmark-results/` | Digest do conteúdo, excluindo `report_content_sha256` |
|---|---|
| `trajectory-prediction-audit-development.json.gz` | `cd6639e8f1d9c9879195eb400d074ee9ac431f32f46d195864d3405c79eae92d` |
| `trajectory-prediction-audit-reserved.json.gz` | `c78c3a8d53ac9831b3b8e2dde72c13271530857dc16ad1d81ec0f695e7cb6d9a` |

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_prediction_audit.py

PYTHONPATH=src python scripts/trajectory_prediction_audit.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --seed 20270117 --output /tmp/prediction-audit-development.json.gz
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. O novo job focado `prediction-audit` compila essa biblioteca, executa os testes, reproduz ambos os seeds e compara os JSON completos descomprimidos. O status remoto precisa ser conferido no commit publicado. O commit anterior `5bc88ac` terminou com oito workflows aplicáveis aprovados; o condicional foi ignorado. Os contratos e relatórios anteriores não foram modificados.

## Próximo limite

Este avanço fornece um registro temporal verificável das hipóteses recuperadas e das observações vinculadas. Ainda faltam observações de um processo externo cuja geração não consulte a hipótese, verificação da associação com a pergunta e uma política explícita de aprender com seus resultados. Um observador independente em ambiente controlado pode ser a próxima etapa, preservando previsões e evidências em espaços diferentes e mantendo os casos de autocópia e divergência. Não há descoberta causal, confiança calibrada ou aprendizado geral demonstrado; o PR permanece em rascunho.
