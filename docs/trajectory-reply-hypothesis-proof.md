# Hipótese de resposta observada e abstenção

Continuação de `2f5cf76`, cujos sete workflows aplicáveis passaram, incluindo trajetória `37575024665`. O incremento acrescenta uma política diagnóstica opt-in sobre a recuperação guardada, oito testes, dois resumos e um passo de CI. Não modifica os seletores anteriores ou o runtime nativo. O PR #374 permanece em rascunho.

## Contrato da hipótese

`reply_hypothesis` recebe a saída de `resolve_with_refresh`. Recuperação rejeitada ou esgotada produz `UNAVAILABLE`, sem episódios fabricados. Uma recuperação aceita precisa conservar o escopo de endereços locais, a fronteira regional verificada e o envelope não qualificado. Relações duplicadas, estrangeiras, com alvo divergente ou origem anterior/igual à sequência do alvo são rejeitadas.

A política conserva cada episódio e agrupa suas relações não eco por payload, mantendo todas as origens individuais. Somente **um alvo observado e uma alternativa não eco** permitem `PROPOSAL / UNIQUE_OBSERVED_REPLY_HYPOTHESIS`. O resultado inclui `proposal_payload_id` e `proposal_origins`; `answer:null`, `qualified:false`, `selected_target:null` e `selection_used:false` permanecem.

Nenhum alvo produz `NO_OBSERVED_TARGET`; mais de um, `AMBIGUOUS_TARGETS`; um episódio sem relação não eco, `NO_DISTINCT_REPLY`; alternativas distintas, `COMPETING_REPLIES`. Conteúdo comum em episódios diferentes não escolhe o episódio pretendido. Vinte cópias adicionais de uma alternativa não fazem ela vencer uma rival. Esta é uma regra explícita de cardinalidade de evidência observada, não aprendizagem autônoma de intenção ou verdade.

Ecos nativos conservam endereço, payload e trilha em `query_echo_relations`, mas não viram alternativas de resposta. O fixture usa `query + '!'`: um payload Unicode bruto diferente com a mesma trilha nativa normalizada, sem criar outro alvo bruto exato. A pontuação pertence ao fixture; a política usa somente o flag nativo já verificado pelo transporte.

Um vínculo explícito pode sustentar uma hipótese cuja raiz esteja fora dos candidatos estruturais. A política conserva essa origem e a condição fora dos candidatos, sem inventar compatibilidade de moldura. Relação observada não estabelece relevância semântica ou verdade factual.

## Resultados e comparadores

Os treze casos nativos incluem: molduras sem vínculos, um vínculo, cópias do mesmo vínculo, conflito equilibrado, conflito com 21 contra 1 ocorrências, eco isolado, vínculo com eco, dois episódios com a mesma resposta, rival estrangeira, resposta fora da moldura, consulta sem alvo bruto, recuperação esgotada e atualização que acrescenta outro alvo ambíguo.

Em cada seed, há cinco propostas, sete abstenções e uma indisponibilidade. Todos os episódios, conflitos e origens necessários permanecem disponíveis. A origem gerada é excluída. Nos doze casos de recuperação aceita, a decisão completa se conserva após flush, fechamento e reabertura, exceto o hash da recuperação que registra orçamento/histórico diferentes entre o primeiro percurso e a leitura fria. O argumento da política e as linhas nativas não são modificados por sua execução.

| Regra comparada no avaliador | Seed 20261213 | Seed 20261214 |
| --- | --- | --- |
| nova hipótese por um episódio/uma alternativa | 13/13 | 13/13 |
| hipótese estrutural anterior mapeada a candidato observado | 8/13 | 8/13 |
| primeiro candidato estrutural | 6/13 | 2/13 |
| maioria de ocorrências ligadas | 10/13 | 10/13 |
| payload único ao juntar todos os episódios | 11/13 | 11/13 |

As contagens avaliam exclusivamente o contrato de **propor ou abster-se diante das relações observadas nesses fixtures**. Não são precisão factual. A hipótese estrutural anterior é preservada; os outros comparadores são escolhas do avaliador e não foram instalados em seletores. A maioria erra no conflito reforçado e nas ambiguidades de alvo. Juntar episódios erra nas duas ambiguidades mesmo quando o payload é comum. Escolher o primeiro candidato varia com as renomeações/endereços dos conteúdos.

Seeds 20261213/20261214: **106/106 controles de integridade PASS em cada seed**. Os seeds renomeiam o mesmo fixture; os treze resultados não representam generalização semântica.

## Falha de intenção/qualificação preservada

Dois avaliadores recebem exatamente a mesma recuperação e a mesma proposta. Um espera a resposta observada; outro não admite promovê-la a resposta factual. Esses papéis só são atribuídos depois do processamento, nunca fornecidos à política. O envelope que sempre conserva `answer:null` atende **1/2 expectativas**; promover a proposta automaticamente também atende **1/2**, errando na outra interpretação.

O relatório mantém `semantic_quality_status:FAIL_HIDDEN_ROLE_TWINS` e qualidade factual `NOT_EVALUATED`. A resposta ligada continua observada, sem um mecanismo que descubra qual interpretação ou qualificação o usuário pretendia. Os papéis ocultos históricos 2/4 FAIL, o gate pessoal 23/26 e os demais limites anteriores permanecem. O sucesso de integridade não apaga essas falhas.

## Validação e continuidade

Regressões locais: **290 passed, 1 optional BDR skip**. Os oito testes novos passaram, incluindo os dois seeds contra a biblioteca nativa e a falha de intenção oculta explicitamente esperada. Resumos e hashes completos foram reproduzidos byte a byte. Compilação Python e `git diff --check` passaram. A CI deste incremento ainda precisa executar.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so python -m unittest discover -s tests -p test_trajectory_reply_hypothesis_probe.py
python scripts/trajectory_reply_hypothesis_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261213 --summary
python scripts/trajectory_reply_hypothesis_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261214 --summary
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. Resumos: `benchmark-results/trajectory-reply-hypothesis-{development,reserved}.json`; sem `--summary`, o probe conserva recuperações completas, propostas e comparadores. Não há geração de linguagem nem integração com OFF.IA. Continuam os limites de token/fingerprint de 64 bits, fronteira regional e proveniência estrangeira fornecida pelo chamador. Próxima investigação: comparar inferência de relações sem `reply_to` explícito com esta referência observada, mantendo casos indistinguíveis e abstenção, sem fornecer rótulos ocultos ao aprendizado.
