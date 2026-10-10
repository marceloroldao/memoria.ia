# Relações entre rotas: diagnóstico estrutural e intervenções persistidas

O novo diagnóstico distingue ausência de resultados, uma rota ativa, conjuntos de raízes iguais e conjuntos diferentes. Também expõe interseção parcial e testemunhos compartilhados. Todas as candidatas, origens e propostas da composição anterior permanecem idênticas. O diagnóstico não aprende penalizações, escolhe respostas nem declara qual rota está certa.

## O que os sinais significam

| Estado | Significado estrutural | Limite |
|---|---|---|
| `NO_ROUTE_OUTPUT` | Nenhuma rota produziu candidata | Pode ser falta de cobertura mesmo com conteúdo registrado |
| `ONE_ROUTE_OUTPUT` | Só uma rota produziu candidatas | A única rota pode estar errada ou trazer múltiplas raízes |
| `SAME_ROOT_SET` | Rotas ativas recuperaram o mesmo conjunto | Pode haver duas cores concorrentes ou relevância oculta diferente |
| `DIFFERENT_ROOT_SETS` | Rotas ativas recuperaram conjuntos distintos | Não identifica automaticamente contradição factual nem qual candidata é falsa |

Cada comparação inclui raízes comuns, exclusivas de cada rota, raízes de payload usadas nos testemunhos e pares de testemunhos compartilhados. Sobreposição de raízes de treinamento mostra reutilização de payloads; ela não identifica necessariamente a mesma ocorrência nativa. Pares compartilhados preservam os IDs de origem/destino da raiz e o segmento observado. Nem a presença nem a ausência de sobreposição estabelecem independência estatística ou factual: `evidence_independence_status=NOT_ESTABLISHED`.

A sinalização depende apenas das candidatas e dos testemunhos já transportados pela composição. Nenhum vocabulário, referência do avaliador, regra de verdade ou interpretação de texto entra na classificação dos conjuntos. `factual_contradiction_status` e qualidade factual continuam `NOT_EVALUATED`; `selection_used=false`.

## Intervenções no mesmo armazenamento nativo

Três intervenções preservam o prefixo bruto inteiro e apenas acrescentam observações. Cada uma é testada de duas maneiras: nos cenários completos separados e por gravação antes/depois em um único diretório BDR. A leitura após append precisa coincidir com o cenário completo; depois o BDR é reaberto e a leitura completa precisa permanecer igual.

| Observações acrescentadas | Mudança na consulta literal |
|---|---|
| 9 entradas de demonstração de transformação compatível | Uma rota passa a duas rotas com a mesma raiz; o conteúdo isolado continua com uma ocorrência |
| 40 entradas de cor concorrente/repetições e barreiras | Ambas as rotas concordam no conjunto de duas raízes; origens ficam em 20/1 e não decidem o resultado |
| 11 entradas de demonstração de transformação alternativa e conteúdo correspondente | Cópia recupera a raiz original; transformação recupera a original e uma extra; interseção parcial permanece explícita |

O estado `SAME_ROOT_SET` não muda quando uma raiz vira duas raízes compartilhadas. Por isso o diagnóstico também expõe multiplicidade geral e dentro de cada rota. Na interseção parcial, ele distingue a raiz comum da exclusiva da transformação, preservando ambas. Na divergência disjunta, cada rota tem uma raiz exclusiva.

Essas intervenções comprovam persistência de observações e mudança do diagnóstico após append. Os leitores continuam reconstruindo suas molduras a partir da janela bruta; não implementamos aprendizado incremental de peso, reforço por acerto ou penalidade por erro. Consultas não são inseridas como observações, e conteúdo gerado continua em campo separado, fornecendo somente barreiras de sequência.

## Resultados positivos e negativos

A bateria usa 14 cenários com quatro consultas cada, em texto legível e em renomeação injetiva: **112 consultas por seed**. As quatro consultas são pergunta em maiúsculas, pergunta literal em minúsculas, paráfrase observada e entidade ausente. Desenvolvimento `20261229`; reservado `20261230` muda entidades e valores. Templates e relações são correlacionados; isso não é uma amostra independente de linguagem natural.

Em ambos os seeds, passaram **377/377 verificações de integridade**. Elas incluem projeções nativas, exclusões, read-only, reabertura, preservação integral dos resultados anteriores, paridade de scores/relações sob renomeação, dois pares de gêmeos com referências ocultas e as três intervenções reais em um armazenamento. O diagnóstico preservou as candidatas em todas as 112 consultas.

A composição subjacente teve **72/112 conjuntos exatos, 60 recuperações esperadas, 20 extras e 24 perdas**. Não houve melhora de recuperação neste incremento; a alteração é um diagnóstico. A contagem é por consulta, não por fatos distintos.

| Estado observado | Consultas | Conjuntos exatos | Recuperações esperadas | Extras | Perdas |
|---|---:|---:|---:|---:|---:|
| Nenhuma rota | 48 | 28 | 0 | 0 | 20 |
| Uma rota | 54 | 40 | 50 | 14 | 4 |
| Mesmo conjunto | 6 | 4 | 6 | 2 | 0 |
| Conjuntos diferentes | 4 | 0 | 4 | 4 | 0 |

Essa tabela usa referências apenas no avaliador. As quatro consultas com conjuntos diferentes têm extras, mas **16 dos 20 extras ocorrem sem divergência**: 14 com uma rota e dois com conjuntos iguais. Logo, divergência não é detector suficiente de erro. Concordância também não garante relevância: o gêmeo de concordância usa exatamente as mesmas observações e leitura positiva, enquanto o avaliador exige resultado vazio. Há ainda um segundo gêmeo para o cenário composto comum.

Os controles mostram que ausência de candidata pode significar ausência de conteúdo ou cobertura insuficiente; uma associação errada pode vir de uma rota única; duas rotas podem concordar sobre conteúdos concorrentes. Não se pode converter esses sinais em rótulos de verdade/falsidade sem outras observações ou critérios.

Qualidade de recuperação permanece `FAIL_EXTRA_OR_MISSING_CONTENT`; relevância oculta, `FAIL_INDISTINGUISHABLE_INPUTS`; qualidade factual, `NOT_EVALUATED`.

A rota nativa inalterada (`top_k=16`) teve, em cada subconjunto legível de 56 consultas, zero conjuntos exatos, 42 recuperações esperadas, 510 extras e zero perdas. Na renomeação, teve 20 conjuntos exatos com referências vazias, zero recuperações esperadas, zero extras e 42 perdas. Renomeação altera a tokenização nativa; não demonstra invariância dessa rota. O subconjunto de consultas e os cenários mudaram, portanto esses números não são comparáveis diretamente aos anteriores.

## Validação e reprodução

**59 testes de regressão passaram**, incluindo os dois leitores, composição, classificação de conjuntos, interseção parcial, gêmeos, mascaramento de metadados e preservação do endereço/origens da candidata antiga após append no mesmo BDR. Ambos os resumos e hashes completos reproduziram byte a byte em nova execução. Compilação Python e `git diff --check` passaram.

Os relatórios versionados preservam entradas, consultas, candidatas, origens, testemunhos por rota, molduras completas, diagnósticos e registros das intervenções. Proveniência completa e união repetida de testemunhos por candidata têm hashes e são regeneráveis sem `--summary`. O detalhamento de qualidade por estado é exclusivamente do avaliador e nunca volta para a aprendizagem.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_route_relation_probe.py \
 tests/test_trajectory_composed_frame_probe.py tests/test_trajectory_symbol_transform_probe.py \
 tests/test_trajectory_question_variant_probe.py tests/test_trajectory_question_frame_probe.py \
 tests/test_trajectory_analogy_frame_probe.py tests/test_trajectory_analogy_anchor_probe.py \
 tests/test_trajectory_native_bridge_probe.py tests/test_trajectory_native_evidence_join_probe.py

PYTHONPATH=src python scripts/trajectory_route_relation_probe.py \
 --library build/trajectory-native/libmemoria_mobile.so --seed 20261229 --summary
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. Relatórios: `benchmark-results/trajectory-route-relation-{development,reserved}.json`. A CI de `6c6901f` passou nos oito workflows aplicáveis, incluindo trajetória no run `38086413178`. A CI de `b41492c` também passou, com trajetória no run `38083673221`; `1c0b0a3` passou com trajetória no run `38082813810`. O workflow condicional foi ignorado. A CI executou os testes e ambos os seeds deste diagnóstico.

O diagnóstico permanece uma rota opt-in de pesquisa; não altera o núcleo estável, ABI, seletor padrão ou MVP. O próximo problema é representar retorno observado de acerto/erro com alvo e proveniência próprios, testar contrafactuais e fontes concorrentes e só então investigar uma mudança de suporte de rota. Repetição, concordância e divergência sozinhas não forneceram esse sinal.
