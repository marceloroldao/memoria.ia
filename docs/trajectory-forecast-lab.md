# Fluxo local de observações, previsão e confronto

O piloto `scripts/trajectory_forecast_lab.py` coloca as baselines numéricas em um processo local com entrada e saída JSON por linha. Ele recebe medições fornecidas pelo chamador, congela previsões e confronta automaticamente a medição posterior com as duas regras candidatas e com o seletor. Não solicita valores ao simulador dos testes.

O objetivo é permitir conectar um produtor de dados ao fluxo, preservando o BDR e os recibos, em vez de chamar manualmente cada função experimental. É uma CLI para Linux com limites pequenos e explícitos. As regras continuam sendo as baselines aritméticas fornecidas pelo programador, descritas em [escolha por desempenho anterior](trajectory-rule-selection-baseline.md).

## Iniciar

Com o runtime nativo já construído:

```bash
PYTHONPATH=src python scripts/trajectory_forecast_lab.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --data-dir "$HOME/.local/share/memoria-forecast-lab"
```

O diretório escolhido deve persistir entre execuções. O backend fica no subdiretório `native`, usando BDR. Reiniciar o comando com o mesmo diretório recupera observações, hipóteses, vínculos e pontuações. Não precisa carregar um LLM.

Se for necessário construir a biblioteca, usar a configuração já validada no CI, com `deps/resolutive-DB` no commit `317882a00f041fc1568ff986af8016b09453f21a`:

```bash
cmake -S native/mobile -B build/trajectory-native -DCMAKE_BUILD_TYPE=Release \
  -DMEMORIA_BDR_ROOT="$PWD/deps/resolutive-DB"
cmake --build build/trajectory-native --target memoria_mobile --parallel 2
```

A sessão pronta em `examples/forecast-lab-session.jsonl` usa dados sintéticos identificados como exemplo. Para executá-la inteira, usar um diretório separado dos dados reais:

```bash
PYTHONPATH=src python scripts/trajectory_forecast_lab.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --data-dir "$HOME/.local/share/memoria-forecast-lab-demo" \
  < examples/forecast-lab-session.jsonl
```

Cada linha produz uma resposta JSON. Um produtor pode escrever os mesmos comandos em stdin e consumir stdout. A integração com um sensor, coletor ou OFF.IA exige um adaptador desse produtor; esta mudança não instala um aplicativo móvel ou serviço remoto.

## Comandos

| Operação | Campos específicos | Comportamento |
|---|---|---|
| `observe` | `observation_id`, `entity`, `tick`, `value` | Persiste uma medição declarada e vincula automaticamente todas as previsões registradas para essa entidade/tick |
| `predict` | `prediction_id`, `entity`, `target_tick` | Congela as duas candidatas e a escolha do seletor antes da medição alvo |
| `prediction` | `prediction_id` | Consulta a proposta congelada, decisão, pontuações e confronto; somente leitura |
| `history` | Nenhum | Devolve medições, journal completo, resumos e pendências de recuperação; somente leitura |
| `status` | Nenhum | Mostra contagens, limites e identificadores que exigem retomada; somente leitura |

Todas as operações aceitam `scope`, que vale `principal` por padrão. Escopos são séries independentes; não compartilham pontuações ou continuidade de treinamento. Seus nomes usam até 32 letras ASCII, dígitos, underscores ou hífens. Identificadores de observação e previsão usam até 40 desses caracteres.

Exemplo de entrada:

```json
{"op":"observe","observation_id":"m0","entity":"ab","tick":0,"value":10}
{"op":"observe","observation_id":"m1","entity":"ab","tick":1,"value":11}
{"op":"observe","observation_id":"m2","entity":"ab","tick":2,"value":12}
{"op":"predict","prediction_id":"p3","entity":"ab","target_tick":3}
{"op":"observe","observation_id":"m3","entity":"ab","tick":3,"value":17}
{"op":"prediction","prediction_id":"p3"}
```

A proposta inicial será 13 e a medição posterior 17 produzirá `DIFFERS_FROM_SELECTED_PROPOSAL`. O erro permanece. A sessão completa continua até o tick 7: após observar a recuperação da regra recente, o seletor a escolhe para a próxima previsão, que coincide com 21 no exemplo.

## Contrato numérico e limites do piloto

- Entidade: exatamente duas letras minúsculas ASCII, como `ab`.
- Tick declarado: inteiro de 0 a 1000, sem relógio físico implícito.
- Valor: inteiro entre -10000 e 10000; booleanos e decimais são recusados.
- Até **8 observações e 5 pedidos de previsão por escopo**.
- Novos ticks observados não podem diminuir para a mesma entidade. Repetição exata de uma observação antiga permanece permitida.
- Um novo alvo de previsão deve estar depois do último tick observado da entidade. Só existe um pedido por entidade/tick; repetir o alvo exige o identificador original.

Os limites mantêm os leitores combinatórios e os metadados congelados dentro de uma janela pequena. Ao atingir o limite, consultas e repetições exatas continuam disponíveis. Outro escopo começa um histórico independente; não há rolagem automática, retenção ou continuidade entre janelas. Esta versão não valida operação contínua de longa duração ou escalabilidade de produção.

Valores distintos declarados para o mesmo tick são preservados como conflito, com identificadores distintos. Um payload idêntico com outro identificador é recusado para evitar duplicação. Nada escolhe automaticamente qual medição conflitante é verdadeira.

## Persistência e repetição

`observe` usa o identificador para recuperar a mesma ocorrência. Repeti-lo com o mesmo conteúdo retorna `EXACT_REPLAY`; reutilizá-lo com outro conteúdo é erro. Os três vínculos de confronto usam identificadores determinísticos e não duplicam a medição ao serem repetidos.

`predict` registra três hipóteses: histórico completo, trecho recente e seletor. Repetir o mesmo pedido retorna sua decisão original, mesmo depois de chegar o resultado. Não reajusta a previsão retrospectivamente. Os dados fornecidos entram em uma região própria `forecast-lab:<scope>`, enquanto as hipóteses ficam no journal de auditoria separado.

A sessão de exemplo é testada em um processo real de CLI e consultada novamente em outro processo. O primeiro erro, a escolha final e as contagens são recuperados integralmente.

## Falhas parciais e retomada

As etapas são persistentes, mas não compõem uma única transação. O processo usa o mesmo lock consultivo do laboratório local anterior, para excluir outros proprietários cooperantes do mesmo diretório. Esse lock não protege contra ferramentas externas que ignorem o protocolo.

Se uma falha ocorrer após possível escrita, a CLI termina com erro de execução, sem enviar uma resposta `ok:false` que pudesse sugerir ausência de escrita. Reabrir com o mesmo diretório e consultar `status`:

- `repair_prediction_ids`: repetir `predict` com o mesmo identificador e alvo para concluir as etapas ausentes.
- `repair_observation_ids`: repetir `observe` com o mesmo identificador e conteúdo para concluir os vínculos ausentes.

Outras gravações ficam bloqueadas enquanto essa retomada estiver pendente. As consultas continuam disponíveis. Quando a previsão incompleta é concluída, a resposta usa `COMPLETED_RETRY`; se já estava completa, usa `EXACT_REPLAY`. Uma observação cujo conteúdo já foi gravado usa `EXACT_REPLAY` mesmo quando a repetição termina vínculos que faltavam.

Os testes injetam falhas antes de uma etapa, depois de gravar o seletor e durante os vínculos. Demonstram recuperação das operações parciais testadas, não recuperação arbitrária de um armazenamento corrompido. Alterações externas que invalidem o prefixo histórico bloqueiam novas gravações; o piloto não reescreve a memória para esconder a falha.

Erros de validação de comandos são devolvidos por linha e o processo continua. Falhas de armazenamento ou falhas internas após possível mutação interrompem o processamento; comandos seguintes no mesmo stdin não são confirmados. O cliente deve reabrir e repetir o identificador original.

## Validação e limites de interpretação

Foram aprovados 25 testes novos do laboratório e os 171 testes anteriores, totalizando 196 testes locais. A cobertura inclui ciclo completo, CLI real entre processos, repetição sem duplicação, leituras sem escrita, isolamento, conflitos, campos inválidos, limites com identificadores máximos, lock e recuperação de previsões/vínculos parciais. Um teste faz a função de medição do simulador lançar uma exceção e comprova que o fluxo recebe apenas os valores fornecidos.

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
  python -m pytest -q tests/test_trajectory_forecast_lab.py
```

A resposta mantém `answer=null`, `qualified=false` e `factual_quality_status=NOT_EVALUATED`. A CLI torna o fluxo operacional, mas não autentica os sensores, não aprende a veracidade das medições e não aplica automaticamente os contratos opcionais de HMAC/freshness. Uma fonte que copie a hipótese pode produzir coincidência enganosa. O núcleo cognitivo, ABI móvel e servidor publicado permanecem preservados.
