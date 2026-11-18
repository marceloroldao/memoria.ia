# Veto experimental por âncoras internas

O seletor de analogia anterior aceita como um único valor livre tudo que está entre o prefixo e o sufixo comuns do destino. No contraexemplo `varying_tag`, isso reúne o campo de relação variável, um delimitador comum e o valor. Uma raiz isolada com uma quarta relação acaba selecionada, embora o contrato da bateria exija ausência.

`trajectory_analogy_anchor_probe.py` executa uma política em sombra: depois de aprender os mesmos quadros, identifica trechos contíguos comuns dentro dos três valores livres. Conserva os trechos máximos e todas as posições de ocorrência, sem escolher uma divisão entre campos. Quadros com essas âncoras são vetados para seleção. O relatório preserva integralmente candidatos, hipótese e testemunhas do seletor anterior, além das âncoras e testemunhas dos quadros bloqueados. Uma raiz continua elegível se outro quadro não bloqueado a sustentar.

Nenhuma regra usa palavras, categorias semânticas ou os campos anotados do gerador. Não alteramos o motor, o seletor anterior, o runtime nativo ou a política padrão. Leituras verificam restauração, estado de aprendizagem e geração padrão sem alterações.

## Bateria original, sem mudar os contratos

| Política | Acertos / casos | Respostas corretas / positivas | Seleções indevidas | Ausências vazias / negativas |
| --- | --- | --- | --- | --- |
| Seletor anterior, sementes 20261016 e 20261017 | 128/168 por lote | 8/44 | 4 | 120/124 |
| Veto em sombra, sementes 20261018 e 20261019 | 132/168 por lote | 8/44 | 0 | 124/124 |

As duas novas sementes mudam apenas os endereços opacos. Os casos com renomeação são controles correlacionados, não novas formas independentes. Os relatórios completos ficam em `benchmark-results/trajectory-analogy-anchor-{development,reserved}.json`. A qualidade permanece **FAIL**: continuam 36 respostas positivas sem recuperação em cada lote. Os controles `baseline` e `invariant_tag` conservam todas as respostas corretas e negativas vazias.

## Limite demonstrado do veto

Um novo controle positivo usa valores legítimos com um símbolo interno coincidente nas três demonstrações. O seletor anterior recupera a raiz correta; o veto recusa essa resposta. Outro teste preserva as duas posições de uma âncora repetida. Esses controles ficam nos cinco testes de `test_trajectory_analogy_anchor_probe.py`; não foram acrescentados ao denominador de 168, para manter a comparação com a bateria original.

Uma âncora interna indica que há outra divisão possível, mas não prova que essa divisão tenha significado de relação. O veto fecha o contraexemplo conhecido à custa de cobertura. Não estabelece que papéis latentes possam ser inferidos apenas pelos símbolos. A política segue experimental e não está pronta para integração. A enumeração de substrings e de trios não tem garantia de eficiência para grandes memórias.

## Validação e próximo passo

Localmente: cinco testes novos, seis testes da analogia anterior, cinco testes de estresse e 59 testes do gerador passaram. A CI executa novamente a política em sombra e as regressões existentes. `--strict-quality` continua retornando 1 quando a qualidade é FAIL; a execução normal verifica integridade, sem declarar aprovação de qualidade.

O próximo estudo deve preservar interpretações concorrentes de um e vários campos e testar exemplos adicionais que distingam essas interpretações. Não é suficiente transformar este veto em regra geral. Os três gates pessoais nativos continuam pendentes; esta comparação não modifica seus resultados nem habilita OFF.IA.
