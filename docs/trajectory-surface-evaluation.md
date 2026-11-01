# Diagnóstico de escrita e demonstração de novas molduras

Este experimento investiga as falhas de caixa e paráfrase da [avaliação de transferência](trajectory-transfer-evaluation.md). O leitor e o motor permanecem sem alterações. Não foi acrescentada normalização de caixa, lista de sinônimos ou regra de domínio à inferência.

**Três demonstrações adequadas da nova escrita: 16/16 recuperações exatas. As oito condições de controle: 0/16 cada. A outra escrita ainda não demonstrada: 0/8 em todas as condições.** O gate completo permanece reprovado.

## Hipótese e método

O leitor compara o prefixo e os limites da consulta com molduras aprendidas de pares observados. O mapa de símbolos pertence a cada moldura: saber um mapa em uma escrita não implica reutilizá-lo automaticamente em outra. O experimento separa ausência de moldura, falta de símbolo no mapa da moldura e mapa sem destino observado compatível.

O requisito de três testemunhos distintos já pertence ao algoritmo experimental. Esta rodada verifica seu efeito neste corpus; não descobre um limiar universal de aprendizagem.

São usadas as mesmas duas sementes e os mesmos domínios sintéticos da rodada anterior. Esta é uma intervenção após diagnóstico, não um teste independente ou cego. As consultas originais já admitem o conteúdo após o exemplo adicional daquela rodada. Os fatos-alvo permanecem observados, mas nenhuma pergunta de avaliação ou fato-alvo é incluído nos novos pares de demonstração.

Cada contexto é testado separadamente em caixa alta e em uma paráfrase fixa. A função que constrói esses exemplos existe somente no avaliador: o leitor recebe os textos literais. Para cada escrita, são executadas nove condições em memórias novas:

| Condição | Demonstrações adicionais |
|---|---|
| Baseline | Nenhuma |
| Repetir original | Três pares na escrita original |
| Uma nova | Um par na nova escrita |
| Duas novas | Dois pares na nova escrita |
| Três novas | Três pares na nova escrita, cobrindo todos os símbolos necessários |
| Somente símbolos antigos | Três pares na nova escrita, sem o quarto símbolo da consulta-alvo |
| Mapa incorreto | Três pares na nova escrita, com mapa incorreto para o quarto símbolo |
| Geradas | Três pares adequados, declarados como conteúdo gerado |
| Outro escopo | Três pares adequados, registrados efetivamente em outro escopo |

Os pares adicionais usam entidades e valores que já serviam de demonstração, nunca as entidades-alvo. Barreiras geradas continuam separando os pares. A ordem das condições é fixa, sem escolha baseada em score ou diagnóstico. Os gabaritos ficam fora dos comandos da sessão.

Cada memória recebe dez consultas: duas originais, duas na escrita investigada, uma na outra escrita ainda não demonstrada e cinco controles de ausência. Os controles também usam a escrita investigada, cobrindo atributo e entidade ausentes, símbolo sem mapa, conteúdo somente gerado e conteúdo de outro escopo.

## Resultados

Foram **720 consultas em 72 memórias novas**, duas sementes, dois domínios, duas escritas e nove condições. Cada contagem da coluna de escrita investigada contém oito casos de caixa alta e oito de paráfrase.

| Condição | Escrita investigada | Escrita original | Outra escrita ainda não ensinada | Ausência |
|---|---:|---:|---:|---:|
| Baseline | 0/16 | 16/16 | 0/8 | 40/40 |
| Repetir original | 0/16 | 16/16 | 0/8 | 40/40 |
| Uma nova | 0/16 | 16/16 | 0/8 | 40/40 |
| Duas novas | 0/16 | 16/16 | 0/8 | 40/40 |
| Três novas | **16/16** | 16/16 | **0/8** | 40/40 |
| Somente símbolos antigos | 0/16 | 16/16 | 0/8 | 40/40 |
| Mapa incorreto | 0/16 | 16/16 | 0/8 | 40/40 |
| Geradas | 0/16 | 16/16 | 0/8 | 40/40 |
| Outro escopo | 0/16 | 16/16 | 0/8 | 40/40 |

Nos oito contextos com três demonstrações adequadas, 72/80 consultas passam no total; as oito consultas na outra escrita continuam falhando. `retrieval_status=EXTRA_OR_MISSING_CONTENT` conserva essa falha, sem promover integridade a aprovação de recuperação. `selected_answer_count=0` em toda a avaliação.

Os **576 controles de integridade** passaram: estado preservado nas leituras, escopo estrangeiro preservado, repetição de leituras completas, candidatas de observações admitidas, nenhuma qualificação factual, igualdade após reabertura e concordância do diagnóstico com a rota de transformação.

## Leitura dos diagnósticos

Nas 16 consultas da escrita investigada de cada condição, `NO_COMPATIBLE_SOURCE_FRAME` aparece em baseline, repetição da original, uma e duas demonstrações, conteúdo gerado e outro escopo. `UNWITNESSED_SYMBOLS_IN_FRAMES` aparece nos 16 casos de símbolos antigos: a moldura existe, mas seu mapa não testemunhou o símbolo necessário. `NO_OBSERVED_DESTINATION_IN_FRAMES` aparece nos 16 mapas incorretos. Com três demonstrações adequadas, os 16 casos admitem o conteúdo observado e exibem `OBSERVED_CANDIDATE_REQUIRES_REVIEW`. Adequação factual continua não avaliada.

O diagnóstico não conhece o mapa considerado correto pelo avaliador. Sua concordância com as rotas reais é verificada, e a leitura continua sem registrar novas observações. Não se trata de uma prova geral de causalidade ou de uma recomendação automática de exemplos.

## Reprodução e limites

```sh
PYTHONPATH=src python scripts/trajectory_surface_evaluation.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output /tmp/surface-evaluation.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m pytest -q tests/test_trajectory_surface_evaluation.py
```

Passaram **37 testes**, onze novos do experimento e 26 regressões de transferência, diagnóstico e sessão. A avaliação anterior reproduziu byte a byte seu relatório, incluindo as falhas de caixa/paráfrase. O relatório novo conserva observações locais e estrangeiras, origens, consultas, referências do avaliador, candidatas, pontuação, achados e contagens de status dos diagnósticos. Os hashes das leituras completas permitem conferir a reprodução sem omitir a distinção entre integridade e recuperação.

Relatórios: `benchmark-results/trajectory-surface-evaluation.json` e `benchmark-results/trajectory-surface-evaluation-validation.json`. O resumo final foi derivado das leituras reais coletadas nesta execução, sem repetir os 720 casos após acrescentar o indicador de recuperação; a igualdade das leituras, scores e controles foi conferida. Compilação Python e `git diff --check` passaram. A CI do novo incremento permanece pendente após publicação.

O modo padrão retorna zero quando a integridade passa e mantém a recuperação reprovada no relatório. Adicionar `--strict-retrieval` ao primeiro comando retorna 1 quando o gate completo falha. Essa separação também tem testes próprios.

A execução combina armazenamento nativo em BDR com o leitor experimental em Python. Nenhuma resposta factual é selecionada. Os mapas sorteados são reutilizados nos dois domínios e as molduras são correlacionadas; as contagens não estimam precisão geral. Demonstrar explicitamente outra escrita não prova compreensão automática de paráfrases inéditas, aprendizagem geral, uso humano, escala ou integração ao produto.
