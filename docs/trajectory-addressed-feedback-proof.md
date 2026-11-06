# Oposição endereçada ao conteúdo ou à moldura

O leitor experimental `scripts/trajectory_addressed_feedback_probe.py` separa explicitamente dois alvos. O chamador precisa declarar se rejeita a candidata daquela recuperação (`CONTENT`) ou uma moldura específica que a recuperou (`FRAME`). Rejeitar conteúdo não implica culpar automaticamente sua trajetória, mesmo quando há apenas uma moldura geradora.

O experimento anterior de atribuição por unicidade permanece preservado em `trajectory_route_feedback_probe.py`, com seus resultados positivos e negativos. O novo leitor não o chama nem migra feedback antigo para penalizações de moldura. Não altera os leitores padrão, o console, a ABI, o MVP ou o OFF.IA.

## Contrato explícito

| Alvo solicitado | Vínculo armazenado | Efeito no leitor novo |
|---|---|---|
| `{"kind":"CONTENT"}` | Recibo integral da candidata, consulta, escopo e snapshot | Oposição local àquela recuperação; continuidade exige a mesma consulta e evidência compatível |
| `{"kind":"FRAME","frame_id":"..."}` | Mesmo recibo, mais moldura completa e proveniência de seus testemunhos | Oposição à moldura exata; pode afetar outras consultas/candidatas que dependam dela |

`CONTENT` não significa que o texto foi considerado falso em todos os contextos. É uma decisão local de disponibilidade sobre uma candidata endereçada. `FRAME` também não significa que o sistema descobriu um erro causal: o alvo é declarado pelo chamador e pode estar errado.

A moldura escolhida precisa pertencer a `candidate.frame_ids` no recibo atual. Um ID inexistente, uma moldura que não gerou a candidata, um alvo omitido, campos indevidos ou recibo alterado/antigo são recusados antes de escrever. Quando há várias molduras, o chamador pode escolher uma delas; as outras continuam oferecendo caminhos para a mesma candidata. Não existe prioridade de rota, votação ou seleção factual automática.

Exemplo de chamada de laboratório:

```python
binding = receipt(native, region, query, candidate_payload_id)
record_addressed(native, binding, "decisao-1", "operador", "oppose",
                 {"kind": "CONTENT"})

record_addressed(native, binding, "decisao-2", "operador", "oppose",
                 {"kind": "FRAME", "frame_id": chosen_frame_id})

withdraw_addressed(native, region, "retirada-2", "operador", "decisao-2")
view = addressed_read(native, region, query, enabled=True)
```

Os dois eventos são independentes. Retirar a oposição à moldura restaura sua contribuição, mas não retira uma oposição local ao conteúdo. Retirar somente o conteúdo também não reativa uma moldura ainda rejeitada. Apoio não suspende candidatas, não cancela oposição e não transforma evidência em verdade.

## Persistência e leitura

Um campo nativo separado, `addressed-feedback:<hash da região>`, armazena operações `FEEDBACK` e `WITHDRAW` em um só journal append-only. Cada operação tem seu endereço nativo. O envelope versionado JSON/UTF-8/Base64 preserva strings sem alterar a ABI de texto. Nenhuma operação ou referência de avaliação é ingerida na região de aprendizado.

O replay mantém cada feedback original com estado ativo/inativo e a retirada correspondente. A retirada referencia endereço, ID e digest integral de uma ocorrência anterior; origem declarada diferente, alvo já retirado ou histórico inconsistente são recusados. Reenvios exatos de feedback e retirada não acrescentam operações; reutilizar uma identidade com conteúdo ou tipo de alvo diferente falha. Reenviar feedback retirado não o reativa. Nova decisão exige novo ID e recibo atual válido.

As escritas confirmam `flush` antes de retornar sucesso. Uma falha de flush tem resultado incerto e exige reabrir/conferir antes de repetir. Cada append é uma operação; não há substituição atômica de uma decisão por outra, nem transação conjunta com observações. As funções pressupõem um único escritor; não fornecem lock de serviço ou autenticação. A identidade do operador é declarada, e os digests não são assinaturas.

O leitor aplica primeiro o feedback antigo como oposição ao conteúdo, preservando a política anterior. Para eventos novos, valida o digest do recibo e reconstrói a leitura histórica pelo prefixo de observações. A oposição à moldura só se aplica enquanto estrutura, ID, testemunhos e todas as origens de seus payloads coincidem. Repetir uma ocorrência de testemunho muda a proveniência e impede o transporte. Uma candidata com outra moldura sobrevivente continua disponível.

Todas as candidatas, origens e evidências permanecem em `raw_view`. O envelope tem `answer=null`, `qualified=false`, `selection_used=false`, qualidade factual `NOT_EVALUATED` e aprendizado geral `NOT_ESTABLISHED`. O recurso fica desativado por padrão; não está conectado automaticamente ao laboratório/console existente.

## Resultados controlados

Seeds `20270111` e `20270112`, cada um com cinco cenários em símbolos legíveis e sob renomeação injetiva. Eles mudam entidades/valores lexicais, mas compartilham templates e não são amostras independentes de linguagem natural. Os conteúdos da segunda entidade já estão observados; a segunda consulta e seu payload não são alvos do feedback. Os alvos da operação vêm de endereços observados, não de respostas esperadas. Referências são usadas somente na pontuação posterior.

Contagens: **esperados recuperados / extras / perdas** na segunda consulta.

| Cenário | Antes | Depois | Observação |
|---|---|---|---|
| Rejeitar somente o conteúdo na primeira consulta | 1 / 1 / 0 | 1 / 1 / 0 | Nenhuma penalização de moldura é inferida; a primeira candidata fica vetada localmente |
| Rejeitar explicitamente a moldura do extra | 1 / 1 / 0 | 1 / 0 / 0 | Oposição declarada alcança outro payload pela mesma moldura |
| Rejeitar explicitamente uma moldura correta | 1 / 0 / 0 | 0 / 0 / 1 | A decisão errada ainda propaga uma perda |
| Escolher uma entre várias molduras geradoras | 1 / 0 / 0 | 1 / 0 / 0 | Outra moldura preserva a candidata |
| Gêmeo com referência diferente oculta | 1 / 1 / 0 | 0 / 1 / 1 | Mesmas observações, alvo e leitura não distinguem outra relevância |

O gêmeo preserva observações, recibo, feedback e leitura completa idênticos ao caso positivo; só o contrato do avaliador muda. A separação de alvos evita uma atribuição implícita, mas não decide qual alvo é correto ou qual intenção é relevante. No controle errado, a perda é deliberadamente mantida como resultado negativo.

Todos os cenários testam retirada, reenvio sem reativação, consulta read-only, preservação do histórico, modo desativado e igualdade integral depois de reabrir o BDR. Retirar o evento devolve a disponibilidade anterior, inclusive quando isso restaura um extra.

## Reprodução e validação

Ambos os seeds passaram em **159/159 verificações de integridade**. Os relatórios completos foram repetidos e coincidiram byte a byte. Eles guardam observações, consultas, recibos, alvo solicitado, feedback/projeção, retirada, leitura completa e scores exclusivos do avaliador.

| Relatório | Digest, excluindo `report_content_sha256` |
|---|---|
| `benchmark-results/trajectory-addressed-feedback-development.json` | `ab7022f6abe0ea7a36fb5d30fc197e81e40944b58e6dc25e3a439dd625ba1993` |
| `benchmark-results/trajectory-addressed-feedback-reserved.json` | `dcc296f36411a370e0b5c280bc59168d0f03220c3ca91a88e7ceee2168cb24aa` |

Passaram **73 testes locais distintos**: 19 novos e 54 regressões de transferência anterior, ledger, veto, continuidade e retirada. Incluem alvos inválidos, atribuição explícita entre várias molduras, suporte sem qualificação, feedback antigo sem conversão automática, independência das retiradas, identidade de operação, recibo adulterado/antigo, controles como regiões de aprendizado, alteração de proveniência e persistência. Compilação Python e `git diff --check` passaram. Sem biblioteca implícita, os 19 contratos novos foram pulados como esperado; o job nativo informa o caminho explicitamente e não pode aprová-los assim. O BDR está fixado em `317882a00f041fc1568ff986af8016b09453f21a`.

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_addressed_feedback_probe.py

PYTHONPATH=src python scripts/trajectory_addressed_feedback_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --seed 20270111 --output /tmp/addressed-development.json
```

A CI tem um job focado `addressed-feedback`: compila o BDR fixado, executa as suítes nova e anterior, reproduz ambos os seeds e compara os arquivos integrais aos relatórios versionados. Isso não remove verificações do job cumulativo existente. A aprovação remota deste incremento deve ser conferida no commit publicado.

Na verificação do commit anterior `90831a7`, sete workflows aplicáveis já estavam aprovados, incluindo os três gerais que antes falharam por setup nativo. O workflow cumulativo de trajetórias ainda estava em execução e o condicional estava ignorado. Não se confunde esse status parcial com aprovação integral.

## Limites e próxima investigação

O avanço é representar o alvo da decisão como parte dos dados persistentes, com consequências diferentes e reversíveis. Não demonstra descoberta autônoma de erro, compreensão geral, verdade factual ou pesos aprendidos. Não há transferência entre molduras diferentes, autenticação de fonte, validação de confiabilidade do operador, NLP de correções ou ganho de escala. Reconstruções históricas e enumeração de molduras continuam custosas; as baterias são pequenas e correlacionadas.

A próxima investigação pode endereçar um testemunho específico dentro da moldura, para distinguir uma demonstração inadequada de uma transformação inadequada, preservando caminhos alternativos e os controles de feedback errado. Qualquer ampliação deve ser comparada ao contrato atual sem converter referências do avaliador em aprendizado. O PR permanece em rascunho.
