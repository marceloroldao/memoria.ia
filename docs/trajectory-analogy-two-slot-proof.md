# Duas pistas variáveis transportadas da origem ao destino

O estudo anterior mostrou contratos incompatíveis para observações idênticas: uma cauda podia ser interpretada como valor inteiro ou como relação mais valor. Este experimento acrescenta informação à origem, sem mudar os seletores anteriores. Três pares contêm dois trechos variáveis distintos separados por um trecho comum. Ambos aparecem exatamente uma vez em seus destinos. A política aprende as bordas, o separador e a ordem das duas cópias pelos símbolos, sem nomes de campos ou regras de vocabulário.

O destino inclui um prefixo, um trecho fixo entre as cópias e um valor livre com sufixo comum. Não exige delimitador entre a segunda cópia e o valor: a extensão aprende essa borda pela cópia exata do segundo trecho da origem. O valor livre mantém três demonstrações distintas e o veto por âncoras internas. Todas as raízes candidatas precisam copiar os dois trechos consultados exatamente uma vez.

## Bateria própria

| Cenário | Acertos / casos por lote | Comportamento |
| --- | --- | --- |
| Ordem direta | 18/18 | As duas pistas selecionam o destino correspondente |
| Ordem invertida no destino | 18/18 | A ordem inversa é aprendida pelos exemplos |
| Conflito na primeira combinação | 18/18 | Dois destinos para a mesma combinação são preservados; a outra combinação continua única |
| Separador repetido no trecho consultado | 12/18 | Duas divisões ficam registradas e os seis positivos são recusados |

Total por semente: **66/72 FAIL**, **14/20** respostas corretas, **4/4** conflitos preservados, **48/48** ausências vazias e zero seleções únicas indevidas. As sementes 20261030 e 20261031 têm o mesmo resultado. Cada cenário contém nove consultas, com e sem renomeação bijetiva. As versões são correlacionadas e as sementes mudam endereços, não novas formas independentes.

Os dois destinos isolados compartilham o primeiro trecho e diferem no segundo. Nenhum deles participa dos três pares de treinamento. A consulta pode escolher cada um usando ambos os trechos copiados. Uma pista desconhecida, pista ausente, separador alterado, duas pistas completas na mesma consulta ou entrada não relacionada mantêm ausência.

Na combinação conflitante, dois valores diferentes para os mesmos dois trechos permanecem candidatos inteiros. A política não escolhe pela ordem, novidade ou quantidade de rotas. Os candidatos da política anterior são preservados e unidos às novas rotas, sem prioridade.

## Ambiguidade mantida visível

Quando o primeiro trecho consultado contém outra ocorrência do separador, duas divisões são possíveis. Ambas aparecem no relatório, com posições e pares de trechos; nenhuma é autorizada. Os seis positivos recusados continuam sendo falhas de cobertura, não foram reclassificados como ausências corretas. Esta extensão exige uma divisão única da consulta e não soluciona alinhamentos gerais.

## Relação com as baterias anteriores

Este experimento usa origens diferentes, com uma segunda pista observável. **Não transforma o resultado 76/84 da bateria sem marcação em aprovação.** Um teste reaplica os dois contraexemplos anteriores: nenhuma forma de dois campos é aprendida ali, os candidatos anteriores ficam exatamente iguais e a seleção indevida permanece. A comparação de 146/168 da bateria original também não foi alterada.

O ganho aqui demonstra uso de informação adicional, não recuperação do papel semântico oculto a partir dos mesmos dados. As posições podem corresponder a identificador e relação no gerador, mas o seletor recebe apenas tuplas de símbolos. Os três pares precisam variar os dois trechos e seus valores livres; isso continua sendo uma escolha conservadora experimental.

## Evidência e validação

Relatórios completos: `benchmark-results/trajectory-analogy-two-slot-{development,reserved}.json`. Preservam pares de treinamento, endereços das observações, quadros, alternativas de divisão, candidatos, testemunhas e política anterior. Todo candidato e testemunha é verificado contra a proveniência. As leituras verificam paridade após restauração, aprendizagem inalterada e geração padrão inalterada.

Seis novos testes verificam seleção por ambas as pistas, aprendizado de ordem inversa, conflito restrito à combinação consultada, divisão ambígua, renomeação/segunda semente e preservação das falhas anteriores. Os 53 testes locais de analogia passaram. `--strict-quality` retorna 1 para o resultado FAIL; aprovação da CI confirma integridade e regressões, não aprovação dos gates de qualidade.

O motor, os seletores anteriores, o runtime nativo e OFF.IA permanecem inalterados. Os três gates pessoais nativos continuam pendentes. Não existe prova de eficiência da enumeração de trios e substrings ou de generalidade para linguagem e modalidades arbitrárias.

Próximo passo: testar alinhamentos múltiplos com candidatos concorrentes e exemplos em que uma das pistas se repete entre demonstrações. Mais pistas observáveis podem reduzir ambiguidade, mas não devem impor uma decisão única antes que as rotas e os negativos a sustentem.
