# Escopo experimental por trecho transportado na origem

## Resultado e limite

Nova opção `transported_source_scope=True` em `contextual_route_hypothesis`, **desativada por padrão**. A pré-verificação local dos mesmos registros fictícios da ponte melhora de 18/32 para 24/32 critérios, e respostas corretas de 2/16 para 8/16. Mantém 12/12 abstenções de ausência e 4/4 conflitos, sem resposta diferente do alvo esperado nessa bateria. Qualidade geral continua **FAIL**, pois oito critérios ainda falham.

| Fixture | Padrão | Opção experimental |
|---|---:|---:|
| Capturas isoladas | 2/8 | 2/8 |
| Pares ordenados | 2/8 | 8/8 |
| Pares com conflito | 6/8 | 6/8 |
| Barreira do assistente | 8/8 | 8/8 |

A opção recupera as respostas dos pares ordenados sem modificar `GenerationResult`, sua seleção padrão, candidatos, pesos, testemunhas ou aprendizado. A consulta sobre o drone ainda expõe o candidato concorrente “eu robô”, mas a hipótese opcional pode deixá-lo fora do seu escopo com as testemunhas correspondentes em `scoped_out_witnesses`. O motivo novo é `TRANSPORTED_SOURCE_SCOPE`. Os fragmentos continuam em `contextual_fragments` e na geração original, inclusive os não contidos na resposta.

## Condição estrutural

Apenas COMBINED_RECALL não truncado com uma única raiz de destino observado pode usar a opção. Para dispensar o suporte próprio de uma origem concorrente, exige um nódulo recuperado que:

- esteja na origem e no destino de cada par que o testemunha;
- esteja ausente da consulta, das pistas completas que sustentam o destino escolhido e desse próprio destino;
- seja um fragmento próprio, diferente do destino completo de qualquer uma das suas testemunhas;
- tenha exatamente o mesmo par origem/destino/captura da evidência deixada fora do escopo.

Um trecho de uma terceira origem não pode autorizar a exclusão de outro par. A origem não pode estar integralmente na consulta nem conter uma pista completa de suporte da resposta. Candidatos externos à resposta precisam estar transportados em todas as suas origens e ter todos os pares cobertos. Destinos completos concorrentes não são descartados.

Além das testemunhas recuperadas, a consolidação experimental audita todos os pares de raízes observados na mesma hierarquia cujos destinos contenham algum fragmento atualmente recuperado. Esses pares precisam de suporte próprio para o destino escolhido ou do discriminador por par. O escopo não depende apenas de a descoberta composicional continuar mostrando uma evidência. Essa auditoria é conservadora: até uma origem distante com um fragmento de destino comum pode bloquear a hipótese. Não há alegação de eficiência ou completude geral.

Não há normalização, palavras-chave, classes de entidade, verdade factual ou limiar de cobertura. O mesmo teste usa Unicode, UTF-8 e renomeação bijetiva dos endereços, com e sem prefixo inédito. São versões correlacionadas dos mesmos controles.

## Falha intermediária preservada

A primeira versão do discriminador mantinha o controle de dois pares `Código de Daro?` → `Daro: 791.` e `código de daro?` → `Daro: 415.`. Mas acrescentar `Código de Rumo?` → `Rumo: 827.` mudou os fragmentos descobertos: a segunda origem de Daro saiu das testemunhas recuperadas. A proposta consolidou indevidamente em relação ao contrato de suporte próprio. O teste novo falhou e essa versão não foi publicada como implementação final.

A auditoria dos pares de raízes corrigiu esse caso. O teste mantém tanto a configuração original de dois pares quanto a de três pares, exigindo abstenção em ambas. Isso não reclassifica a resposta de Daro como verdadeira ou falsa; conserva o impedimento de consolidação definido no contrato anterior.

## Verificação

Seis testes novos passaram localmente: recuperação dos pares ordenados com adaptadores/renomeação/prefixo; suporte próprio com e sem terceira origem; discriminador presente na consulta; truncamento; destino concorrente completo transportado; execução dos **18 contratos anteriores também com a opção habilitada**. Os 59 testes do gerador passaram.

O lote padrão 20261013 permaneceu PASS 150/150 e seu JSON completo coincide exatamente com o relatório anterior. O diagnóstico histórico da política rejeitada também produz exatamente o mesmo relatório completo. Logo, essa nova opção não reescreve os resultados da política padrão nem apaga a rejeição anterior.

`python scripts/trajectory_transported_scope_probe.py` usa os registros fictícios e compara a política padrão com o relatório nativo frio anterior. Verifica geração completa inalterada, estado de aprendizado/snapshot intactos e igualdade depois de restaurar a memória. `--library <libmemoria_mobile.so>` adiciona observação pela ABI, leitura de janelas, reabertura do BDR, proveniência e igualdade exata dos 32 casos experimentais com a pré-verificação. `--strict-quality` deve retornar 1 enquanto 24/32 continuar FAIL.

O novo passo nativo de CI compila o runtime inalterado com BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. A inferência experimental acontece somente na memória Python construída para a comparação; não entra no runtime nativo ou OFF.IA. O gate nativo original continua 23/26 e a ponte padrão continua 18/32. PR draft.

Pendências: capturas isoladas não ensinam a relação temporal; no fixture com conflito, a pergunta do outro sujeito ainda se abstém, pois os fragmentos concorrentes ali recuperados não satisfazem a condição transportada. Não removemos esses casos do avaliador.

## Validação concluída

[Workflow 36805425261](https://github.com/marceloroldao/memoria.ia/actions/runs/36805425261) passou no commit `3a1fb1abe59ca474c93794a3a2e19429275c92ef`: seis testes novos (incluindo os 18 contratos habilitados), 18 testes padrão da hipótese, 59 do gerador e 66 regressões (um BDR opcional pulado), além dos controles anteriores. Os cinco lotes padrão de variações preservaram PASS 150/150. O diagnóstico histórico continua REJECTED. Todos os outros workflows aplicáveis passaram; experimental PR regression foi pulado por sua condição existente.

O job nativo confirmou a opção experimental **FAIL 24/32**, respostas 8/16, ausência 12/12, conflitos 4/4 e zero hipóteses diferentes do alvo esperado na bateria. O relatório coincide exatamente com a pré-verificação em todos os campos comuns, incluindo os casos e diagnósticos; a avaliação nativa adicional confirmou ordem, endereços e reabertura. A ponte padrão permaneceu **FAIL 18/32**. Relatório completo dos logs em `benchmark-results/trajectory-transported-scope-report.json`.

Após fixar implementação e seis contratos, executamos localmente um novo lote de variações, seed `20261014`, com a opção habilitada: **PASS 150/150**, respostas 54/54 e zero hipóteses indevidas. Não foi executado no CI nem pela ABI nativa. Seu relatório preserva todos os casos e explicita a revisão experimental em `benchmark-results/trajectory-transported-scope-reserved.json`; os controles opacos e adaptadores seguem correlacionados. A flag estrita do novo diagnóstico foi executada localmente e retornou 1, corretamente, diante de qualidade FAIL 24/32.

O avanço está limitado à opção explícita em Python. A política padrão e as três falhas nativas continuam pendentes; não há ativação no OFF.IA nem declaração de verdade factual.
