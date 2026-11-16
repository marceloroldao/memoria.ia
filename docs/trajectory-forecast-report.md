# Relatório estático do laboratório de previsões

O exportador consulta um escopo existente do [laboratório local](trajectory-forecast-lab.md) e produz HTML portátil, com JSON opcional. É uma ferramenta experimental de revisão: preserva medições declaradas, previsões congeladas, erros, abstenções, conflitos e operações incompletas. Não qualifica nenhuma hipótese como fato.

## Uso

Depois de executar uma sessão JSON-lines ou uma [importação CSV](trajectory-forecast-csv.md):

```bash
python scripts/trajectory_forecast_report.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --data-dir /tmp/forecast-lab-csv \
  --scope csv \
  --html /tmp/forecast-exports/relatorio.html \
  --json /tmp/forecast-exports/relatorio.json
```

Abra o HTML em um navegador, inclusive sem conexão. Ele contém CSS e SVG internos, sem JavaScript, fontes remotas, bibliotecas ou chamadas de rede. O layout adapta as contagens para telas pequenas; tabelas largas podem ser roladas horizontalmente. `--title` permite alterar o título. O HTML inclui o snapshot completo; o JSON separado é opcional.

O diretório de dados deve conter um subdiretório `native` existente e não vazio. O comando recusa uma fonte ausente ou vazia antes de abrir o backend, evitando inicializar um BDR por engano. Um escopo vazio em um BDR existente gera um relatório sem pontos inventados.

Os arquivos de saída devem ficar **fora de todo o diretório de dados**, ter extensões HTML/HTM e JSON correspondentes e caminhos distintos. Arquivos existentes e links simbólicos de saída são recusados. Todos os destinos são verificados antes da primeira gravação; as saídas são criadas exclusivamente. Uma falha de I/O ainda pode deixar uma exportação parcial: a dupla HTML/JSON não é uma transação atômica. Escolha novos nomes para exportar novamente.

A saída do comando é JSON com `ok`, `snapshot_id`, contagens, caminhos, `qualified:false` e `native_mutations_requested:false`. Erros de entrada/saída previstos encerram com código 2. Falhas internas do backend também encerram sem declarar sucesso.

## Leitura dos resultados

| Estado | Interpretação |
| --- | --- |
| Coincide com o registro | A hipótese selecionada coincide com a medição posteriormente vinculada. |
| Diverge do registro | A medição vinculada difere da hipótese; o erro continua registrado. |
| Abstenção | O seletor já havia se abstido antes da medição posterior. |
| Pendente de vínculo | Não há confronto concluído para o seletor. |
| Medições conflitantes | Há valores posteriores divergentes; todos são preservados. |
| Histórico não verificável | O prefixo da decisão não pode mais ser reproduzido. |
| Previsão incompleta | A gravação das etapas da previsão foi interrompida. |

O gráfico mostra pontos declarados e apenas hipóteses do **seletor** cujo histórico é verificável. Não interpola trajetórias nem mostra propostas de candidatas não escolhidas como se fossem a decisão. A tabela e os recibos preservam os demais detalhes.

O desvio é `observado − proposto`. Só é calculado quando existe exatamente uma medição vinculada ao seletor, uma proposta e um confronto verificável de coincidência ou divergência. Não é calculado para abstenções, conflitos, pendências ou históricos não verificáveis.

Uma medição bruta com a mesma entidade e tick não estabelece, por si só, um vínculo. Depois de uma interrupção entre as etapas de vinculação, o relatório conserva a medição na seção de observações e sinaliza a pendência; não inventa o confronto e não executa recuperação.

Não há percentual agregado de “precisão”. Contagens separadas evitam misturar propostas, abstenções, conflitos e falhas de integridade. Coincidência com uma declaração, inclusive uma cópia da própria proposta, não prova verdade nem confirmação independente.

## Preservação e limites

A coleta usa o lock do proprietário e somente as operações `history` e `status`. Não chama `observe`, `predict`, simulador ou reparação; não altera observações ou decisões pelo protocolo do laboratório. A abertura e o fechamento do backend podem criar lock ou atualizar metadados/flush. Portanto, a garantia é de preservação **lógica**, não de filesystem fisicamente somente leitura ou de hashes idênticos dos arquivos BDR.

O proprietário nativo é fechado antes de escrever as saídas. O snapshot tem hash determinístico, sem timestamp de exportação; a renderização rejeita alterações no snapshot recebido. Esse hash identifica o conteúdo e detecta alteração acidental, mas não é assinatura nem autenticação da fonte.

Os arquivos exportados contêm valores, endereços, proveniência e journal completos do escopo. Compartilhá-los compartilha esses dados. A exportação é estática: novos registros exigem outro arquivo.

Permanecem os limites do piloto: 8 observações e 5 previsões por escopo, duas regras aritméticas fornecidas e um seletor restrito. Core, ABI móvel e servidor publicado permanecem fora desta mudança.

## Verificação

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_forecast_report.py
```

A integração contínua compila o runtime com BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`, executa os testes do relatório e a regressão do laboratório. Os testes cobrem paridade após reabertura, preservação lógica, erros e abstenções, pontos SVG, vínculos incompletos, conflitos, histórico não verificável, escaping HTML, arquivos existentes e execução real da CLI.

O job `forecast-report` também importa o CSV **sintético** do repositório e disponibiliza HTML/JSON no artefato `forecast-report-example`, com retenção de 7 dias. Nenhum dado pessoal é usado nessa amostra. A verificação de HTML é estrutural; não substitui inspeção visual em navegadores e dispositivos. Nesta etapa, a validação executável ocorre no GitHub Actions porque o executor local está indisponível.
