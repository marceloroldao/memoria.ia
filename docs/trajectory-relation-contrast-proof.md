# Pista copiada de relação e variação cruzada de valor

Experimento somente leitura com o pacote de evidência anterior, sem modificar qualquer leitor, motor, pesos ou runtime nativo. O usuário autorizou continuar a investigação após a separação entre candidato recuperado e continuação observada.

## Informação nova

As primeiras três demonstrações têm uma origem com apenas uma pista variável e destinos contendo duas pistas e um valor. Duas raízes isoladas do mesmo primeiro identificador têm segundos identificadores diferentes. Repetir as demonstrações preserva as mesmas raízes, mas não ensina a origem enriquecida consultada.

Três novas origens passam a conter ambos os identificadores, separados por um trecho comum, e são seguidas dos mesmos destinos existentes. Nenhum rótulo de relação, entidade ou verdade entra no leitor: o avaliador usa esses nomes para descrever sua fixture; o aprendizado recebe apenas sequências opacas. O leitor de dois trechos já existente aprende as cópias ordenadas. As consultas de avaliação combinam identificadores não presentes nas demonstrações e não têm continuação exata; a recuperação usa quadros e raízes já observadas.

A intervenção seguinte muda o segundo identificador conservando o primeiro; muda só o valor conservando ambos; depois muda o primeiro conservando o segundo. Assim, os campos deixam de variar apenas juntos nos dados. Controles adicionais verificam a conservação do destino original, dois valores concorrentes sob as mesmas pistas e o destino após alterar o primeiro identificador. Essa intervenção melhora a informação disponível; não demonstra identificação geral de papéis semânticos.

## Resultados por lote

| Estágio | Casos corretos |
| --- | --- |
| Segunda pista ausente das origens | 6/10 |
| Repetição das mesmas demonstrações | 6/10 |
| Segunda pista copiada nas novas origens | 10/10 |
| Variações cruzadas de pista e valor | 10/10 |
| Repetição de um par cruzado | 10/10 |
| Novo valor rival para as mesmas pistas consultadas | 10/10 |

O subconjunto enriquecido passa **40/40**: 14/14 hipóteses estruturais esperadas, 2/2 conflitos preservados, 24/24 ausências vazias e zero seleções únicas indevidas nesse contrato. Os controles cruzados, contados separadamente, passam **6/6**. A bateria completa conserva as oito falhas iniciais: **52/60 FAIL**. `enriched_quality_status:PASS` não substitui `structural_quality_status:FAIL`. `--strict-quality` retorna 1 por esse FAIL. A CI verifica integridade sem declarar resolução das falhas.

As sementes 20261109 e 20261110 e as duas versões por bijeção mudam símbolos, não formas independentes. A amostra é pequena, delimitada e sintética; não mede precisão factual nem linguagem geral. Nas fases enriquecidas, repetir um par não muda conteúdo, candidatos ou hipótese avaliada. Quando aparece um valor rival, a primeira consulta conserva ambos os destinos e suspende a hipótese; a segunda relação continua com sua raiz anterior.

## Evidência e limites

Cada estágio guarda somente a proveniência então existente; não contém a futura observação rival. O pacote conserva candidatos, quadros, divisões, testemunhas e a hipótese estrutural herdada, mas sempre mantém `answer:null`, `qualified:false`. A fronteira entre relação e valor continua sendo uma interpretação do avaliador, não uma verdade semântica aprendida. A inclusão explícita de uma segunda pista distingue estes destinos observáveis; não resolve os contraexemplos anteriores cujos contratos diferem apesar de dados idênticos.

Seis novos testes verificam denominadores e falhas iniciais, repetição sem desbloqueio, consultas reservadas sem continuação direta, conflitos localizados e proveniência por estágio, controles cruzados e renomeação. Toda leitura verifica restauração, aprendizado e geração padrão inalterados. Relatórios completos: `benchmark-results/trajectory-relation-contrast-{development,reserved}.json`.

Validação local desta etapa: seis novos testes passaram; 145 testes anteriores do pacote, analogia e consumidores estruturais passaram, com um teste opcional de BDR pulado. Os dois relatórios foram gerados e o modo estrito foi confirmado retornando 1 para as falhas iniciais preservadas.

Validação anterior: o commit `5478fb0` passou todos os sete workflows aplicáveis, incluindo [trajectory generation proof 36975033802](https://github.com/marceloroldao/memoria.ia/actions/runs/36975033802); um workflow experimental não aplicável foi pulado. Isso comprova integridade da etapa anterior, não qualidade semântica.

OFF.IA e os três gates pessoais nativos continuam inalterados. A enumeração combinatória de trios e substrings permanece sem garantia de eficiência. Próxima investigação: remover ou tornar ambíguo o separador da segunda pista, preservando os mesmos destinos e controles negativos, para medir quanto do resultado depende da delimitação explícita.
