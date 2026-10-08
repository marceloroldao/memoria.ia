# Demonstrações observadas de pergunta e conteúdo

Continuação de `a859b7c`, cujos oito workflows aplicáveis passaram, incluindo trajetória `37730431571`. Reutilizamos o leitor de analogias por molduras existente, sem alterar seu aprendizado ou o motor. O novo adaptador diagnóstico restringe as cinco entradas brutas à região pedida, aprende a partir de ocorrências sequenciais e consulta raízes completas já observadas. Não instala um seletor na tela/MVP nem gera linguagem; o PR #374 permanece em rascunho.

## Informação observada

As demonstrações têm frases como `Qual é a cor do barco?` seguidas de `A cor do barco é azul.`. Três objetos diferentes demonstram cor, nome e tensão, com valores diferentes. Uma barreira gerada separa cada par. Os conteúdos do objeto novo `drone` aparecem isolados, separados por barreiras, sem sua pergunta. Nenhuma consulta de avaliação é gravada na memória.

O algoritmo recebe símbolos Unicode brutos e os campos de origem/ordem já usados anteriormente. Prefixos, sufixos, trechos copiados e partes fixas vêm dos exemplos; não há lista de atributos, classificador de pergunta ou vocabulário português no leitor. Três variáveis distintas sustentam uma moldura; repetir um mesmo par não substitui demonstrações distintas. A região é explicitamente escolhida pelo chamador, sem inferir sua intenção.

Cada candidato é uma raiz observada completa, com todas as origens locais aceitas, IDs das molduras e testemunhos dos pares. O relatório completo inclui a tabela de texto/origens das raízes usadas nas demonstrações. Uma raiz única permite apenas `proposal_payload_id`; continuam `answer:null`, `qualified:false`, `selected_target:null`, `selection_used:false`, `query_observed:false` e qualidade factual `NOT_EVALUATED`.

O armazenamento nativo separa gerados em `<região>:generated`. A coleta recompõe a ordem local usando sequência e projeta apenas os cinco campos brutos; metadados de vizinhança/vínculo nativo não entram no aprendizado. No adaptador, conteúdo gerado serve somente como barreira e não fornece raízes ou origens de evidência. As origens aceitas de usuários continuam endereços nativos reais. Reabertura fria verifica a projeção bruta e a visão completa do leitor.

## Bateria e resultados

Onze cenários contêm nove consultas cada: cor, nome, tensão, idade, corrente ausente, objeto ausente, paráfrase, maiúsculas e prefixo adicional. Os cenários variam quantidade de demonstrações, repetição, origem gerada, região estrangeira, conteúdo novo somente gerado, conflito com cópias, demonstrações trocadas, relevância escondida e um atributo observado sem exemplos específicos.

Cada cenário é executado em texto português e em renomeação injetiva de caracteres. Seeds 20261221/20261222 dão **211/211 controles de integridade cada**, com os mesmos resultados estruturais. São renomeações correlacionadas das mesmas formas, sem estatística de compreensão geral.

| Cenário, texto português | Conjuntos exatos de moldura / 9 | Evidência principal |
| --- | ---: | --- |
| Três exemplos distintos | 7 | Cor, nome e tensão do objeto novo recuperados separadamente; idade/corrente/objeto ausentes sem candidatos. |
| Sem exemplos | 3 | Abstenção em positivos; perda de cobertura conservada. |
| Dois exemplos por relação | 3 | Quatro molduras existem, mas não cobrem as consultas novas deste desenho. |
| Três cópias de um par | 3 | Não substituem três variáveis distintas. |
| Um exemplo de cor gerado | 7 | A rota de cor ainda tem apoio em molduras mais amplas de outros pares aceitos. |
| Demonstrações em outra região | 3 | Não fornecem molduras locais. |
| Conteúdo de cor somente gerado | 9 | Nunca vira candidato; nome e tensão continuam recuperáveis. |
| Conflito com cópias | 7 | Dois conteúdos de cor, 20 origens para verde e uma para branca; nenhuma escolha por maioria. |
| Exemplos cor/nome trocados | 4 | Aprende a associação trocada; propostas incompatíveis com a referência semântica são mantidas como falhas. |
| Gêmeo com relevância escondida | 5 | Mesmas observações e saída do positivo, referências diferentes apenas no avaliador. |
| Idade observada sem demonstração própria | 7 | Molduras mais amplas transportam `idade do drone` literalmente para a raiz observada. |

No texto português, a moldura tem **58/99 conjuntos exatos**, 22 conteúdos de referência recuperados, sete extras e 39 perdidos. O recall nativo original, nas mesmas observações adicionais e no limite existente de 16 contextos, recupera 60 referências, admite 1098 extras, perde uma e não tem conjunto exato. A moldura reduz excesso neste desenho, mas perde 38 conteúdos que o recall nativo recupera. Não é melhora geral de cobertura, nem substitui a bateria anterior de 37 perguntas.

Na renomeação, a moldura mantém **58/99**, 22 corretos, sete extras e 39 perdidos. O comparador nativo fica sem candidatos, com 42/99 abstenções de referência e 61 perdas: substituir inclusive espaços por letras modifica a tokenização de palavras do runtime. Portanto a renomeação verifica invariância do leitor de símbolos, **não** equivalência de desempenho semântico do comparador nativo. Somando as versões correlacionadas, a moldura fica em **116/198**, 44 recuperados, 14 extras e 78 perdidos por seed.

## Limites mantidos

A paráfrase `Que cor tem o drone?` e a versão em maiúsculas ficam sem rota mesmo no cenário completo. Um prefixo adicional antes da pergunta literal é admitido pelo leitor já existente. São perdas reais de cobertura no contrato deste teste, não consultas redefinidas como negativas depois do resultado.

Quando um exemplo específico é gerado, sua origem não entra em nenhum testemunho. A consulta de cor ainda pode usar molduras aprendidas de dois exemplos de cor e de outros exemplos com a mesma composição literal. Isso não permite afirmar que a barreira apaga todas as rotas possíveis. Analogamente, a idade observada é recuperada por uma composição mais ampla apesar de não haver pares próprios de idade. Não há descoberta de idade inexistente: sem a raiz observada, a mesma consulta permanece vazia.

As demonstrações trocadas ensinam cor → nome e nome → cor. O leitor segue essas relações observadas, mas o avaliador exige os conteúdos de cor/nome conforme a pergunta; os falsos candidatos ficam visíveis. Observação sequencial não certifica confiabilidade do exemplo nem verdade factual.

O gêmeo de relevância escondida tem os mesmos dados e as mesmas nove saídas do positivo. A consulta literal de cor é correta em um contrato e extra no outro: **1/2 nesse par de referências**. É um limite informacional construído pelo avaliador, não uma situação que o algoritmo possa distinguir por símbolos iguais. Conservam-se `FAIL_EXTRA_OR_MISSING_CONTENT`, `FAIL_INDISTINGUISHABLE_INPUTS` e factual `NOT_EVALUATED`.

Na preparação, uma renomeação para caracteres U+0100+ foi rejeitada pelo tokenizador nativo atual. Mantivemos o runtime e passamos a usar um alfabeto injetivo ASCII/Latin-1 admitido. Também corrigimos a comparação de entrada para considerar os cinco campos brutos, pois janelas nativas acrescentam `prev_source_id`, `next_source_id` e `reply_to`. Os metadados seguem mascarados; essas duas falhas de preparação não foram contadas como resultados semânticos.

## Verificação e reprodução

Oito testes novos e regressões dos leitores de moldura/âncora e adaptadores nativos: **30 passed**. Cobrem discriminação literal, consultas novas sem gravação, perda por poucos exemplos/cópias, fontes e testemunhos aceitos, conflito sem voto, metadados mascarados, exemplos trocados, gêmeos indistinguíveis, perdas de paráfrase/maiúsculas, reabertura fria e símbolos renomeados.

Os resumos preservam todas as entradas, consultas, candidatos, origens, scores dos dois leitores e falhas. Molduras completas, tabela de proveniência e testemunhos longos têm hashes; sem `--summary`, a CLI emite todo o conteúdo. `full_report_sha256` usa a serialização canônica do relatório, sem timestamps. Ambos os resumos e hashes completos reproduziram byte a byte em nova execução. Compilação Python e `git diff --check` passaram. A CI inclui ambos os seeds e os testes novos. O novo commit ainda precisa executar seus checks.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
PYTHONPATH=src python -m pytest -q \
  tests/test_trajectory_question_frame_probe.py tests/test_trajectory_analogy_frame_probe.py \
  tests/test_trajectory_analogy_anchor_probe.py tests/test_trajectory_native_bridge_probe.py \
  tests/test_trajectory_native_evidence_join_probe.py

PYTHONPATH=src python scripts/trajectory_question_frame_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so --seed 20261221 --summary
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. Resumos: `benchmark-results/trajectory-question-frame-{development,reserved}.json`. A próxima investigação é aprender variantes observadas de pergunta, medir se recuperam paráfrases/maiúsculas sem admitir atributos ausentes, e preservar origens e relações concorrentes. Nenhuma destas medições qualifica respostas ou resolve os contraexemplos históricos.
