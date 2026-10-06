# Região conhecida, endereço do episódio ainda ausente

Continuação de `92ba22d`. Os sete workflows aplicáveis desse commit passaram, incluindo o run `37471413915` de trajetória; o workflow condicionado de regressão experimental foi pulado. O incremento adiciona um resolvedor experimental de leitura, seu diagnóstico, sete testes e um passo de CI. Motor, runtime nativo, ingestão, seletores anteriores e OFF.IA permanecem inalterados. O PR continua em rascunho.

## Enumeração de ocorrências

O chamador fornece uma região explícita e uma consulta bruta, sem precisar fornecer inicialmente `source_id` e `sequence`. A função enumera todas as ocorrências de usuário daquela região cujo texto bruto é exatamente igual à consulta. Ela não usa vocabulário, pontuação de pergunta, nome de source ID ou rótulo do avaliador para classificar uma ocorrência como pergunta. `user_turn` e `user_assertion` são aceitos pelo contrato de observação existente; saídas geradas são excluídas.

Ocorrências com conteúdo idêntico permanecem em endereços distintos. Três cópias da consulta produzem três entradas, sem deduplicação por payload. Um endereço único produz `SINGLE_RAW_MATCH`; vários produzem `AMBIGUOUS_RAW_MATCHES`; nenhum produz `NO_RAW_MATCH`. Esses estados descrevem a enumeração, não intenção ou verdade. `selected_target` permanece null em todos os casos.

Para cada endereço enumerado, a consulta nativa de vínculos é feita com a tripla completa `(hierarchy_id, target_source_id, target_sequence)`. Não se emite a consulta nativa que recebe apenas região e retorna vínculos globais. Região ausente, vazia ou inválida é rejeitada. Uma região desconhecida ou uma consulta sem correspondência bruta exata não emite consultas nativas de vínculos e não faz fallback global.

## Duas informações mantidas separadas

O pacote estrutural regional anterior permanece integralmente disponível, inclusive quando a enumeração não encontra endereços. Um prefixo novo conserva neste fixture as duas alternativas estruturais, mas tem zero correspondências brutas exatas. Não se associa essa hipótese automaticamente a episódios cujo texto original era diferente.

As entradas enumeradas conservam o episódio sem vínculo ao lado dos episódios com relações observadas. Cada entrada guarda o resultado nativo e, quando completo e coberto pelo contrato anterior, o join de proveniência por ocorrência. A região e o endereço de conteúdo continuam distintos das origens individuais.

O contrato anterior do join não cobre ecos que repetem a pergunta, porque a API agrupada omite suas origens dos grupos. Nesses casos, o diagnóstico mantém a entrada e o pacote nativo, incluindo `repeat_question_links`, marca `UNSUPPORTED_QUERY_ECHO_LINKS` e não constrói um join que aparentaria estar completo. Para grupos/origens truncados, mantém `INCOMPLETE_NATIVE_EVIDENCE`. Contratos nativos qualificados, com resposta selecionada ou escopo global são rejeitados; a condição não é escondida pelo envelope não qualificado.

## Intervenções e resultados

O fixture anterior contém três ocorrências da pergunta na primeira região e uma na outra região, com fontes e sequências coincidentes entre regiões. Adiciona-se uma cópia gerada da consulta, que não vira alvo. Os estágios são: sem vínculos, vínculos explícitos por episódio e um vínculo adicional cujo conteúdo repete a consulta.

| Consulta | Endereços encontrados | Comportamento |
| --- | --- | --- |
| texto exato na primeira região | três | ambiguidade conservada; episódio sem vínculo mantido |
| mesmo texto na segunda região | um | somente o endereço dessa região; sem seleção automática |
| região desconhecida | zero | nenhuma busca nativa de vínculos; pacote regional vazio |
| prefixo novo na primeira região | zero | nenhuma busca de vínculos; duas alternativas estruturais conservadas |

O eco adicional torna somente o primeiro episódio local não coberto pelo join. Os outros episódios permanecem enumerados; o pacote nativo não é substituído por um resultado vazio. Todas as consultas são de leitura. Flush, fechamento e reabertura preservam os resultados completos, janelas e condições de cobertura.

Seeds 20261205/20261206: **27/27 controles de integridade PASS em cada seed**, em renomeações correlacionadas do mesmo fixture. Os sete testes verificam entradas inválidas/duplicadas, admissão de ocorrências sem classificação linguística, todos os pedidos nativos com endereço local completo, ausência de pedidos globais quando não há match, exclusão gerada, condições de eco/truncamento, rejeição de contratos qualificados/globais e execução nativa real dos dois seeds com BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`.

## Limites e validação

Saídas seguem `answer:null`, `qualified:false`, `selected_target:null`, `global_fallback_used:false`, qualidade factual `NOT_EVALUATED`. Correspondência bruta exata não mede compreensão semântica e não resolve qual episódio o usuário pretendia consultar. Tampouco o episódio sem vínculo é declarado falso ou sem intenção. Permanecem os limites anteriores de cortes/molduras, o gate pessoal nativo 23/26 e os papéis ocultos 2/4 FAIL. Este fluxo ainda é diagnóstico, sem integração com o aplicativo.

Regressões locais dos probes e consumidores estruturais: **259 passed, 1 optional BDR skip**, com os sete testes novos executados contra a biblioteca nativa. Os resumos e hashes completos dos dois seeds foram reproduzidos byte a byte em uma segunda execução. Compilação Python e `git diff --check` passaram. A CI deste incremento ainda precisa executar.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so python -m unittest discover -s tests -p test_trajectory_region_target_probe.py
python scripts/trajectory_region_target_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261205 --summary
python scripts/trajectory_region_target_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261206 --summary
```

Resumos: `benchmark-results/trajectory-region-target-{development,reserved}.json`. Sem `--summary`, reproduzem-se os pacotes, joins e condições de cobertura completos. Próxima investigação: obter testemunhas endereçáveis dos ecos e de páginas adicionais sem omitir relações nem perder a ambiguidade, reutilizando as APIs nativas existentes antes de ampliar este contrato.
