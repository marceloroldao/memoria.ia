# Testemunhas paginadas: ecos e origens antes truncadas

Continuação de `a61d75a`, cujos sete workflows aplicáveis passaram. O incremento adiciona um caminho experimental de leitura, sete testes, dois resumos e um passo de CI. O PR #374 permanece em rascunho.

## Transporte e escopo da evidência

A API nativa existente `probe_structural_linked_replies` fornece testemunhas individuais de `reply_to`, inclusive o endereço de uma ocorrência cujo texto repete a consulta. Ela pagina globalmente as testemunhas da consulta. O diagnóstico declara esse transporte como `global_query_witness_pages`; não o apresenta como uma API nativa restrita à região.

O chamador fornece região e consulta bruta. A enumeração anterior encontra todas as ocorrências locais de usuário com texto exatamente igual, excluindo saídas geradas. O join admite somente testemunhas cujo endereço completo de alvo pertence a essa enumeração. Uma testemunha da outra região, mesmo com source ID, sequência e conteúdo coincidentes, fica fora das relações locais. Sem alvo bruto local, não há pedido nativo de testemunhas.

Cada relação admitida confere endereço, texto bruto, tipo de fonte e `reply_to` contra as linhas observadas. A cobertura deve coincidir com todas as relações de usuário observadas para os alvos enumerados. Páginas incompletas, offsets saltados, duplicações, totais alterados e contratos com resposta/seleção/qualificação são rejeitados. As alternativas estruturais e suas origens compartilhadas permanecem disponíveis; uma origem estrangeira de payload não ganha vínculo local por compartilhar conteúdo.

O endereço nativo de trilha normalizada e o identificador estrutural do payload bruto Unicode continuam em campos distintos. Um eco pode ter raiz fora dos candidatos estruturais: sua relação endereçável é conservada nesse campo, sem transformá-lo em candidato ou resposta. Os resolvedores anteriores permanecem disponíveis com seus limites explícitos.

## Intervenção e resultado

O fixture mantém três alvos locais da mesma consulta, um alvo em outra região, alternativas conflitantes e uma cópia gerada excluída. Acrescenta vinte cópias de uma resposta ao primeiro episódio e um eco endereçado. A consulta agrupada anterior apresenta origens truncadas e omite a origem do eco; a consulta paginada recupera as 25 testemunhas.

| Tamanho de página | Páginas | Testemunhas globais | Relações por episódio local |
| --- | --- | --- | --- |
| 1 | 25 | 25 | 23, 1, 0 |
| 7 | 4 | 25 | 23, 1, 0 |
| 64 | 1 | 25 | 23, 1, 0 |

O primeiro episódio conserva 21 cópias da primeira alternativa, uma alternativa rival e um eco. O segundo conserva um vínculo; o terceiro permanece sem vínculo. Uma testemunha estrangeira é excluída da evidência da primeira região e conservada na própria região. Multiplicidade descreve ocorrências, sem votação nem preferência pela alternativa mais repetida.

Seeds 20261207/20261208: **25/25 controles de integridade PASS em cada seed**. As três paginações produzem resultados regionais completos idênticos. Leituras não alteram linhas; flush, fechamento e reabertura conservam páginas, janelas estruturais e joins. Os seeds renomeiam o mesmo fixture; não representam uma amostra independente de compreensão.

## Limites e validação

Todos os envelopes seguem `answer:null`, `qualified:false`, `selected_target:null`, `selection_used:false`, qualidade factual `NOT_EVALUATED`. Relação observada não prova verdade, intenção ou relevância semântica. A API não fornece token de snapshot para paginação: verificações de cabeçalho e cobertura detectam inconsistências ensaiadas, sem garantir atomicidade sob escritores concorrentes arbitrários. Os limites anteriores, incluindo gate pessoal nativo 23/26 e papéis ocultos 2/4 FAIL, permanecem.

Regressões locais: **266 passed, 1 optional BDR skip**. Os sete testes novos passaram, incluindo execução nativa dos dois seeds. Resumos e hashes completos reproduzidos byte a byte; compilação Python e `git diff --check` passaram. CI de `5205b8b`: sete workflows aplicáveis passaram, incluindo trajetória `37554455794`; a regressão experimental condicionada foi pulada.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so python -m unittest discover -s tests -p test_trajectory_paged_relation_probe.py
python scripts/trajectory_paged_relation_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261207 --summary
python scripts/trajectory_paged_relation_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261208 --summary
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. Resumos: `benchmark-results/trajectory-paged-relation-{development,reserved}.json`; sem `--summary`, o script conserva os pacotes completos. Próxima investigação: testar divergência entre páginas sob intervenção controlada, preservando rejeição explícita e os limites de consistência.
