# Região de proveniência e endereço de resposta observado

Continuação de `27692db`. Este diagnóstico usa o runtime nativo existente, compilado com BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. Não altera motor, runtime, contrato de ingestão ou OFF.IA. O incremento anterior passou nos sete workflows aplicáveis; o run `37384017364` concluiu tanto `proof` quanto `native-bridge`, incluindo cortes, regiões e regressões finais. O oitavo workflow foi pulado por sua condição existente.

## Comparação e limite do escopo

A projeção estrutural anterior recebe uma região explícita. Aqui comparamos o alcance dessa região de proveniência com vínculos `reply_to` explicitamente registrados no BDR. O diagnóstico não alimenta esses vínculos no aprendiz de molduras e não cria uma nova política de seleção.

Há uma particularidade importante no contrato nativo `resolve_structural_text`, modo `linked_reply_evidence`: **somente `hierarchy_id` não restringe os vínculos à região**. Sem endereço de alvo, `evidence_scope` é `matching_targets` e os grupos são globais. O diagnóstico verifica isso em todos os estágios. A visualização regional é uma filtragem externa, de leitura, dos `sources` pelo `hierarchy_id`; não é apresentada como recurso de seleção nativa. A restrição nativa ao episódio exige a tripla `hierarchy_id`, `target_source_id`, `target_sequence`, produzindo `evidence_scope: exact_target`.

## Intervenções

Fixtures opacos usam a mesma pergunta e o mesmo `source_id` em regiões diferentes e duas sequências da mesma região. Isso impede tratar texto ou `source_id` isolados como identidade do episódio. Os vínculos são declarados diretamente pelo fixture, nunca inferidos de proximidade nem extraídos de saída gerada.

| Leitura | Inicial | Repetição ligada ao primeiro alvo | Rival ligado ao primeiro alvo |
| --- | --- | --- | --- |
| global por texto | duas alternativas | duas alternativas | duas alternativas |
| projeção da primeira região | duas alternativas de episódios distintos | duas alternativas | duas alternativas |
| primeiro alvo, endereço completo | primeira alternativa | mesma alternativa, duas ocorrências | ambas as alternativas, conflito |
| segunda ocorrência da pergunta na mesma região | rival | rival | rival |
| mesmo texto e source ID em outra região | rival | rival | rival |
| região com evento adjacente sem vínculo | sem vínculo | sem vínculo | sem vínculo |
| sequência errada ou consulta desconhecida | vazia | vazia | vazia |

A região sem vínculo possui uma continuação temporal nativa observável. Mesmo assim, sua leitura de vínculos fica vazia. Registrar vínculos não altera o resultado temporal existente. A repetição mantém o endereço da trilha do conteúdo, acrescentando ocorrência, e não escolhe uma alternativa por maioria. O rival tardio retém ambas as trilhas no mesmo alvo, com `status: CONFLICT`.

Cada origem emitida aponta para uma linha observada e um `reply_to` exato; o alvo também é endereçável. As leituras não modificam as janelas. Após cada estágio, flush, fechamento e reabertura preservam os pacotes completos e todas as linhas, incluindo os vínculos.

## Resultado e limitações

Seeds 20261129 e 20261130: **28/28 controles de integridade PASS em cada seed**. São duas renomeações correlacionadas do mesmo fixture; esse denominador não mede compreensão geral nem qualidade factual. Os relatórios guardam as alternativas, origens, evidência temporal e SHA256 dos pacotes de cada estágio.

Todos os resultados mantêm `answer:null`, `qualified:false`, `selection_used:false`. `factual_quality_status` é `NOT_EVALUATED`: um vínculo comprova que a relação foi registrada, não que seu conteúdo seja verdadeiro. O diagnóstico depende de um endereço fornecido pelo chamador; não aprende sozinho qual episódio o usuário pretende consultar. Os gêmeos anteriores sem papel observado continuam com FAIL 2/4, e os resultados estruturais anteriores não foram substituídos.

O gate pessoal nativo original foi executado novamente: **23/26**, com as mesmas falhas `known_answer_first`, `other_subject_first`, `absent_recombination_empty`. O script original retorna sucesso técnico enquanto reporta essas falhas de qualidade; não se interpreta esse exit code como 26/26.

## Validação

Três testes novos cobrem projeção sem mutação, identidade completa do fixture e execução real dos 28 controles nos dois seeds. O teste nativo exige `MEMORIA_NATIVE_LIBRARY`; o novo passo de CI fornece essa variável depois de compilar o runtime com BDR fixado, evitando skip silencioso nesse passo. Regressões locais dos probes e consumidores estruturais: **242 passed, 1 optional BDR skip**, com a biblioteca nativa fornecida e o teste novo executado. Os relatórios dos dois seeds foram reproduzidos byte a byte em uma segunda execução. Compilação Python e `git diff --check` passaram. A CI deste incremento ainda precisa executar.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so python -m unittest discover -s tests -p test_trajectory_region_reply_probe.py
python scripts/trajectory_region_reply_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261129
python scripts/trajectory_region_reply_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261130
python scripts/mobile_personal_proof_gate.py --library build/trajectory-native/libmemoria_mobile.so
```

Relatórios: `benchmark-results/trajectory-region-reply-{development,reserved}.json`. Próxima investigação: comparar o mesmo par pergunta/conteúdo com e sem relação explicitamente observada, conectando endereços nativos aos pacotes estruturais anteriores somente como proveniência. Manter desconhecido o episódio pretendido quando não há endereço observado, sem transformar essa associação em fato ou integrar o caminho à produção.
