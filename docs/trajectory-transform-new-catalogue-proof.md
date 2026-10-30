# Novo catálogo: símbolos sem mapa, mapas conflitantes e fronteiras de valor

Esta etapa testa os mecanismos identificados anteriormente com identificadores novos e duas famílias de observações: frequência (`Hz`) e nível (`dB`). Os identificadores são sequências explícitas, como `ABC`, `DAC`, `LM` e `UN`, sem significado fornecido ao leitor. O catálogo foi desenhado depois dos diagnósticos anteriores. É uma replicação estrutural curada, com templates correlacionados, e não uma estimativa independente de precisão de linguagem.

Cada família inclui quatro experimentos e quatro memórias independentes por experimento: baseline, observação irrelevante, demonstração adequada e contraste. São 32 memórias principais com seis consultas cada, mais dois controles de IDs com duas consultas cada: **196 consultas** e **34 memórias independentes**. As demonstrações adicionais não contêm a pergunta-alvo nem o payload-alvo. O motor, os leitores e a política de seleção permanecem iguais.

## Resultado nos dois catálogos

Os resultados abaixo se repetiram em frequência e nível. Cada fração conta os conteúdos de referência recuperados para a consulta principal, não respostas factuais certificadas.

| Experimento | Baseline | Observação irrelevante | Demonstração adequada | Contraste |
|---|---:|---:|---:|---:|
| Símbolo ainda sem mapeamento | 0/1 | 0/1 | 1/1 | 0/1 |
| Par identidade ainda sem testemunho | 0/1 | 0/1 | 1/1 | 0/1 |
| Dois mapas concorrentes, dois destinos observados | 1/2 | 1/2 | 2/2 | 1/2 |
| Fronteira de valor presa à unidade comum | 1/2 | 1/2 | 2/2 | 1/2 |

**Símbolo sem mapa.** A variável da consulta contém um símbolo que não está na moldura. Uma demonstração sobre outra entidade fornece o par exigido, e uma nova moldura passa a cobrir a consulta. O contraste ensina outra saída para esse símbolo; como não há destino observado compatível, a referência continua ausente. Nenhum payload é fabricado.

**Identidade sem testemunho.** O novo símbolo deve permanecer idêntico, como `Z → Z`. O leitor não assume essa identidade automaticamente. Demonstrá-la em outra entidade permite recuperar o destino. Ensinar `Z → z` mantém a perda do destino com `Z` literal. O comportamento se repete com outro símbolo no segundo catálogo.

**Mapas conflitantes.** Já existem dois conteúdos de destino distintos, mas inicialmente só um possui rota aprendida compatível com a pergunta. A intervenção demonstra um segundo mapa, usando as entidades de treinamento. O leitor passa a retornar as duas candidatas com seus testemunhos, preservando `answer=null`, `selected_target=null`, `qualified=false` e `selection_used=false`. A referência neste cenário é o conjunto das duas hipóteses observadas: não há rótulo de qual delas é verdadeira. O contraste repete o primeiro mapa e continua retornando somente sua candidata; repetir observações não cria o segundo mapa.

**Fronteira excessivamente específica.** Os valores de treinamento compartilham uma unidade de medida no final. Um destino observado terminado em `sem leitura.` não é admitido pela moldura inicial. Demonstrar esse outro final em uma entidade nova permite aprender uma fronteira menos restrita e recuperar ambos os destinos. Acrescentar uma nova entidade com valor ainda terminado na mesma unidade não resolve a perda.

O estado inicial recupera 4 dos 12 conteúdos esperados nas oito consultas principais dos dois catálogos. As intervenções adequadas recuperam 12/12 nessas mesmas consultas. Esse número descreve intervenções direcionadas sobre oito cenários construídos; não representa qualidade geral, aprendizagem autônoma ou verdade dos conteúdos.

## Controles e integridade

Os **160 controles negativos** (atributo ausente, entidade sem destino, conteúdo somente gerado, conteúdo estrangeiro e ausência de sobreposição) retornam listas vazias em todos os braços. O controle de `abc` e `ABC` conserva dois conteúdos diferentes e passa **4/4 consultas**. A mesma fixture de IDs é repetida nos dois catálogos, portanto não corresponde a duas amostras independentes.

Passaram **334/334 verificações de integridade**: consulta/repetição sem escrita, proveniência aceita no escopo, ausência de feedback implícito, envelopes sem qualificação, paridade de histórico e leitura após reabertura e paridade entre rastreamento e rota real. A intervenção não fornece respostas de referência como labels ao motor; somente textos de observações e consultas são enviados. Os conjuntos esperados são usados para pontuar depois da recuperação.

Passaram **21 testes locais**, três novos do catálogo e dezoito regressões do rastreador, localização de maiúsculas e transformação original. O relatório completo foi repetido e coincidiu byte a byte. Compilação Python e `git diff --check` passaram.

As baterias anteriores permanecem preservadas. Este incremento acrescenta somente fixtures, avaliação, rastreamento já existente, relatório, testes e CI. Não altera o motor, a ABI, o produto ou as referências históricas.

Relatório completo: `benchmark-results/trajectory-transform-new-catalogue.json`. SHA-256 canônico, excluindo o próprio campo de hash: `45fa1281d8710b0001f3f7d451880610a57a016de679a84b62059f8b689fa5c6`.

```sh
PYTHONPATH=src python scripts/trajectory_transform_catalogue_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output /tmp/transform-new-catalogue.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m pytest -q tests/test_trajectory_transform_catalogue_probe.py
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. A CI do commit anterior `3d7c1d7` passou, run `41037546771`; a CI deste incremento fica pendente após publicação. `human_evaluation_status=NOT_PERFORMED` e `general_learning_status=NOT_ESTABLISHED` permanecem explícitos.

## Próxima etapa

Construir um diagnóstico de lacuna para o operador que use somente a leitura e seus testemunhos: símbolo sem mapa, nenhuma moldura compatível, ausência de destino observado ou hipóteses concorrentes. Uma fronteira específica pode ser informada como observação estrutural, mas não removida automaticamente. Avaliar se esse diagnóstico orienta demonstrações adicionais em casos novos, sem escolher uma verdade, produzir conteúdo inexistente ou usar os gabaritos para decidir a solicitação.

O comando opcional `diagnose` da sessão local está documentado em [trajectory-evidence-diagnosis.md](trajectory-evidence-diagnosis.md). Ele acrescenta orientação de evidências à leitura, preservando o comportamento de `query`.
