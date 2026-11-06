# Cópias repetidas com alinhamento consistente

O diagnóstico anterior exige que a variável da origem apareça exatamente uma vez no destino. A extensão experimental deste estudo aprende um quadro separado quando todas as três demonstrações têm o mesmo número de cópias exatas não sobrepostas, pelo menos duas, com os mesmos trechos fixos antes e entre elas. Cada destino mantém uma ponte, um valor livre e um sufixo após a última cópia. Os três valores livres devem continuar distintos. Quadros com âncoras internas nesses valores permanecem bloqueados.

A consulta fornece a variável pelas bordas aprendidas na origem, seguindo a política anterior. O destino precisa reproduzir todas as cópias, todos os trechos fixos e o número exato de ocorrências da variável. A extensão lê apenas raízes inteiras observadas. Cópias corrompidas, sobrepostas ou adicionais não autorizam a seleção. Os quadros rejeitados pelo veto interno continuam registrados com suas âncoras e testemunhas.

Os candidatos da política anterior são preservados e recebem a união das rotas adicionais. Não existe preferência pelo quadro novo ou pelo número de cópias. Se rotas antigas e novas sustentam raízes diferentes, ambas permanecem candidatas e a hipótese fica vazia.

## Bateria mantida

| Política | Acertos / casos | Respostas corretas / positivas | Seleções indevidas | Ausências vazias / negativas |
| --- | --- | --- | --- | --- |
| Uma borda opcional | 138/168 | 14/44 | 0 | 124/124 |
| Extensão por cópias repetidas | 142/168 | 18/44 | 0 | 124/124 |

As sementes 20261024 e 20261025 dão os mesmos resultados. O ganho corresponde aos quatro positivos correlacionados da família `copied_twice`: consulta exata e novo prefixo, com e sem renomeação. As outras onze famílias conservam exatamente os candidatos e as hipóteses anteriores. Nenhum contrato ou denominador foi alterado. Os relatórios completos estão em `benchmark-results/trajectory-analogy-copy-{development,reserved}.json` e incluem o resultado anterior em cada leitura.

A qualidade continua **FAIL**, com 26 respostas positivas sem recuperação por lote. Sementes e renomeações mudam endereços opacos, não constituem novas formas independentes nem medem desempenho no mundo real.

## Controles adicionais

Sete testes novos verificam recuperação das duas formas positivas, recusa com uma cópia corrompida ou uma ocorrência adicional, duas raízes conflitantes, concorrência entre rotas de uma e duas cópias, duas pistas na consulta, veto de relação misturada dentro do valor livre, contagens inconsistentes, sobreposição, paridade das demais famílias e renomeação. Os 34 testes locais de analogia passaram.

Toda consulta verifica igualdade após restauração, aprendizagem inalterada e geração padrão inalterada. `--strict-quality` retorna 1 enquanto a qualidade for FAIL; a CI normal valida integridade sem transformar esse resultado em aprovação de qualidade. O motor, os seletores anteriores, o runtime nativo e OFF.IA permanecem inalterados. Os três gates pessoais nativos continuam pendentes.

## Limitações

Três demonstrações e três valores livres distintos continuam sendo escolhas conservadoras herdadas do diagnóstico. O experimento não cobre inversão, permutação, número variável de cópias ou alinhamentos sem trechos fixos entre as cópias. A ocorrência adicional no valor livre é recusada mesmo que fosse legítima, pois este modelo não distingue seu papel; a regra é conservadora e não uma lei de memória.

A enumeração de trios e substrings permanece sem garantia de eficiência em grandes memórias. Coincidências internas ainda podem vetar respostas legítimas, e o contexto adicional sem prefixo de origem continua sem solução. Não há inferência semântica nem prova de generalidade para linguagem ou outras modalidades.

Próximo estudo: valores constantes ou parcialmente repetidos entre exemplos. A diversidade do identificador pode sustentar uma transformação mesmo quando o valor retornado se repete, desde que isso não autorize destinos conflitantes ou campos de relação sem suporte. Qualquer ganho deve preservar esta bateria e seus negativos.
