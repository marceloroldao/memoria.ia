# Importação CSV com previsão e confronto automáticos

`scripts/trajectory_forecast_csv.py` automatiza o [laboratório local](trajectory-forecast-lab.md). Em vez de escrever cada comando JSON, o chamador fornece um CSV: o importador registra uma medição, pede a previsão do tick seguinte após o aquecimento e deixa o laboratório confrontar as medições posteriores. O fluxo usa o mesmo BDR e não consulta o simulador ou um LLM.

É um adaptador para o piloto Linux existente. As regras numéricas, a escolha por perdas anteriores e os limites continuam preservados: até **8 medições e 5 previsões por escopo**, com ticks de 0 a 1000 e valores inteiros entre -10000 e 10000. Esta etapa não amplia a escala do histórico nem transforma a baseline em previsão geral.

## Arquivo de entrada

O cabeçalho obrigatório, nessa ordem, é:

```csv
observation_id,entity,tick,value
m0,ab,0,10
m1,ab,1,11
m2,ab,2,12
m3,ab,3,17
```

O arquivo descreve uma entidade de duas letras minúsculas. Os identificadores devem ser únicos, e os ticks devem crescer estritamente. Valores decimais, expoentes, booleanos, campos ausentes, colunas extras ou uma nona medição são recusados. Para registrar conflitos deliberados no mesmo tick, usar a API JSON do laboratório, não este formato de lote.

O separador padrão é vírgula; `--delimiter ';'` aceita ponto e vírgula. UTF-8 com BOM é aceito, e espaços nas células são removidos antes da validação. O BDR recebe a observação numérica normalizada, não uma cópia integral dos bytes do CSV. Conservar o arquivo original quando ele for necessário como fonte documental. `normalized_input_sha256` identifica o conteúdo normalizado, não autentica o sensor ou o arquivo.

## Prévia sem banco

```bash
PYTHONPATH=src python scripts/trajectory_forecast_csv.py \
  --input examples/forecast-lab-measurements.csv --dry-run
```

A prévia valida o arquivo inteiro e devolve o plano de comandos. Não precisa da biblioteca nativa e não abre o diretório de dados. Ela mostra as operações planejadas, não calcula previsões. A compatibilidade com um histórico já armazenado é verificada somente na aplicação.

O arquivo de exemplo contém dados sintéticos. Ele produz oito observações e cinco pedidos de previsão. As duas primeiras linhas ficam em aquecimento; após a oitava medição, o plano informa `PREDICTION_BUDGET_REACHED` em vez de tentar ultrapassar o limite.

## Aplicar e consultar

Com a biblioteca nativa construída conforme o [guia do laboratório](trajectory-forecast-lab.md):

```bash
PYTHONPATH=src python scripts/trajectory_forecast_csv.py \
  --input examples/forecast-lab-measurements.csv \
  --library build/trajectory-native/libmemoria_mobile.so \
  --data-dir "$HOME/.local/share/memoria-forecast-csv-demo"
```

Para dados fornecidos por um coletor, trocar o caminho do arquivo e escolher um diretório persistente separado do exemplo. `--input -` lê de stdin. O escopo padrão é `csv`; `--scope outra_serie` usa uma série independente, cujo nome segue as regras do laboratório. Um escopo novo não transfere automaticamente pontuações de outro.

As respostas são JSON por linha:

| `phase` | Significado |
|---|---|
| `plan` | Prévia completa, sem operações de dados |
| `validation` | Erro antes de iniciar os comandos de observação/previsão desta execução |
| `recovery` | Repetição de um comando anteriormente interrompido |
| `apply` | Resposta a um comando do plano, com o índice da linha de dados |
| `summary` | Contagens finais, limites, pendências e previsões não agendadas |

Cada linha de aplicação inclui a resposta do laboratório, com identificadores, proposta ou abstenção e confronto quando disponível. O resumo não afirma que os valores estão corretos no mundo. Consultas detalhadas continuam disponíveis pela CLI JSON, usando `scope: "csv"` e o mesmo diretório.

## Regra de agendamento

Depois da terceira medição, o alvo automático é sempre `tick_atual + 1`, enquanto existir orçamento de previsões. O importador não usa o tick da próxima linha do arquivo para escolher o alvo. Em um CSV com lacunas, uma previsão pode ficar pendente porque não existe medição do tick previsto. Ao atingir tick 1000, informa `TICK_LIMIT_REACHED`.

O arquivo é lido antes da aplicação para validar todas as linhas. Ainda assim, as funções de previsão recebem apenas o prefixo já persistido no momento de cada comando. Os valores posteriores não são enviados ao ajuste ou ao seletor. Um teste muda as linhas posteriores de dois arquivos válidos e confirma que o primeiro recibo de previsão continua idêntico.

No exemplo completo, a primeira previsão é 13 e a medição posterior é 17: o erro permanece. Após os dados seguintes, o seletor escolhe a regra recente para o tick 7, cuja medição fornecida é 21. Esse é um exemplo controlado, não uma taxa de acerto geral.

## Reaplicar, acrescentar linhas e retomar

Reexecutar o mesmo arquivo e escopo recupera os mesmos identificadores. Os IDs de previsão são derivados deterministicamente de escopo, entidade e alvo; não dependem dos valores futuros. As observações existentes e as hipóteses congeladas não são duplicadas ou reajustadas.

Um CSV pode crescer, por exemplo, de três para quatro linhas e depois até oito, desde que preserve o prefixo já armazenado. A reaplicação reutiliza as operações antigas e acrescenta somente o sufixo novo. Ao atingir os limites, não há rolagem automática para outro escopo.

Antes de aplicar qualquer comando, a compatibilidade exige:

- Todas as observações já presentes devem corresponder exatamente ao prefixo normalizado do arquivo, incluindo ordem e identificadores.
- As previsões existentes devem pertencer ao plano e ter sido congeladas na quantidade de observações prevista para aquela etapa.
- Uma previsão ausente não pode ser criada se medições posteriores à sua etapa já estão armazenadas.
- Históricos incompletos ou alterados devem permitir uma retomada coerente; não se substitui o prefixo para escondê-los.

Assim, um arquivo reduzido, alterado no prefixo ou misturado com previsões manuais incompatíveis é recusado antes de aplicar novos comandos. Se três medições foram gravadas e houve interrupção antes da previsão seguinte, a retomada pode criá-la no prefixo atual. Se outras medições já chegaram, o importador recusa esse preenchimento retroativo. Não há opção de forçar uma previsão antiga com acesso a dados posteriores.

Quando o laboratório informa uma previsão parcial ou vínculos de observação incompletos, o importador localiza o comando original no CSV e o repete em `phase: "recovery"` antes de reaplicar o prefixo. A repetição é testada após reabertura do BDR, sem outra medição ou outro vínculo para a mesma ocorrência.

## Falhas e limites operacionais

O arquivo inteiro passa pela validação sintática antes de abrir o backend. Uma linha inválida no fim não provoca importação silenciosa das anteriores. A compatibilidade do prefixo é uma verificação de leitura antes dos comandos; `data_operations_started=false` significa que nenhum comando de observação/previsão foi iniciado nesta execução, não que o backend nunca tenha criado arquivos internos.

O lote não é uma única transação. Se uma falha ocorrer durante a aplicação, os comandos anteriores já confirmados permanecem válidos. Falhas de execução propagam e encerram o processo com código não zero; não há resumo de sucesso ou alegação de rollback. Reabrir com o mesmo arquivo antes de acrescentar dados por outra ferramenta. O próximo passo é verificar e reparar o estado parcial conhecido, não apagar dados.

O lock consultivo do laboratório fica mantido durante o lote, e o lock reentrante cobre a verificação e a aplicação no mesmo processo. Isso exclui proprietários cooperantes, mas não protege contra ferramentas que ignorem o protocolo. Não há observação contínua de um arquivo em escrita; fornecer um CSV coerente para cada chamada.

As respostas mantêm `qualified=false`, `answer=null` e qualidade factual não avaliada. Fonte falsa ou autocópia ainda podem enganar o confronto. Este adaptador não acrescenta autenticação automática, aprendizado de fontes, novas regras ou alterações no núcleo, ABI móvel e servidor publicado.

## Validação

Foram aprovados **231 testes locais: 35 novos e 196 anteriores**. Os testes cobrem formatos, prévia sem backend, delimitadores, aquecimento, orçamento, gaps de tick, prefixo incompatível, arquivo crescente, recusa de previsões retroativas, retomada de previsão/vínculo parcial, ausência de influência de valores posteriores e CLI real em dois processos.

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
  python -m pytest -q tests/test_trajectory_forecast_csv.py
```

O exemplo reutilizável está em `examples/forecast-lab-measurements.csv`. O CI dedicado reconstrói o runtime com BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a` e executa o importador junto às regressões anteriores.


## Relatório para revisão

Depois da sessão, exporte um [relatório HTML com JSON opcional](trajectory-forecast-report.md). Ele consulta o escopo existente, preserva decisões congeladas e distingue medições declaradas de confrontos efetivamente vinculados. Erros, abstenções, conflitos e operações incompletas ficam visíveis; a exportação não executa recuperação.
