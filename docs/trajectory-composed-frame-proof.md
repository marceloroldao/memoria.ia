# Composição de cópia literal e transformação observada

A composição experimental reúne as candidatas dos dois leitores existentes, preservando a origem de cada rota. Nas mesmas entradas do cenário positivo, a cópia literal e a transformação isoladas têm **6/11 consultas exatas cada**; a união chega a **8/11**. Ela cobre perguntas ensinadas em minúsculas, a paráfrase observada e perguntas em maiúsculas cujos símbolos têm transformação demonstrada. Não instala prioridade, votação ou confiança baseada no número de rotas.

## Composição e proveniência

Cada leitor aprende suas próprias molduras a partir das observações brutas. As duas funções de aprendizado e recuperação anteriores não foram alteradas. A união usa o endereço da raiz observada, sem repetir o conteúdo quando ambas as rotas o encontram. IDs de moldura recebem namespace da rota e preservam o ID original. Cada candidata transporta os IDs e testemunhos separados por rota, além da união de testemunhos e de todas as ocorrências nativas do conteúdo.

No cenário de sobreposição, as demonstrações de transformação mudam `v→w`, enquanto a nova variável `drone` usa somente símbolos cujo mapa é identidade. A cópia literal e a transformação encontram a mesma raiz de drone: uma candidata, uma ocorrência do conteúdo isolado, duas rotas com testemunhos próprios. O reservado usa `morena` e demonstrações diferentes. As rotas compartilham parte das observações, portanto a concordância não constitui evidência independente nem aumenta uma confiança factual.

Se as rotas encontram raízes diferentes, todas permanecem. A recuperação continua `answer=null`, `qualified=false`, `selected_target=null`, `selection_used=false`; uma raiz única pode ter proposta não qualificada. Consultas não são registradas automaticamente.

## Resultado por cenário

Cada cenário tem 11 consultas. Os números são conjuntos exatos, incluindo controles com referência vazia. As três rotas abaixo usam exatamente as mesmas observações e referências.

| Cenário | Cópia literal | Transformação | Composição |
|---|---:|---:|---:|
| Sem exemplos | 4/11 | 4/11 | 4/11 |
| Apenas exemplos de cópia | 6/11 | 4/11 | 6/11 |
| Apenas exemplos de transformação | 4/11 | 6/11 | 6/11 |
| Exemplos para ambas | 6/11 | 6/11 | 8/11 |
| Mesma raiz por duas rotas | 6/11 | 7/11 | 8/11 |
| Transformação errada e cópia correta | 6/11 | 4/11 | 6/11 |
| Rotas que divergem no mesmo cue | 6/11 | 4/11 | 5/11 |
| Cores concorrentes repetidas | 6/11 | 6/11 | 8/11 |
| Exemplos de cópia gerados | 4/11 | 6/11 | 6/11 |
| Exemplos de cópia em outra região | 4/11 | 6/11 | 6/11 |
| Mesmas entradas com relevância oculta diferente | 9/11 | 9/11 | 7/11 |

Há ganho de cobertura, mas também perda de precisão. Na consulta `Qual é a cor do drone?` do cenário de divergência, a cópia recupera corretamente o conteúdo observado sobre drone. A transformação aprendida errada acrescenta o conteúdo observado sobre `brole`; a união passa a ter uma falsa candidata. Nenhuma rota é descartada ou promovida automaticamente. Na pergunta em maiúsculas desse cenário, a transformação errada continua sendo a única rota compatível e sua associação errada permanece explícita.

No conflito de cores, ambas as raízes permanecem nas três formas cobertas de pergunta, com 20 origens para verde e uma para branca. Repetições não decidem o resultado. Os controles de entidade/atributo ausente e dois cues ficam vazios no cenário positivo. Símbolos ainda não demonstrados (`GATO`), nome ainda não ensinado e `Que cor possui…` continuam sem resultado mesmo quando o conteúdo esperado está registrado. Conteúdo gerado e exemplos de outra região não fornecem as novas rotas locais.

O gêmeo de irrelevância tem exatamente as mesmas observações e leituras que o cenário composto positivo. Somente a referência do avaliador muda; o aprendizado não recebe essa referência. A união amplia os resultados e, nesse gêmeo, amplia também os falsos resultados. Intenção oculta permanece indistinguível.

## Totais e controles

Desenvolvimento `20261227`; reservado `20261228` troca objetos de demonstração, valores e objeto de consulta. Cada seed tem 11 cenários em texto legível e renomeado: **242 consultas**. Essa variação é correlacionada por templates e relações, não uma amostra independente de linguagem natural.

Em ambos os seeds:

| Rota | Conjuntos exatos / 242 | Recuperações esperadas | Extras | Perdas |
|---|---:|---:|---:|---:|
| Cópia literal | 122 | 28 | 4 | 122 |
| Transformação | 124 | 30 | 14 | 120 |
| Composição | 140 | 56 | 18 | 94 |

Recuperações são contadas por consulta, não como fatos distintos. Duas recuperações esperadas compartilhadas pelas rotas são deduplicadas na composição. A união pode ampliar cobertura e preservar erros ao mesmo tempo. Qualidade: `FAIL_EXTRA_OR_MISSING_CONTENT`; relevância oculta: `FAIL_INDISTINGUISHABLE_INPUTS`; qualidade factual: `NOT_EVALUATED`.

As **279/279 verificações de integridade por seed** passaram. Além das nove verificações de cada cenário nativo, a bateria verifica igualdade com a união das rotas, raízes emitidas uma vez, cobertura de testemunhos por rota, paridade de scores sob renomeação e identidade dos gêmeos. As leituras completas preservam o estado e reproduzem após reabrir o armazenamento. Metadados extras permanecem mascarados e cada origem pertence a uma entrada local aceita.

Na rota nativa inalterada (`top_k=16`), cada bateria legível de 121 consultas tem zero conjuntos exatos, 75 recuperações esperadas, 1.102 extras e zero perdas. A bateria renomeada de desenvolvimento tem 49 conjuntos exatos com referência vazia, zero recuperações esperadas, 12 extras e 75 perdas; a reservada tem 51 conjuntos exatos com referência vazia, zero recuperações esperadas, zero extras e 75 perdas. A renomeação muda a tokenização nativa; o controle de invariância se aplica aos leitores de molduras. O universo de entradas mudou, portanto essas contagens não substituem nem se comparam diretamente às anteriores.

## Reprodução e estado do incremento

**51 testes de regressão passaram**, incluindo os dois leitores anteriores, os adapters nativos, exclusões, sobreposição, divergência e reabertura. Ambos os resumos e hashes completos reproduziram byte a byte em nova execução. Compilação Python e `git diff --check` passaram. Os relatórios versionados retêm observações, consultas, candidatas, origens, testemunhos por rota, scores isolados e compostos e molduras completas. A tabela completa de proveniência e a união repetida de testemunhos por candidata têm hashes e são regeneráveis sem `--summary`.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_composed_frame_probe.py \
 tests/test_trajectory_symbol_transform_probe.py tests/test_trajectory_question_variant_probe.py \
 tests/test_trajectory_question_frame_probe.py tests/test_trajectory_analogy_frame_probe.py \
 tests/test_trajectory_analogy_anchor_probe.py tests/test_trajectory_native_bridge_probe.py \
 tests/test_trajectory_native_evidence_join_probe.py

PYTHONPATH=src python scripts/trajectory_composed_frame_probe.py \
 --library build/trajectory-native/libmemoria_mobile.so --seed 20261227 --summary
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. Relatórios: `benchmark-results/trajectory-composed-frame-{development,reserved}.json`. A CI inclui os testes e ambos os seeds. A CI de `b41492c` passou nos oito workflows aplicáveis; a prova de trajetória passou no run `38083673221`. O predecessor `1c0b0a3` também passou nos oito workflows aplicáveis, incluindo a prova de trajetória no run `38082813810`; o workflow condicional foi ignorado.

A composição permanece uma rota opt-in de pesquisa, com custo combinatorial de aprendizado herdado dos leitores. Não foi integrada ao seletor padrão nem à interface do MVP. O próximo problema é expor ou aprender sinais de contradição entre rotas a partir de intervenções observadas, sem confundir discordância com falsidade nem decidir pela quantidade de rotas ou ocorrências.
