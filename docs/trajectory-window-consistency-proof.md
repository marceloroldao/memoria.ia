# Janela regional sob intervenções entre chamadas

Continuação de `5205b8b`. Seus sete workflows aplicáveis passaram, incluindo trajetória `37554455794`; a regressão experimental condicionada foi pulada. Este incremento acrescenta uma guarda experimental opt-in, um probe com escrita controlada, oito testes e um passo de CI. O PR #374 permanece em rascunho.

## Limite reproduzido no leitor anterior

O transporte paginado nativo de testemunhas não fornece token de snapshot. Mudanças de totais são detectadas pelo coletor anterior, mas uma nova ocorrência sem vínculo não altera esses totais. A enumeração de episódios usa as linhas fornecidas pelo chamador; sem uma verificação adicional, ela pode continuar apresentando coerentemente esse retrato anterior mesmo depois de a janela nativa mudar.

O experimento executa a intervenção depois de uma resposta nativa e antes da chamada seguinte, no mesmo handle e na mesma thread. Não simula acesso simultâneo inseguro à biblioteca C. Dois bancos independentes, com a mesma entrada e intervenção, comparam o caminho anterior e o novo caminho guardado. Nomes dos casos e resultados esperados ficam no avaliador, sem entrar no aprendizado.

Os vínculos nativos existentes são imutáveis: reaplicar o mesmo vínculo é idempotente e tentar trocar seu alvo é rejeitado. Por isso, os casos reais acrescentam observações ou vínculos antes ausentes, em vez de fingir uma substituição que a API não permite.

## Guarda da região solicitada

`resolve_guarded_region` primeiro valida os argumentos e lê a janela regional completa. A primeira página captura `window_token`; as seguintes usam o `expected_token` existente. Também confere offsets, contagem, revisão, endereços duplicados e cobertura das páginas.

Compara as linhas locais do chamador com texto, tipo de fonte, endereço e `reply_to` da janela atual. Linhas diferentes produzem `REJECTED / STALE_INPUT_ROWS` antes de qualquer pedido de testemunhas. Se coincidem, chama o resolvedor paginado anterior e verifica novamente o token regional depois do transporte. Uma mudança produz `REJECTED / STALE_REGIONAL_WINDOW`, com `view:null`. Uma falha do contrato de testemunhas produz `WITNESS_CONTRACT_REJECTED`, igualmente sem visão parcial. Não há repetição automática nem escolha de resposta.

O sucesso declara `REGIONAL_TOKEN_UNCHANGED`, o token, a revisão e a fronteira verificada. Isso cobre somente a região solicitada durante essas chamadas. Proveniência estrangeira continua identificada como `caller_supplied_rows`; `global_snapshot_guaranteed` permanece false. Sem alvo local bruto exato, não há consulta nativa de testemunhas, embora a janela regional seja verificada.

## Resultados nativos

| Intervenção após resposta de testemunhas | Cabeçalhos globais | Token local | Leitor anterior | Guarda |
| --- | --- | --- | --- | --- |
| nenhuma | iguais | igual | aceita | aceita |
| pergunta local sem vínculo | iguais | muda | aceita retrato anterior | rejeita token |
| consulta gerada local | iguais | muda | aceita retrato anterior | rejeita token |
| vínculo local a texto fora da consulta | iguais | muda | aceita retrato anterior | rejeita token |
| novo vínculo local à consulta | mudam | muda | rejeita cabeçalhos | rejeita contrato |
| pergunta sem vínculo em outra região | iguais | igual | aceita | aceita escopo local |
| novo vínculo à consulta em outra região | mudam | igual | rejeita cabeçalhos | rejeita contrato |
| pergunta local após a última página | iguais | muda | aceita retrato anterior | rejeita token |

Seeds 20261209/20261210: **72/72 controles de integridade PASS em cada seed**. Os relatórios preservam **quatro FAILs do critério de janela atual no caminho anterior**, em cada seed. Isso não reclassifica seus controles anteriores nem mede qualidade factual. A pergunta local nova aumenta a enumeração de dois para três alvos; o texto gerado e o vínculo fora da consulta não alteram os alvos, mas invalidam conservadoramente a janela completa.

Depois de atualizar explicitamente as linhas, a guarda aceita o estado final de todos os oito casos. Flush, fechamento e reabertura conservam as linhas e a saída guardada completa. Os dados fornecidos pelo chamador não são modificados. Os dois seeds renomeiam o mesmo fixture, sem representar amostras independentes de compreensão.

## Limites e validação

O token nativo é um fingerprint de 64 bits, não uma trava ou prova matemática de ausência de colisões. A verificação final não impede uma escrita posterior. O transporte continua global: um vínculo novo estrangeiro pode causar rejeição de cabeçalhos mesmo sem mudar a região local. Não se reivindica snapshot global, atomicidade sob escritores arbitrários ou segurança de chamadas C simultâneas.

As saídas continuam sem resposta ou alvo selecionado, com `qualified:false` e qualidade factual `NOT_EVALUATED`. As rejeições mantêm `answer:null`, `view:null`. Os limites históricos, incluindo gate pessoal 23/26 e papéis ocultos 2/4 FAIL, permanecem. Motor, runtime nativo, ingestão e seletores anteriores não foram alterados; não há integração com OFF.IA.

Regressões locais: **274 passed, 1 optional BDR skip**. Os oito testes novos passaram, incluindo os dois seeds contra a biblioteca nativa. Resumos e hashes completos foram reproduzidos byte a byte. Compilação Python e `git diff --check` passaram. CI de `f6e349d`: sete workflows aplicáveis passaram, incluindo trajetória `37559701392`; a regressão experimental condicionada foi pulada.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so python -m unittest discover -s tests -p test_trajectory_window_consistency_probe.py
python scripts/trajectory_window_consistency_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261209 --summary
python scripts/trajectory_window_consistency_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261210 --summary
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. Resumos: `benchmark-results/trajectory-window-consistency-{development,reserved}.json`; sem `--summary`, o probe inclui as visões e rejeições completas. Próxima investigação: atualizar as linhas e repetir uma leitura rejeitada com orçamento explícito, sem esconder a intervenção ou promover estabilidade regional a verdade factual.
