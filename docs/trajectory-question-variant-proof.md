# Variantes observadas de perguntas: prova experimental

A rota experimental aprende as formas observadas `Que cor tem o …?` e `QUAL É A COR DO …?` com o mesmo leitor de molduras, sem classificador de perguntas, dicionário de sinônimos ou normalização de caixa. As consultas usam um objeto novo, nunca registrado como pergunta. As respostas candidatas continuam sendo textos completos já observados, com todas as origens. Não são respostas factualmente qualificadas.

## Resultado e limite

| Cenário | Conjuntos exatos / 13 consultas |
|---|---:|
| Sem demonstrações das novas variantes | 9 |
| Três demonstrações distintas por variante | 11 |
| Duas demonstrações por variante | 9 |
| Demonstrações geradas | 9 |
| Demonstrações em outra região | 9 |
| Variantes com conteúdos concorrentes | 11 |
| Perguntas e conteúdos também observados em maiúsculas | 12 |
| Paráfrase ensinada com relação cruzada | 10 |
| Mesma entrada, referência oculta de irrelevância | 7 |

`Que cor tem o drone?` e `QUAL É A COR DO drone?` passam após demonstrações distintas locais. `QUAL É A COR DO DRONE?` não encontra o conteúdo em minúsculas, mesmo com exemplos que alternam caixa entre pergunta e conteúdo: o leitor exige cópia literal da variável. A consulta passa quando há demonstrações e um conteúdo separado `A COR DO DRONE É VERDE.`. Essa prova mede correspondência literal; não demonstra equivalência semântica entre caixa alta e baixa. A referência dessa consulta no cenário correspondente aponta apenas ao texto em maiúsculas.

`Que cor possui o drone?` continua sem resultado. Os controles de idade, corrente, entidade ausente e variantes de ausência não produzem conteúdo na região positiva. No conflito, ambas as cores permanecem, com 20 origens para verde e uma para branca, sem votação nem escolha. Demonstrações cruzadas recuperam o nome em vez da cor. A entrada do gêmeo de irrelevância é idêntica à entrada positiva e produz a mesma leitura: intenção oculta continua impossível de distinguir.

Em ambos os seeds, passaram **83/83 verificações de integridade**. A rota de molduras obteve **87/117 conjuntos exatos**, com **44 conteúdos esperados recuperados, sete extras e 26 perdas**. A rota nativa obteve zero conjuntos exatos: em ambos os seeds, 69 recuperações esperadas, 1.510 extras e uma perda. Não usamos esses scores para instalar um limiar.

## Medição reproduzível

Nove cenários, 13 consultas cada: 117 consultas por seed. O seed de desenvolvimento é `20261223`; o reservado `20261224` muda nomes de objetos e valores por substituição no fixture, preservando as relações de superfície. Isso é uma variação lexical correlacionada, não uma amostra independente de linguagem natural. Não repetimos aqui o controle opaco de símbolos, preservado na prova anterior.

Cada cenário grava observações no BDR nativo, lê a janela com apenas cinco campos brutos, compara o estado antes/depois da consulta, mascara metadados extras e reabre o armazenamento. O conteúdo gerado fica em campo nativo separado e fornece somente barreiras de sequência. As referências entram apenas na avaliação. A integridade tem 83 verificações por seed, incluindo paridade completa das leituras após reabertura e identidade das entradas/leituras do gêmeo oculto.

O relatório também mede a rota nativa de associação sem mudar seu `top_k=16`. As demonstrações acrescentam perguntas e conteúdos ao universo recuperável; as métricas nativas não são comparáveis diretamente à bateria anterior de 37 consultas. A qualidade continua `FAIL_EXTRA_OR_MISSING_CONTENT`; a relevância oculta continua `FAIL_INDISTINGUISHABLE_INPUTS`; a qualidade factual continua `NOT_EVALUATED`.

Os resumos versionados retêm entradas, consultas, candidatos, origens e falhas. Molduras, proveniência completa e testemunhos longos ficam resumidos por contagens e hashes; a CLI sem `--summary` emite o relatório completo. Não alteramos o núcleo estável, ABI, seletor padrão nem a interface do MVP. O único ajuste na prova anterior permite injetar um fixture, com o fixture original como padrão.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_question_variant_probe.py tests/test_trajectory_question_frame_probe.py \
 tests/test_trajectory_analogy_frame_probe.py tests/test_trajectory_analogy_anchor_probe.py \
 tests/test_trajectory_native_bridge_probe.py tests/test_trajectory_native_evidence_join_probe.py

PYTHONPATH=src python scripts/trajectory_question_variant_probe.py \
 --library build/trajectory-native/libmemoria_mobile.so --seed 20261223 --summary
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. A CI anterior (`dc3ea89`) passou nos oito workflows aplicáveis. O novo workflow inclui os testes e ambos os seeds; a CI de `53c481b` passou nos oito workflows aplicáveis (prova de trajetória: run `37973289818`); o workflow condicional foi ignorado.

O próximo limite útil é aprender relações observadas que transformem a variável, em vez de apenas copiá-la, mantendo controles de transformação errada, conteúdo ausente e origem observada. Este incremento não implementa essa transformação.

Validação local: 35 testes da bateria de regressão passaram, mais um teste da variação lexical reservada (36 testes no total). Compilação Python e `git diff --check` passaram.
