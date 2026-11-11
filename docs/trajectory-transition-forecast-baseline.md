# Extrapolação numérica restrita antes da observação posterior

Continuação experimental: [suspensão e retomada por trecho recente coerente](trajectory-recent-regime-baseline.md). A baseline de histórico completo desta etapa permanece preservada.

Esta etapa retoma a lacuna de previsão de valores inéditos. É uma baseline experimental fora do núcleo cognitivo: o programador fornece a gramática numérica, o modelo de taxa constante e as regras de abstenção. A taxa é calculada das observações anteriores. Não é descoberta geral de operadores, trajetórias causais ou linguagem natural.

O [registro de recusas autenticadas](trajectory-observer-rejection-proof.md) continua preservado. Este experimento usa o journal genérico de hipóteses; não integra automaticamente HMAC, política de atraso ou registro de recusas. As medições são declarações de fonte e o vínculo posterior é explícito, sob responsabilidade do chamador.

## Modelo e evidência

A gramática fornecida é `M[ab;2]=137.`: entidade de dois símbolos, tick inteiro declarado e valor inteiro. O domínio desta implementação é tick de 0 a 1000 e valor entre -10000 e 10000. A consulta formal é `Next[ab;3]?`.

`fit()` recebe somente linhas observadas, região, entidade e tick alvo. Filtra `user_turn`/`user_assertion` da região e entidade solicitadas. Exige ao menos três ticks distintos e não decrescentes na ordem de ingestão, sem valores conflitantes no mesmo tick. Um ponto repetido conserva seus endereços, mas não conta como um novo tick de suporte.

Para cada par de pontos sucessivos, calcula exatamente com `Fraction`:

\[
 r_i = \frac{v_{i+1}-v_i}{t_{i+1}-t_i}.
\]

Se todas as taxas observadas são iguais, propõe:

\[
 \widehat v(t_*) = v_n + r\,(t_*-t_n),\qquad t_*>t_n.
\]

O modelo se abstém diante de evidência insuficiente, taxas discordantes, conflito, ticks não monotônicos, medição malformada da entidade alvo, alvo não posterior ou resultado fora da representação inteira limitada. Não ajusta um modelo alternativo para contornar uma falha.

Uma série constante pode produzir um payload novo por incluir outro tick, mas seu valor já era conhecido. Por isso o relatório separa a novidade do texto de `predicted_value_not_observed_for_entity`. Essa novidade é relativa às medições elegíveis da entidade no prefixo, não a todo conteúdo existente no sistema.

## Congelamento e confronto

`freeze()` conserva a saída completa da baseline, inclusive abstenção, parâmetros e endereços de suporte, em `observation_context` do recibo nativo. A consulta e o prefixo de memória também ficam registrados pela auditoria anterior. A hipótese não é inserida como medição na região principal. A repetição de um identificador recupera o mesmo modelo congelado, mesmo após novas observações; não o ajusta retrospectivamente.

Só depois do congelamento, o experimento solicita uma medição posterior ao processo `transition_measurement_world.py`. Esse trabalhador recebe semente, entidade, tick e lei do mundo sintético, sem candidatas, caminho do BDR ou modelo previsto. `fit()` não recebe a semente, a lei ou o valor posterior e não chama o trabalhador.

A ingestão posterior é explícita. `link_measurement()` exige uma ocorrência da entidade e do tick alvo e delega à auditoria a verificação de papel da fonte e ordem lógica de ingestão. Uma nova medição sem vínculo mantém a hipótese pendente. Uma tentativa de desvio pela API genérica com entidade/tick errados não conta como evidência válida para esta comparação.

`compare()` reconstrói o modelo a partir do prefixo congelado, verifica a história nativa e confronta textos exatos. Não corrige parâmetros nem altera memória. Seus estados incluem `PENDING`, `ABSTAINED_BEFORE_OBSERVATION`, `MATCHES_PROPOSED_TRANSITION`, `DIFFERS_FROM_PROPOSED_TRANSITION`, `DIVERGENT_LATER_MEASUREMENTS` e `UNVERIFIABLE_HISTORY`.

A saída mantém `answer=null`, `qualified=false`, `learning_applied=false` e `provenance_independence=NOT_ESTABLISHED`. Aqui `learning_applied=false` significa ausência de atualização adicional do estado cognitivo pelo confronto; a taxa da baseline foi ajustada por cálculo sobre dados anteriores. A ingestão normal da observação conserva seus efeitos anteriores.

## Resultados e falhas preservados

| Mundo ou controle | Resultado |
|---|---|
| Crescimento linear | Propõe valor novo e coincide com a medição posterior |
| Queda linear | Propõe valor novo e coincide com a medição posterior |
| Valor constante | Coincide, mas o valor já estava observado |
| Quebra oculta depois do prefixo linear | Propõe o mesmo futuro do crescimento linear e erra |
| Aceleração já visível | Abstém-se por taxas observadas discordantes |
| Apenas dois ticks distintos | Abstém-se |
| Um ponto repetido três vezes | Abstém-se; repetição não cria suporte temporal distinto |
| Valores conflitantes no mesmo tick | Abstém-se |
| Exemplos gerados ou de outra região | Não fornecem suporte |
| Medição posterior não vinculada | Continua pendente |
| Cópia da hipótese gravada pelo chamador como observação | Produz coincidência, embora o mundo sintético posterior discorde |

Os mundos de crescimento linear e quebra oculta têm exatamente as mesmas linhas anteriores e geram exatamente o mesmo modelo congelado, mas têm valores posteriores diferentes. A falha é conservada: três pontos com taxa constante não determinam a lei futura.

Nas quatro leis com proposta pontuadas explicitamente — crescimento, queda, constante e quebra oculta — houve **3 coincidências e 1 erro por semente**. Entre as três propostas de valor novo nesse grupo, houve duas coincidências e um erro. O caso de autocópia fica fora dessa contagem e é apresentado separadamente como confirmação enganosa. Aceleração, ausência de suporte e pendência também ficam fora do denominador.

Esses quatro cenários escolhidos não estimam uma precisão geral ou probabilidade de sucesso. As duas sementes apenas variam entidade e nível numérico no mesmo desenho sintético; não constituem validação cega de uma arquitetura geral. O ajuste de taxa constante é uma hipótese matemática fornecida pelo programador.

## Verificação reproduzível

- 126 testes locais aprovados: 30 novos e 96 anteriores.
- Sementes `20270127` e `20270128`: 110/110 verificações de integridade por semente. Esses números não são acertos de previsão.
- Modelo completo, medições, journal e confronto reproduzidos em dois processos sucessivos.
- Cobertos taxas positivas/negativas/nulas/racionais, dados conflitantes, duplicação, limites, abstenção, escopo, leitura sem observador, vínculo incorreto, desvio pela auditoria genérica e preservação do prefixo.
- Os dois relatórios anteriores do registro de recusas foram reproduzidos byte por byte.

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
  python -m pytest -q tests/test_trajectory_transition_forecast_probe.py \
  tests/test_trajectory_observer_rejection_probe.py tests/test_trajectory_observer_freshness_probe.py \
  tests/test_trajectory_authenticated_observer_probe.py \
  tests/test_trajectory_controlled_observer_probe.py tests/test_trajectory_prediction_audit.py
PYTHONPATH=src python scripts/trajectory_transition_forecast_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so --seed 20270127 \
  --output /tmp/transition-forecast-development.json.gz
```

Repetir com `20270128` para a amostra reservada. Relatórios completos em `benchmark-results/trajectory-transition-forecast-{development,reserved}.json.gz`, com linhas anteriores, hipóteses congeladas, resultados posteriores, confronto, avaliação e falhas. O CI dedicado reconstrói o runtime com BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a` e compara integralmente os relatórios descomprimidos.

O núcleo, ABI móvel, MVP e console não foram alterados. Esta baseline fornece um experimento auditável de extrapolação aritmética, não uma função geral de previsão do produto. Descoberta de operadores, seleção entre modelos, adaptação após erro, autenticação das medições e inferência causal continuam lacunas separadas.
