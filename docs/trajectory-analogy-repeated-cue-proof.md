# Pistas repetidas e competição entre formas específicas e amplas

Este diagnóstico executa o leitor de consenso anterior sem modificar aprendizagem, seleção ou motor. As observações usam símbolos opacos e duas pistas na origem. Três demonstrações repetem uma pista e variam a outra; os destinos conservam ambas. O destino termina com um valor variável e um delimitador, sem uma ponte entre a segunda pista e o valor.

Uma consulta usa uma combinação ausente das demonstrações. Duas raízes isoladas já observadas conservam suas duas pistas, mas têm prefixos de destino diferentes. A primeira corresponde à forma específica demonstrada. A segunda só recebe uma rota depois de três novas demonstrações com ambas as pistas variáveis. Nesse estágio, o contrato exige conservar as duas raízes como conflito. Nenhuma raiz é gerada pelo diagnóstico.

## Resultado sequencial

| Pista repetida | Demonstrações específicas | Repetição de um par | Adição da forma ampla | Nova repetição do par específico |
| --- | --- | --- | --- | --- |
| Primeira | Sem candidato; resposta esperada falha | Mesma falha | Apenas raiz ampla; conflito esperado falha | Mesma seleção única indevida |
| Segunda | Raiz específica selecionada | Mesmo resultado | Duas raízes preservadas; hipótese suspensa | Conflito preservado |

Repetições acrescentam endereços de observação, mas não raízes de conteúdo. As correspondências e testemunhas podem crescer, sem serem usadas como votos. Nos casos avaliados, repetir o par específico não elimina o conflito nem repara a perda da rota específica.

A assimetria tem uma limitação estrutural identificável: com a primeira pista fixa, o trecho variável é a segunda pista, imediatamente seguida do valor no destino. O leitor anterior de um campo exige uma ponte não vazia após esse trecho. O leitor de dois campos exige três valores distintos em cada pista. Com a segunda pista fixa, o leitor de um campo consegue usar o intervalo até o valor como ponte. Estes requisitos conservadores não cobrem as duas formas igualmente.

O rótulo `UNIQUE_ROOT_WITH_COMPLETE_ALIGNMENT_SUPPORT` aparece na seleção ampla indevida. A enumeração cobre os quadros aprendidos, mas a forma específica ausente da aprendizagem não aparece nessa enumeração. Portanto, consenso entre divisões enumeradas não comprova cobertura de todas as relações demonstradas. Os relatórios preservam esse rótulo e a falha, sem alterar retrospectivamente o leitor anterior.

## Contratos e limites

Cada lote tem quatro estágios, três consultas (exata, com contexto inicial e pista fixa alterada), duas posições de pista repetida e duas versões por renomeação: **32/48 FAIL**, com **8/16** respostas corretas, **8/16** conflitos preservados, **16/16** ausências vazias e **8 seleções únicas indevidas**. As oito seleções derivam da mesma lacuna estrutural em dois estágios, duas consultas e duas renomeações; não são oito descobertas independentes. Sementes 20261103 e 20261104 mudam endereços opacos, mantendo o mesmo desenho.

Esta bateria tem denominador próprio. O resultado anterior **66/72** e os oito controles de consenso permanecem inalterados. O diagnóstico não corrige as falhas sem marcação, os três gates pessoais nativos ou o runtime OFF.IA.

Relatórios completos: `benchmark-results/trajectory-analogy-repeated-cue-{development,reserved}.json`. Cada estágio registra seu catálogo de endereços sem incluir observações futuras. Toda leitura verifica igualdade após restauração, geração padrão e aprendizagem inalteradas e testemunhas vinculadas a raízes observadas. Seis testes cobrem assimetria, perda de conflito, repetição, proveniência por estágio, bijeção e contrato da semente reservada. O modo `--strict-quality` retorna 1; a CI executa integridade sem declarar qualidade aprovada.

Próximo passo: estudar uma representação que conserve as demonstrações de uma forma específica mesmo quando ela não satisfaz os requisitos atuais de quadro. Qualquer ampliação precisa reavaliar os contraexemplos sem marcação e expor suporte incompleto; liberar a ponte vazia indiscriminadamente ainda não está validado.
