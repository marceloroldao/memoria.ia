# Contraexemplos sem marcação interna dos papéis

Este estudo não muda o motor nem qualquer seletor. Executa a última extensão experimental, compara a política anterior e registra uma nova bateria de seis famílias. O objetivo é verificar a hipótese de valor livre quando relações diferentes não compartilham um delimitador interno.

## Resultado em bateria separada

| Política | Acertos / casos | Respostas corretas / positivas | Seleções indevidas |
| --- | --- | --- | --- |
| Antes da extensão de valores repetidos | 72/84 | 0/8 | 4 |
| Com a extensão de valores repetidos | 76/84 | 8/8 | 8 |

As sementes 20261028 e 20261029 dão os mesmos resultados. A política atual mantém 68/76 ausências vazias. Há sete consultas por família, com e sem renomeação bijetiva. Esses controles são correlacionados, e as sementes apenas alteram endereços. Qualidade é **FAIL**; a melhoria agregada acompanha aumento de seleções indevidas e não justifica integração.

As famílias `relation_two_no_anchor` e `relation_three_no_anchor` geram, cada uma, quatro falhas por lote: consulta exata e contexto adicional, com e sem renomeação. No caso de dois corpos distintos, a extensão recente abre a seleção que antes era vazia. No caso de três corpos distintos, a falha já ocorre na política anterior. A raiz selecionada existe na memória; o erro está na autorização da escolha pelo contrato, não em inventar um payload.

Os controles com delimitador interno mantêm o veto. Os controles de cauda constante recuperam a correspondência exata e recusam a cauda alterada. Identificador desconhecido, prefixo/sufixo alterados, consulta não relacionada e duas pistas permanecem vazios nas seis famílias.

## Observações idênticas, contratos incompatíveis

`whole_value_two` e `relation_two_no_anchor` fornecem exatamente as mesmas origens, destinos, raiz isolada e consultas. O primeiro gerador interpreta todo o corpo como um valor livre e exige a raiz como resposta. O segundo interpreta parte do mesmo corpo como campo de relação e exige ausência para a quarta relação não demonstrada. O seletor recebe apenas os símbolos, e os resultados são exatamente iguais.

Essa equivalência é verificada por teste, incluindo o resultado completo. Ela mostra que esses dois contratos não podem ser satisfeitos simultaneamente por uma política que dependa apenas dessas observações. A classificação do avaliador não foi fornecida à memória. Não alegamos que o seletor consiga ou deva descobrir automaticamente o papel latente, nem que uma interpretação seja a verdade semântica dos símbolos.

O veto por âncoras é útil quando existe evidência interna comum, mas sua ausência não comprova que todo o corpo tenha um só campo. Dois ou três valores distintos tampouco resolvem essa ambiguidade. A seleção única comprova compatibilidade com uma forma aprendida; sozinha não comprova suporte para o significado pretendido.

## Evidência e validação

Relatórios completos: `benchmark-results/trajectory-analogy-unmarked-{development,reserved}.json`. Incluem observações de treinamento, raiz isolada, consultas, todos os resultados das políticas e endereços das observações para cada raiz. As testemunhas dos candidatos são verificadas contra essa proveniência.

Seis testes novos verificam o aumento de falhas no caso de dois valores, a falha anterior de três valores, equivalência das observações, controles positivos/negativos, renomeação e repetição do resultado na segunda semente. Os 47 testes locais de analogia passaram. A leitura já verifica restauração, aprendizagem e geração padrão inalteradas. `--strict-quality` retorna 1 para esta bateria FAIL. A CI executa o diagnóstico em modo de integridade; testes aprovados não significam que o seletor passou nos contratos de qualidade.

## Pendências e direção

A bateria anterior continua **146/168 FAIL**, com **22/44** respostas positivas e zero seleções indevidas nos seus casos. O resultado histórico permanece válido para aquela bateria; este novo resultado limita sua interpretação. Os denominadores não foram unidos ou substituídos. O runtime nativo e OFF.IA continuam inalterados, e os três gates pessoais nativos permanecem pendentes.

A extensão de valor livre não está qualificada para integração. O próximo estudo deve fornecer evidência que diferencie os papéis, por exemplo um segundo trecho variável na origem que também seja transportado ao destino, e conservar alinhamentos concorrentes. Deve verificar se essa informação permite discriminar as relações sem regras de vocabulário. Na ausência dessa evidência, uma rota estrutural compatível deve continuar sendo tratada como hipótese experimental, não como fato resolvido.
