# Transformações de símbolos aprendidas por observação

A rota experimental agora consegue recuperar `A cor do drone é verde.` para a consulta inédita `QUAL É A COR DO DRONE?`, usando correspondências entre símbolos demonstradas em três pares distintos. O leitor anterior, que exige cópia literal da variável, não recupera esse conteúdo nas mesmas entradas. Não há conversão automática para minúsculas, regra Unicode de caixa ou classificador de idioma no novo leitor.

## O que foi aprendido

No desenvolvimento, as três demonstrações são perguntas sobre `DARDO`, `NERVO` e `ODRE`, seguidas pelos conteúdos sobre `dardo`, `nervo` e `odre`, com três valores de cor distintos. A variável `DRONE` não aparece nas perguntas registradas: é uma nova combinação dos símbolos cuja transformação já foi demonstrada. A cor de drone, por sua vez, precisa estar registrada; o leitor não cria esse conteúdo.

O learner opera sobre sequências de inteiros. Extrai prefixos e sufixos comuns das perguntas e examina possíveis alinhamentos nos conteúdos. Aceita uma moldura quando três variáveis distintas sustentam uma substituição consistente, injetiva e de mesmo comprimento, com valores finais distintos. O mapa contém somente símbolos testemunhados. Uma consulta com símbolo ainda não demonstrado não autoriza extrapolação. Essas restrições e o limiar de três demonstrações são escolhas do experimento, não conclusões sobre aprendizagem humana.

Não usamos referências do avaliador, nomes de atributos ou metadados de resposta para descobrir a transformação. Os exemplos pertencem à região explicitamente solicitada. A sequência adjacente fornece uma relação observada, sem garantir que ela seja uma explicação correta ou um fato.

## Ganhos e falhas

Cada cenário tem nove consultas: objeto coberto, prefixo novo, objeto observado com símbolos ainda não demonstrados, entidade ausente, relação ainda não ensinada, atributo ausente, pergunta em minúsculas ainda não ensinada, paráfrase ainda não ensinada e dois cues concorrentes.

| Cenário | Molduras no desenvolvimento | Conjuntos exatos / 9 |
|---|---:|---:|
| Sem exemplos | 0 | 3 |
| Três exemplos e mapa observado | 1 | 5 |
| Dois exemplos | 0 | 3 |
| Mesmo exemplo repetido | 0 | 3 |
| Exemplos gerados | 0 | 3 |
| Exemplos em outra região | 0 | 3 |
| Conteúdos de cor concorrentes | 1 | 5 |
| Transformação ensinada errada | 1 | 3 |
| Duas transformações observadas | 4 | 5 |
| Entrada idêntica com relevância oculta diferente | 1 | 7 |

As consultas coberta e com prefixo novo recuperam o conteúdo esperado. Os controles de entidade/atributo ausente e dois cues não recuperam conteúdo. A pergunta sobre `GATO` fica sem resultado, embora exista um conteúdo sobre gato, pois faltam correspondências para seus símbolos. Nome, paráfrase e pergunta em minúsculas continuam descobertos. Nenhuma dessas perdas foi omitida da avaliação.

No conflito de cores, ambas as raízes permanecem, com 20 origens para verde e uma para branca. Repetições não viram votos. Na transformação errada, o mapa aprende `D→b` e `N→l` e recupera o texto observado sobre `brole`, em vez de drone: duas falsas recuperações por execução legível. Nos mapas concorrentes, molduras completas e parciais compatíveis com grupos de testemunhos diferentes coexistem; quatro molduras no desenvolvimento e duas no reservado produzem duas raízes candidatas, sem escolher uma. A referência desse cenário admite explicitamente ambas as rotas estruturais, sem qualificá-las factualmente.

O gêmeo de relevância oculta tem as mesmas entradas e leituras que o caso positivo, mas o avaliador considera todos os resultados irrelevantes. O leitor não consegue distinguir essas referências invisíveis. Uma candidata única continua sem resposta qualificada: `answer=null`, `qualified=false`, `selected_target=null`, `selection_used=false`.

## Bateria e comparação

São dez cenários em texto legível e em renomeação injetiva de caracteres: **180 consultas e 194 verificações de integridade por seed**. Desenvolvimento `20261225`; reservado `20261226` muda objetos de demonstração, valores e objeto de consulta (`morena`). Essa variação preserva templates e relações, portanto não é uma amostra independente de linguagem natural.

Em ambos os seeds, a rota de transformação teve **80/180 conjuntos exatos, 20 recuperações esperadas, oito extras e 104 perdas**. A integridade passou **194/194**. O controle opaco preservou todos os scores da transformação. Um teste adicional renomeia diretamente os inteiros e verifica a conjugação do mapa, sem depender de caracteres de texto.

A rota nativa usa as mesmas observações e `top_k=16`, sem alteração. Em cada bateria legível de 90 consultas, teve zero conjuntos exatos, 61 recuperações esperadas, 536 extras e uma perda. Na renomeação, o desenvolvimento teve 29 conjuntos exatos, zero recuperações esperadas, 13 extras e 62 perdas; o reservado teve 36 conjuntos exatos, zero recuperações esperadas, zero extras e 62 perdas. Esses conjuntos exatos na renomeação são correspondências com referências vazias, não recuperação de respostas. A renomeação muda a tokenização nativa; ela não comprova invariância desse leitor. As contagens não são comparáveis diretamente às baterias anteriores, que usavam outros universos de entradas e consultas.

Qualidade geral: `FAIL_EXTRA_OR_MISSING_CONTENT`. Relevância oculta: `FAIL_INDISTINGUISHABLE_INPUTS`. Qualidade factual: `NOT_EVALUATED`. A transformação ensina correspondências finitas; não resolve intenção oculta, relações erradas ou fatos ausentes. Substituições de comprimento diferente, símbolos inéditos e equivalência semântica permanecem fora deste incremento.

## Persistência e reprodução

As observações são gravadas no BDR nativo; conteúdo gerado fica no campo separado e fornece somente barreiras de sequência. O adapter projeta os cinco campos brutos. Consultas nunca são registradas automaticamente. Os testes verificam paridade de entradas, leituras completas após reabertura, estado inalterado, mascaramento de metadados e todas as origens locais aceitas. Correspondências inconsistentes dentro dos testemunhos são rejeitadas.

**44 testes de regressão passaram**. Após acrescentar ao resumo as molduras completas de transformação, os oito testes da nova rota passaram novamente; a cópia isolada do resumo também foi verificada. Os dois relatórios completos reproduziram os mesmos hashes e scores. Compilação Python e `git diff --check` passaram.

Os relatórios versionados mantêm entradas, consultas, candidatos, origens, falhas e todas as molduras de transformação, incluindo mapas e testemunhos. A tabela completa de proveniência e testemunhos repetidos por candidata têm hashes e são regeneráveis sem `--summary`.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_symbol_transform_probe.py \
 tests/test_trajectory_question_variant_probe.py tests/test_trajectory_question_frame_probe.py \
 tests/test_trajectory_analogy_frame_probe.py tests/test_trajectory_analogy_anchor_probe.py \
 tests/test_trajectory_native_bridge_probe.py tests/test_trajectory_native_evidence_join_probe.py

PYTHONPATH=src python scripts/trajectory_symbol_transform_probe.py \
 --library build/trajectory-native/libmemoria_mobile.so --seed 20261225 --summary
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. Relatórios: `benchmark-results/trajectory-symbol-transform-{development,reserved}.json`. A CI anterior (`53c481b`) passou nos oito workflows aplicáveis; a prova de trajetória passou no run `37973289818`. A CI de `1c0b0a3` passou nos oito workflows aplicáveis; a prova de trajetória passou no run `38082813810`, e o workflow condicional foi ignorado.

Não alteramos o núcleo estável, ABI, seletor padrão ou MVP. A prova anterior ganhou parâmetros opcionais para injetar leitor e fixture; os padrões preservam o comportamento anterior. A exploração de grupos de três pares tem custo combinatorial e não foi validada para escala de produção. O próximo passo útil é medir a composição entre rotas de cópia e transformação, mantendo ambas as proveniências e expondo novos conflitos em vez de instalar uma prioridade automática.
