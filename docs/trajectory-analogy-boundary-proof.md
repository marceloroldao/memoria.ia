# Extensão experimental com uma borda de origem opcional

A analogia anterior exige prefixo e sufixo comuns nas três origens. A política em sombra deste estudo aceita que uma dessas bordas seja vazia, desde que a outra exista. Não remove bordas que foram observadas e não permite que ambas sejam vazias. Mantém as exigências anteriores: três variáveis distintas, cópia única da variável no destino, prefixo de destino comum, ponte e sufixo de destino não vazios, três valores livres distintos e veto por âncoras internas.

Quando existe prefixo de origem, a consulta precisa conter exatamente uma ocorrência dele; a leitura pode começar ali. Quando o prefixo é vazio, a leitura começa obrigatoriamente na posição zero. Sem evidência para localizar o fim de um contexto adicional, a política não escolhe arbitrariamente uma posição posterior. Todos os destinos continuam sendo raízes inteiras previamente observadas, com os quadros e as testemunhas preservados.

## Comparação no mesmo contrato de 168 casos

| Política | Acertos / casos | Respostas corretas / positivas | Seleções indevidas | Ausências vazias / negativas |
| --- | --- | --- | --- | --- |
| Veto por âncoras internas | 132/168 | 8/44 | 0 | 124/124 |
| Uma borda de origem opcional | 138/168 | 14/44 | 0 | 124/124 |

As sementes 20261022 e 20261023 dão os mesmos resultados. A extensão recupera quatro positivos na família sem sufixo, incluindo o contexto adicional, e dois positivos exatos na família sem prefixo. Os controles renomeados são correlacionados; as sementes apenas mudam os endereços opacos. Qualidade permanece **FAIL**, com 30 respostas positivas sem recuperação em cada lote. Os relatórios completos ficam em `benchmark-results/trajectory-analogy-boundary-{development,reserved}.json` e contêm também a política anterior para cada consulta.

Os casos das outras dez famílias mantêm exatamente os candidatos e hipóteses anteriores. Em particular, o contraexemplo de relação misturada continua vetado, as ausências permanecem vazias e as limitações de valores constantes, cópia duplicada ou invertida e bordas compartilhadas dos valores continuam registradas. Não substituímos o denominador nem mudamos os resultados esperados.

## Limite de identificabilidade sem prefixo

Na família sem prefixo, a consulta positiva com contexto adicional tem a forma `bloco novo + identificador + sufixo`. O negativo chamado `changed_prefix` também tem essa forma, com outro bloco novo. O seletor recebe apenas símbolos: o rótulo do gerador não fornece um critério estrutural para separar esses papéis. A política conserva o negativo e deixa o positivo sem resposta; não alegamos ter solucionado essa distinção. Isso orienta a necessidade de mais exemplos ou contexto observado, sem regra de vocabulário.

## Validação e limites mantidos

Seis novos testes verificam ambas as bordas vazias separadamente, a recusa sem nenhuma borda, extração exata, paridade com a política anterior nas outras famílias, preservação de dois destinos conflitantes, consulta com duas pistas e renomeação bijetiva. Os 27 testes locais de analogia passaram. Toda consulta verifica restauração, estado de aprendizagem e geração padrão inalterados. `--strict-quality` retorna 1 enquanto a qualidade for FAIL; a CI normal verifica integridade e mantém as falhas de cobertura no relatório.

O motor, os seletores anteriores e o runtime nativo não foram alterados. A extensão segue em um script separado e não foi habilitada em OFF.IA. Não há prova de generalidade para linguagem ou outras modalidades, nem garantia de eficiência da enumeração de trios/substrings. O veto por coincidência interna ainda perde uma resposta legítima no controle anterior. Os três gates pessoais nativos permanecem pendentes.

Próximo passo: testar limites onde o identificador aparece em posições diferentes ou várias vezes e estudar alinhamentos concorrentes. Qualquer relaxamento deve conservar os negativos, as raízes concorrentes e a proveniência, sem atribuir automaticamente significado aos campos.
