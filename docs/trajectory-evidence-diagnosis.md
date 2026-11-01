# Diagnóstico estrutural para o operador

A sessão local agora aceita `diagnose`. Ele retorna a mesma leitura, candidatas, recibos e histórico de controles de `query`, acrescentando `result.diagnosis`. O operador pode inspecionar por que algumas rotas não admitem a consulta ou por que há mais de uma candidata. A orientação usa somente a consulta e as evidências observadas. Não recebe respostas de referência do avaliador.

```sh
PYTHONPATH=src python scripts/trajectory_feedback_session.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --data-dir ./data/feedback-session
```

No terminal, envie uma operação por linha:

```json
{"op":"diagnose","scope":"principal","text":"Qual é o nome do meu gato?"}
```

## O que o diagnóstico informa

| Achado | Evidência e orientação |
|---|---|
| `NO_LEARNED_FRAMES` | Não há molduras aprendidas. O operador pode fornecer exemplos observados de pergunta/conteúdo em sequência. |
| `NO_COMPATIBLE_SOURCE_FRAME` | As molduras existentes não admitem os prefixos e limites desta consulta. Conferir a escrita e demonstrar essa forma de perguntar, se pertinente. |
| `UNWITNESSED_SYMBOLS_IN_FRAMES` | Algumas rotas não têm mapa para todos os símbolos da variável. O relatório mostra os símbolos, os pares e os IDs das molduras, inclusive lacunas de pares identidade. |
| `NO_OBSERVED_DESTINATION_IN_FRAMES` | Algumas molduras aplicáveis não admitem destino observado. Conferir mapa, conteúdo disponível e limites antes de fornecer novas observações. |
| `OBSERVED_TARGET_BOUNDARY_MISMATCH` | Há conteúdo com prefixo compatível excluído pelo sufixo ou por um espaço de valor vazio. Conferir pertinência e demonstrar outra forma observada, se adequada. |
| `COMPETING_TRANSFORM_DESTINATIONS` | Rotas admitidas transformam a consulta em destinos diferentes. As alternativas permanecem para inspeção. |
| `MULTIPLE_OBSERVED_CANDIDATES` | Há mais de uma candidata na leitura bruta. Isso não estabelece contradição factual nem uma votação de verdade. |
| `EXPLICIT_FEEDBACK_WITHHOLDS_CANDIDATES` | Conteúdo continua na leitura bruta, mas está suspenso por feedback explícito. Conferir o histórico antes de concluir que falta conteúdo na memória. |
| `OBSERVED_CANDIDATE_REQUIRES_REVIEW` | Há uma candidata observada sem outros achados estruturais nesta leitura; sua adequação factual continua sem avaliação. |

Os achados não são mutuamente exclusivos. Uma moldura pode carecer de mapa enquanto outra recupera uma candidata. O relatório conserva os IDs e testemunhos por moldura, para não transformar a falha de uma rota em diagnóstico global de ausência de conhecimento.

O estado geral é `UNRESOLVED` sem candidatas brutas; `CANDIDATES_REQUIRE_REVIEW` quando há candidatas disponíveis; ou `FEEDBACK_WITHHELD` quando todas as candidatas brutas estão suspensas. Os contadores de candidatas brutas, disponíveis e suspensas são separados. `frames` contém a análise das duas rotas, cópia literal e transformação; `transform_trace` mantém a explicação da rota de transformação.

## Limites e efeitos

O diagnóstico não escolhe qual alternativa é verdadeira, não deduz que um atributo está presente ou ausente semanticamente e não classifica a qualidade do texto. Ausência de moldura compatível não equivale a inexistência de fato no mundo. Prefixo compatível excluído pelo sufixo não autoriza retirar esse sufixo: ele pode ser uma restrição correta.

As orientações são sugestões para inspeção humana. Nenhuma solicitação é enviada e nenhum exemplo é criado, gravado ou incorporado automaticamente. `request_dispatched=false`, `learning_performed=false` e `query_recorded=false`. O envelope mantém resposta e seleção nulas, `qualified=false`, `selection_used=false` e qualidade factual `NOT_EVALUATED`.

A consulta comum não muda. Os limites da sessão continuam 64 observações e 4096 caracteres por escopo e 4000 caracteres por consulta. `diagnose` é uma operação explícita do laboratório local; não integra o servidor de produto, a UI ou a ABI nativa.

## Validação

O avaliador `trajectory_evidence_diagnosis_probe.py` percorre as 32 consultas principais do catálogo de mapas, duas consultas de IDs sensíveis à escrita, uma memória vazia e uma consulta incompatível: **36 casos**. Não fornece os conjuntos esperados ao diagnóstico. Em cada caso, compara a saída com `query` após remover somente `diagnosis`, compara histórico antes/depois, repete a leitura e fecha/reabre o armazenamento para conferir a saída completa.

O rastreador de transformação anterior foi extraído sem mudança de comportamento para `trajectory_transform_trace_core.py`, evitando dependência circular entre o avaliador e a sessão. Tanto a transformação quanto a cópia literal conferem seu conjunto de candidatas contra a rota real; discordância interrompe a operação em vez de exibir uma explicação incoerente.

```sh
PYTHONPATH=src python scripts/trajectory_evidence_diagnosis_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output /tmp/evidence-diagnosis.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m pytest -q tests/test_trajectory_evidence_diagnosis.py
```

Relatório completo: `benchmark-results/trajectory-evidence-diagnosis.json`. A utilidade para operadores humanos permanece sem avaliação: os testes validam o contrato de evidências e a ausência de efeitos de aprendizagem, não a eficácia das sugestões em uso real.

Passaram **22 testes locais**, nove novos e treze regressões da sessão e do rastreador. O protocolo real do terminal foi exercitado em subprocesso. Passaram **288/288 verificações nos 36 casos** e o relatório repetiu byte a byte, com SHA-256 canônico `c84d9a0a942e1a84b40ab3936154f398e3d8c8d13f09857ad4d92a4a0d3d67aa` (sem o próprio campo de hash). A bateria anterior de **196 consultas** reproduziu integralmente `trajectory-transform-new-catalogue.json`, sem alteração de conteúdo. Compilação Python e `git diff --check` passaram. A CI do novo incremento fica pendente após publicação.

## Próxima etapa

Avaliar se um operador, usando somente esses achados e a proveniência, consegue escolher uma demonstração adicional que resolva casos novos. Preservar alternativas ambíguas, controles de conteúdo inexistente e histórico de sugestões que não melhoraram a recuperação. Não usar as referências do avaliador para escolher a próxima ação.

O protocolo preparatório `review_examples` está em [trajectory-demonstration-review.md](trajectory-demonstration-review.md). Sua avaliação programada conserva marcações sem melhora e exemplos úteis sem marcação; a avaliação humana permanece pendente.
