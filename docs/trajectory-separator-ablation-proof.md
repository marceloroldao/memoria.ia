# Delimitação das pistas: separador ausente ou ambíguo

O novo diagnóstico reutiliza o pacote e todos os leitores anteriores sem modificá-los. Compara três layouts de origem: separador explícito exclusivo, nenhum separador e separador que também aparece dentro da primeira pista da consulta. Prefixos, sufixos e símbolos dos campos são opacos; nenhum nome de entidade, relação ou valor é fornecido ao aprendizado.

Todos os destinos das demonstrações, raízes isoladas, raiz rival e contratos esperados são byte a byte iguais entre layouts, inclusive nas versões por bijeção. Só as origens e suas consultas recebem outro separador. As pistas têm múltiplos símbolos; a primeira pista reservada contém um símbolo interno que serve de delimitador no layout ambíguo. Esse símbolo está presente no destino nos três layouts: não se altera o alvo para fabricar uma diferença de qualidade.

## Contrato e resultados

Cada layout usa três pares diagonais, três pares com variação cruzada e duas raízes isoladas para um identificador reservado. A leitura ocorre depois do suporte cruzado, depois de duas repetições de um par e depois de observar um valor rival para as mesmas pistas. Cada estágio tem sete consultas: primeiro destino, contexto inicial novo, segundo destino, segunda pista desconhecida, primeira pista desconhecida, segunda pista ausente e duas consultas concatenadas. Há uma versão renomeada para cada caso.

| Layout por lote | Casos corretos | Hipóteses esperadas | Conflitos preservados | Ausências vazias | Casos com todos os alvos recuperados |
| --- | --- | --- | --- | --- | --- |
| Explícito | 42/42 | 14/14 | 4/4 | 24/24 | 18/18 |
| Ausente | 24/42 | 0/14 | 0/4 | 24/24 | 0/18 |
| Ambíguo | 28/42 | 0/14 | 4/4 | 24/24 | 18/18 |

Total: **94/126 FAIL**, 14/42 hipóteses estruturais corretas, 8/12 conflitos, 72/72 ausências vazias, 36/54 casos retendo todos os alvos e **zero seleções únicas indevidas** neste contrato. Os positivos sem hipótese continuam falhas de cobertura; recuperar um candidato não é contado como responder. O modo `--strict-quality` retorna 1. Sucesso de integridade na CI não altera esse FAIL.

As sementes 20261111/20261112 mudam endereços, mantendo as mesmas formas. Renomeação, contexto inicial e repetição são controles correlacionados, não descobertas independentes. Este contrato usa pistas mais longas e tem denominador próprio; não substitui os resultados 52/60 do experimento anterior nem suas oito falhas iniciais.

## O que a ablação revela

Sem separador, o leitor atual não aprende um quadro de dois trechos que recupere os destinos reservados. A sequência inteira da origem não está copiada contiguamente no destino, que contém uma ponte entre as duas pistas. Os controles negativos vazios passam, mas não compensam a perda dos positivos e dos conflitos.

No layout ambíguo, o separador aparece tanto dentro da primeira pista reservada quanto na fronteira entre as pistas. O leitor enumera uma divisão que recupera as raízes esperadas e outra divisão válida sem raiz observada. Os candidatos e suas testemunhas permanecem acessíveis; `partial_alignment_support` suspende a hipótese. Após o valor rival, ambas as raízes esperadas permanecem e o conflito é preservado. Repetir um par não altera destinos recuperados ou hipóteses em nenhum layout.

O resultado depende de delimitação observável, e não apenas da presença dos destinos na memória. Não se conclui que seja impossível aprender fronteiras sem delimitador; este leitor conservador não demonstrou esse mecanismo. Também não se elimina uma divisão sem suporte para autorizar a outra. A ausência de observações em uma divisão continua informação incompleta.

## Verificação e próxima direção

Seis novos testes verificam denominadores e falhas, igualdade de todos os destinos e expectativas entre layouts, suporte parcial com raízes preservadas, perda de cobertura sem separador e repetição, renomeação/proveniência/pacotes sem autorização e um controle do avaliador que rejeita selecionar apenas uma raiz de um conflito. Toda leitura verifica restauração, aprendizado e geração padrão inalterados; consultas reservadas não têm continuação exata observada. O catálogo de cada estágio não contém a futura raiz rival.

Relatórios completos: `benchmark-results/trajectory-separator-ablation-{development,reserved}.json`. Reprodução: `python scripts/trajectory_separator_ablation_probe.py --seed 20261111` ou `--seed 20261112`. O pacote permanece `answer:null`, `qualified:false`; runtime nativo, OFF.IA e os três gates pessoais não mudam. Não há garantia de eficiência da enumeração.

Validação local: seis novos testes passaram e 151 testes anteriores passaram, com um teste opcional de BDR pulado. Os dois lotes reproduziram os mesmos agregados. O modo estrito foi confirmado retornando 1 para o FAIL, e a árvore publicada deve preservar os relatórios completos preparados localmente.

Próxima investigação: representações que conservem várias correspondências posicionais mesmo sem separador comum aprendido, com testemunhas explícitas para cada hipótese de fronteira. Qualquer extensão deve preservar contraexemplos com dados indistinguíveis e a suspensão por alternativas sem suporte. Não liberar uma hipótese apenas porque o alvo correto está entre os candidatos.
