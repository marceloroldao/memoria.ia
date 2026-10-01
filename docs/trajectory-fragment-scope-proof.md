# Ablação de escopo dos fragmentos — proposta rejeitada

## Resultado

Uma política sombra melhora a comparação da ponte de 18/32 para 24/32 critérios, com respostas corretas de 2/16 para 8/16. Ainda viola o contrato anterior de suporte próprio da origem concorrente. **Não foi adotada:** o motor, os pesos, a seleção padrão e a hipótese opcional publicada permanecem inalterados.

| Fixture fictício | Política atual | Política sombra |
|---|---:|---:|
| Capturas isoladas | 2/8 | 2/8 |
| Pares ordenados | 2/8 | 8/8 |
| Pares com conflito | 6/8 | 6/8 |
| Barreira do assistente | 8/8 | 8/8 |
| Total | 18/32 | 24/32 |

Nos 32 casos, ambas preservam 12/12 abstenções de ausência e 4/4 conflitos, sem hipótese diferente do alvo esperado. Esses critérios não incluem o controle adversarial adicional abaixo. A melhora local não demonstra qualidade geral nem resolve as três falhas pessoais nativas.

## Proposta avaliada

Somente em COMBINED_RECALL não truncado com uma raiz de destino observado: permitir um candidato externo à resposta quando seu trecho está transportado em todas as suas origens; permitir testemunhas de outra origem quando o mesmo nódulo tem alguma testemunha para a raiz escolhida, ou quando o trecho está contido na própria origem dessa testemunha. Mantêm-se os vetos de origem contida na consulta, origem contendo uma pista completa, múltiplos destinos de raiz, ausência de testemunhas e truncamento. Todos os candidatos e testemunhas originais continuam visíveis.

A relaxação perde a exigência de que **cada origem concorrente** também sustente separadamente a resposta escolhida. Ela remove a interferência de “eu robô” na pergunta sobre o drone, mas permite ignorar evidência que o contrato anterior ainda exige conservar como impedimento da consolidação.

## Contraexemplo e rejeição

Dois pares separados: `Código de Daro?` → `Daro: 791.` e `código de daro?` → `Daro: 415.`. A segunda origem nunca sustenta o primeiro destino. A política atual se abstém na primeira pergunta; a sombra emite o primeiro destino e deixa testemunhas concorrentes fora do escopo. Isso quebra `test_source_scope_requires_own_support_for_the_observed_root_destination`. Não há normalização de caixa nem interpretação semântica nessa decisão.

O contraexemplo foi repetido com Unicode, UTF-8 e renomeação bijetiva dos símbolos: **0/4 controles de suporte próprio passam na sombra**. São versões correlacionadas do mesmo controle, não quatro contraexemplos independentes. O teste inicial da alteração temporária passou em 17/18 contratos anteriores e falhou nesse controle. A alteração foi revertida antes de publicar o experimento.

## Reprodução e integridade

`python scripts/trajectory_fragment_scope_probe.py` executa a política somente em uma subclasse local ao diagnóstico, com substituições temporárias encerradas ao final de cada comparação. Não há importação dessa política pelo motor. O relatório distingue `integrity_status: PASS` de `policy_status: REJECTED`; o retorno zero indica reprodução, não aprovação da política.

Usa os mesmos registros fictícios da ponte anterior. Confere igualdade completa dos casos da política atual com `trajectory-native-bridge-report.json`, obtido anteriormente das janelas frias do BDR. **Este diagnóstico não executa a biblioteca nativa** e não apresenta o resultado sombra como teste nativo. Os ciclos de leitura verificam paridade após restauração, GenerationResult completo inalterado e snapshots/estado de aprendizado intactos. As consultas e respostas geradas não são observadas como treinamento.

Três testes novos verificam reprodução da violação, manutenção de múltiplos destinos completos e veto de fragmento introduzido concorrente. Após reverter a proposta, os 18 testes anteriores da hipótese e os 59 do gerador passaram localmente. O workflow recebe o diagnóstico como verificação de integridade e mantém todos os gates anteriores. Relatório completo: `benchmark-results/trajectory-fragment-scope-report.json`.

Próximo problema: distinguir fragmento transportado de competição de origem sem dispensar o suporte próprio exigido pelo contrato. Continuam pendentes a ponte 18/32 e o gate nativo 23/26. PR draft, sem ativação no OFF.IA e sem alteração nativa.
