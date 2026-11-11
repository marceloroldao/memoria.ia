# Suspensão e retomada por trecho recente coerente

Continuação da [baseline de extrapolação numérica](trajectory-transition-forecast-baseline.md). Este experimento compara o modelo de histórico completo com uma regra programada que usa o sufixo mais recente de taxa constante. Ambos continuam fora do núcleo cognitivo e não descobrem operadores ou políticas de aprendizagem.

A adaptação demonstrada é uma nova seleção de observações para calcular outra hipótese. Não é aprendizado geral a partir da classificação de um erro: o algoritmo não recebe acerto/erro do avaliador, verdade do mundo, lei do simulador ou rótulo de mudança de regime. Ele pode mudar de hipótese mesmo que a medição anterior ainda não tenha sido vinculada à previsão.

## Regra explícita

`fit()` começa pela validação da baseline anterior. Mantém as mesmas restrições de gramática, entidade, região, papel da fonte, limites numéricos e ordem dos ticks. Dados gerados ou estrangeiros não fornecem suporte. Repetir o mesmo ponto conserva endereços, mas não cria outro tick distinto.

Quando todas as taxas observadas são iguais, usa o histórico inteiro. Quando elas discordam, calcula a taxa do último intervalo e estende o trecho ativo para trás enquanto as taxas sucessivas forem exatamente iguais. A política é fixa e registrada na hipótese:

```json
{"selection":"LATEST_EQUAL_RATE_SUFFIX","minimum_distinct_ticks":3}
```

Se esse sufixo contém menos de três ticks distintos, a saída é `SUSPENDED_PENDING_STABLE_SUFFIX`, sem proposta. Com suporte suficiente, reaplica a extrapolação aritmética anterior somente ao trecho ativo. A saída conserva todos os pontos históricos, os endereços de suporte, o tick inicial do trecho ativo e a quantidade de pontos anteriores excluídos do ajuste atual. Nada é removido da memória.

Conflitos de valores no mesmo tick, ticks não monotônicos, dados alvo malformados e limites de representação não são escondidos por essa seleção. Um conflito antigo pode manter a abstenção mesmo que exista um trecho recente aparentemente coerente. O critério usa igualdade racional exata: não implementa tolerância a ruído de um sensor real.

A novidade de um valor proposto continua sendo avaliada contra todos os pontos históricos elegíveis da entidade, e não apenas contra o trecho ativo. Reencontrar um valor antigo não o torna inédito por ter ficado fora do ajuste recente.

## Comparação temporal sem apagar o primeiro erro

Em cada tick de 3 a 6, o experimento congela duas hipóteses separadas sobre as mesmas observações: uma de histórico completo e outra de trecho recente. Só depois solicita a medição posterior ao trabalhador independente já utilizado na etapa anterior.

Exemplo de valores: `10, 11, 12, 17, 18, 19, 20`.

| Alvo | Histórico disponível antes da medição | Histórico completo | Trecho recente |
|---|---|---|---|
| Tick 3 | 10, 11, 12 | Propõe 13 e erra | Propõe 13 e erra |
| Tick 4 | 10, 11, 12, 17 | Abstém-se | Suspende; último trecho tem dois pontos |
| Tick 5 | 10, 11, 12, 17, 18 | Abstém-se | Suspende; novo trecho tem dois pontos |
| Tick 6 | 10, 11, 12, 17, 18, 19 | Abstém-se | Usa 17, 18, 19; propõe 20 e coincide |

O salto não foi previsto. A primeira hipótese continua registrada com sua proposta original e seu erro. Cada alvo recebe outro identificador e outro prefixo congelado. Repetir um identificador anterior nunca o ajusta com dados que chegaram depois.

No cenário de quebra oculta, em cada uma das duas sementes:

| Baseline | Coincidências com o mundo | Erros | Abstenções |
|---|---:|---:|---:|
| Histórico completo | 0 | 1 | 3 |
| Trecho recente | 1 | 1 | 2 |

São quatro alvos escolhidos em um mundo sintético, não uma estimativa de precisão geral. A vantagem medida é retomar uma proposta depois da quebra quando os dados recentes sustentam a regra programada. A regra não prova estabilidade futura nem identifica a causa da mudança.

## Controles negativos preservados

| Controle | Resultado |
|---|---|
| Série linear estável | As duas regras continuam produzindo propostas compatíveis com o mundo |
| Aceleração com taxas sempre diferentes | As duas se abstêm |
| Trecho final curto e instável | A regra recente suspende; não procura um trecho antigo favorável |
| Pontos gerados após a quebra | Não completam o suporte necessário para retomar |
| Valores falsos no trecho recente | Podem criar um regime aparente e levar a nova previsão errada |
| Autocópia da hipótese como medição | Pode manter coincidências com entradas fornecidas enquanto todas discordam do mundo |

No controle de dados falsos, o chamador altera as medições dos ticks 3, 4 e 5; a extrapolação recente do tick 6 discorda do mundo. Uma medição falsa também pode fazer parecer que a primeira previsão estava errada quando ela correspondia ao mundo real do simulador. Os relatórios distinguem confronto com o conteúdo fornecido e concordância posterior com o mundo conhecido pelo avaliador.

O controle de autocópia usa um mundo com quebra oculta, mas injeta as próprias propostas como `user_turn`. A comparação produz coincidência em todos os quatro alvos e a avaliação do mundo produz discordância em todos eles. Esse resultado não entra na contagem do cenário de quebra com observações genuínas.

Esta etapa usa medições declaradas e vínculo explícito. Não integra automaticamente HMAC ou a política de atraso. Mesmo uma fonte autenticada poderia fornecer valores incorretos; qualidade de fonte e correção causal não são aprendidas aqui.

## Persistência, separação e verificação

As hipóteses completas ficam em `observation_context` do journal de auditoria. As medições posteriores entram somente pela ingestão explícita. O confronto reconstrói o ajuste no prefixo congelado, verifica a história e compara os valores representados como texto. Nenhuma proposta é inserida automaticamente como fato ou medição.

Os campos `answer=null`, `qualified=false`, `learning_applied=false` e `provenance_independence=NOT_ESTABLISHED` são mantidos. O parâmetro da baseline é recalculado em novas hipóteses; `learning_applied=false` indica ausência de atualização adicional do estado cognitivo pelo ajuste/comparação. A ingestão normal conserva seus efeitos anteriores.

- 149 testes locais aprovados: 23 novos e 126 anteriores.
- Sementes `20270129` e `20270130`: 204/204 verificações de integridade por semente, separadas dos acertos preditivos.
- Erro original, hipóteses suspensas, retomada, medições e journal reproduzidos em dois processos sucessivos.
- Cobertos taxas recentes positivas, negativas, nulas e racionais; histórico inválido; repetição; escopo; novidade; limites; ausência de rótulos de erro; vínculo incorreto e preservação do primeiro erro.
- Os dois relatórios anteriores de extrapolação foram reproduzidos byte por byte.

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
  python -m pytest -q tests/test_trajectory_recent_regime_probe.py \
  tests/test_trajectory_transition_forecast_probe.py tests/test_trajectory_observer_rejection_probe.py \
  tests/test_trajectory_observer_freshness_probe.py tests/test_trajectory_authenticated_observer_probe.py \
  tests/test_trajectory_controlled_observer_probe.py tests/test_trajectory_prediction_audit.py
PYTHONPATH=src python scripts/trajectory_recent_regime_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so --seed 20270129 \
  --output /tmp/recent-regime-development.json.gz
```

Repetir com `20270130` para a amostra reservada. Relatórios completos em `benchmark-results/trajectory-recent-regime-{development,reserved}.json.gz`, com hipóteses das duas baselines em cada tick, entradas fornecidas, medições genuínas do mundo, avaliação e controles. As sementes variam entidade e nível numérico no mesmo desenho; não representam avaliação cega.

O CI dedicado reconstrói o runtime com BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a` e compara integralmente os relatórios descomprimidos. O recibo de modelo mantém o limite de 4096 caracteres da auditoria anterior: esta prova não valida escalabilidade de históricos longos. Há um escritor e nenhuma transação conjunta entre todas as operações.

Núcleo, ABI móvel, MVP e console permanecem preservados. Descoberta de modelos, seleção de políticas aprendida, ruído, confiança nas fontes, previsão da primeira quebra e aprendizado geral continuam lacunas separadas.
