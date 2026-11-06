# Atualização regional com orçamento explícito

Continuação de `f6e349d`, cujos sete workflows aplicáveis passaram, incluindo trajetória `37559701392`. O incremento adiciona um caminho experimental opt-in de atualização/repetição, oito testes, dois resumos e um passo de CI. O PR #374 permanece em rascunho.

## Comportamento

`resolve_with_refresh` exige `max_attempts` inteiro entre 1 e 8. A primeira tentativa usa as linhas fornecidas pelo chamador e o resolvedor regional guardado anterior. Uma rejeição por `STALE_INPUT_ROWS` ou `STALE_REGIONAL_WINDOW` permite uma nova tentativa, se houver orçamento.

Antes da nova resolução, lê a janela atual da região solicitada com a paginação/token existentes e substitui somente as linhas dessa região em uma cópia privada. Conserva as linhas estrangeiras e sua ordem, inclusive sua condição de retrato fornecido pelo chamador. Não atualiza outras regiões nem modifica a entrada original. Se a própria atualização encontra `STALE_WINDOW`, essa tentativa é consumida sem executar o resolvedor e a próxima pode tentar novamente.

Sucesso retorna `OK`. Esgotar tentativas ainda com janela/linhas desatualizadas retorna `EXHAUSTED`, mantendo a última rejeição e `view:null` em `outcome`. `WITNESS_CONTRACT_REJECTED` é terminal: retorna `REJECTED`, sem atualização automática nem repetição. Contratos inválidos de janela continuam falhando explicitamente por exceção; não são tratados como mudanças recuperáveis.

Cada tentativa guarda número, fase (`resolve` ou `refresh`), status, motivo, hash do resultado, hash das linhas usadas, hash das linhas estrangeiras e, quando disponível, token/revisão da atualização. A saída final aceita não apaga a rejeição anterior. Hashes permitem comparar os resultados reproduzidos; não substituem os dados completos disponíveis no probe sem `--summary`.

O orçamento limita tentativas, não garante duração constante ou limite independente do tamanho da janela. Uma tentativa pode ler várias páginas. Não há espera, escrita, geração de linguagem, seleção factual ou promoção de conteúdo repetido a verdade nesse caminho.

## Intervenções nativas

O avaliador aplica escritas entre chamadas, em um handle/thread, para medir o comportamento do leitor. Essas escritas pertencem ao fixture; a função de atualização apenas lê. Não se reivindica segurança de chamadas C simultâneas.

| Caso | Orçamento | Tentativas usadas | Resultado |
| --- | --- | --- | --- |
| janela estável | 1 | 1 | OK |
| linhas já desatualizadas na entrada | 2 | 2 | OK |
| nova consulta local sem vínculo | 2 | 2 | OK |
| nova consulta gerada local | 2 | 2 | OK |
| novo vínculo local fora da consulta | 2 | 2 | OK |
| mudança local com orçamento de uma tentativa | 1 | 1 | EXHAUSTED |
| mudança em toda resolução | 2 | 2 | EXHAUSTED |
| consulta sem vínculo em outra região | 2 | 1 | OK local |
| vínculo à consulta altera totais globais | 2 | 1 | REJECTED |
| mudança também durante a atualização paginada | 3 | 3 | OK |

O último caso usa mais de 64 linhas locais: a primeira resolução é rejeitada; a atualização seguinte lê a primeira página e encontra uma nova escrita antes da segunda; a terceira tentativa atualiza e resolve. O histórico mantém `resolve / REJECTED`, `refresh / REJECTED`, `resolve / OK`, sem resolver sobre páginas incompletas.

Seeds 20261211/20261212: **90/90 controles de integridade PASS em cada seed**. Os dez estados finais, consultados com linhas atualizadas e sem novas intervenções, são aceitos e preservados integralmente após flush, fechamento e reabertura. Os seeds renomeiam o mesmo fixture, não representam amostras independentes de compreensão.

## Limites e validação

As saídas seguem `answer:null`, `qualified:false`, `selected_target:null`, `selection_used:false`, qualidade factual `NOT_EVALUATED`. O sucesso aceita uma visão de relações observadas na fronteira regional verificada; não escolhe uma resposta. Consultas geradas permanecem excluídas do replay estrutural mesmo após a atualização.

O token de 64 bits não é uma trava nem uma prova de ausência de colisões. Uma escrita posterior à verificação final continua possível. `global_snapshot_guaranteed:false` e proveniência estrangeira `caller_supplied_rows` permanecem explícitos. Alterações estrangeiras de vínculos ainda podem invalidar o transporte global; elas não são escondidas por repetição automática. As quatro falhas históricas do critério de janela atual no leitor anterior, o gate pessoal 23/26 e os papéis ocultos 2/4 FAIL permanecem documentados.

Regressões locais: **282 passed, 1 optional BDR skip**. Os oito testes novos passaram, incluindo os dois seeds contra a biblioteca nativa. Resumos e hashes completos foram reproduzidos byte a byte. Compilação Python e `git diff --check` passaram. CI de `2f5cf76`: sete workflows aplicáveis passaram, incluindo trajetória `37575024665`; a regressão experimental condicionada foi pulada.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so python -m unittest discover -s tests -p test_trajectory_bounded_refresh_probe.py
python scripts/trajectory_bounded_refresh_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261211 --summary
python scripts/trajectory_bounded_refresh_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261212 --summary
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. Resumos: `benchmark-results/trajectory-bounded-refresh-{development,reserved}.json`. Motor, runtime nativo, ingestão e seletores anteriores não mudaram; não há integração com OFF.IA. Esta etapa fecha o ensaio de recuperação após rejeição por mudança regional. Próxima investigação: usar a evidência recuperada em ensaios de inferência, medindo escolha, ambiguidade e abstenção contra a baseline anterior, com as falhas históricas visíveis.
