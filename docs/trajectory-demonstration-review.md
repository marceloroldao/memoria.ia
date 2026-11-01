# Revisão de demonstrações: apoio estrutural sem escolha automática

A sessão local passa a aceitar `review_examples`. O operador fornece uma consulta e de um a oito conjuntos de exemplos. Cada conjunto contém de um a três pares explícitos de texto de origem e conteúdo, com um identificador e proveniência declarada opcional. A sessão retorna a leitura, o diagnóstico e `result.example_review`, preservando todos os conjuntos e sua ordem.

Exemplo de operação no terminal da sessão:

```json
{"op":"review_examples","scope":"principal","text":"Qual é a cor do FIESTA?","offers":[{"offer_id":"exemplo-1","provenance":"Observação a conferir pelo operador","examples":[{"source_text":"Qual é a cor do FORTE?","target_text":"A cor do Forte é verde."}]}]}
```

O exemplo ilustra a interface; não constitui uma afirmação verificada sobre esses objetos. Para executar a sessão, use as instruções de `trajectory-feedback-session.md`.

## O que a marcação significa

`EXPOSES_MISSING_SOURCE_SYMBOL` indica que um exemplo contém, na variável de uma moldura compatível, algum símbolo que faltava ao mapa da consulta. A marcação **não verifica qual deve ser a saída desse símbolo**. Tanto um exemplo com mapa adequado quanto outro com mapa inadequado podem receber a mesma marcação.

`VARIES_RESTRICTING_TARGET_ENDING` indica que um exemplo com forma de origem compatível apresenta um final diferente do sufixo de uma moldura que excluía conteúdo observado. Não certifica pertinência, verdade ou que uma nova moldura será aprendida.

Cada marcação expõe índice do exemplo, ID da moldura e símbolo ou final envolvido. O diagnóstico e a leitura bruta fornecem os testemunhos e a proveniência relacionados. A lista `structurally_related_offer_ids` apenas resume marcações; **não é uma recomendação de vencedor**. Todos os conjuntos, inclusive os sem marcação, permanecem em `offers`, na ordem recebida. `selected_offer_id=null`, `ranked=false` e `selection_used=false`.

O operador precisa conferir a origem e a adequação de cada exemplo. Se decidir registrá-lo, deve usar operações explícitas `observe`, com a origem correta e os limites da sessão. `review_examples` não chama esse registro. `offers_recorded=false`, `learning_performed=false` e `request_dispatched=false`.

## Avaliação do protocolo e limites encontrados

Dois catálogos novos, pressão (`Pa`) e potência (`W`), usam identificadores diferentes dos anteriores. Em cada um, quatro cenários apresentam três conjuntos de exemplos com IDs neutros e proveniência idêntica: um contraste, uma intervenção adequada e um conjunto irrelevante. **Nenhum rótulo de eficácia ou resposta esperada é passado à revisão.** Os oito casos de revisão produzem 24 tentativas, cada uma avaliada depois em armazenamento separado. O avaliador tenta todos os conjuntos; não usa scores para escolher o próximo.

| Cenário, repetido nos dois catálogos | Conjuntos marcados | Efeito observado nas tentativas |
|---|---|---|
| Símbolo sem mapa | Contraste e intervenção | Só a intervenção melhora a recuperação |
| Par identidade sem testemunho | Contraste e intervenção | Só a intervenção melhora a recuperação |
| Mapas concorrentes ainda não expostos | Nenhum | A intervenção acrescenta uma segunda hipótese observada, mesmo sem marcação |
| Final de valor excessivamente específico | Intervenção | A intervenção melhora; contraste e irrelevante não melhoram |

No total, houve **10 conjuntos marcados**. Destes, **quatro não melhoraram** a recuperação. Entre os conjuntos sem marcação, **dois melhoraram**. Todas as oito intervenções adequadas melhoraram os casos construídos; os oito contrastes e os oito conjuntos irrelevantes não melhoraram. Essas comparações usam as referências somente na pontuação após cada tentativa.

O resultado impede tratar a revisão como seletor confiável. Uma lacuna de símbolos não revela o mapa correto. Uma candidata já admitida pode ocultar a falta de outra hipótese: o diagnóstico não tem um gabarito para saber que uma alternativa ainda deveria aparecer. Marcação ausente não significa exemplo inútil.

Os **120 controles negativos**, cinco por tentativa, permaneceram vazios. O conteúdo de outro escopo foi efetivamente registrado em uma região separada. Nos casos com mapas concorrentes, o leitor conserva alternativas sem escolher uma verdade. As tentativas são programadas; **não houve avaliação com operadores humanos**, nem medição de tempo de decisão, facilidade de uso ou melhora de uma pessoa após ler as orientações.

## Contrato e validação

IDs de conjuntos devem ser únicos, não vazios e ter até 128 caracteres. A proveniência declarada é texto com até 256 caracteres e não é autenticada. Cada texto de exemplo deve conter conteúdo não vazio e ter até 2000 caracteres. O total de textos oferecidos é limitado a 16000 caracteres. Campos desconhecidos, inclusive rótulos como `expected`, são rejeitados. Os limites originais da memória e da consulta continuam válidos.

O relatório é `benchmark-results/trajectory-demonstration-review.json`. Guarda revisão completa, conjuntos recebidos, leitura e score antes/depois de cada tentativa e resultados negativos. As verificações cobrem leitura sem gravação local ou estrangeira, igualdade de diagnóstico, ordem recebida, nenhuma escolha ou ação automática, repetição integral e paridade após fechar/reabrir o armazenamento.

Passaram **34 testes locais**, quinze novos e dezenove regressões da sessão e do diagnóstico. O protocolo real de `review_examples` foi exercitado pelo terminal em subprocesso. Passaram **104/104 verificações** nos oito casos de revisão e nas 24 tentativas separadas. O relatório repetiu byte a byte; SHA-256 canônico sem o próprio campo de hash: `3dae56bd62ba2e39736e5853c3d0f342a79dac164af3ab330c8e58a64e21b849`. O relatório anterior de 36 casos de diagnóstico também reproduziu integralmente sem alterações. Compilação Python e `git diff --check` passaram. A CI do novo incremento fica pendente após publicação.

```sh
PYTHONPATH=src python scripts/trajectory_demonstration_review_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output /tmp/demonstration-review.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m pytest -q tests/test_trajectory_demonstration_review.py
```

A avaliação em catálogos novos continua curada e correlacionada; não mede precisão geral de linguagem. O motor, a ABI e a saída de `query`/`diagnose` permanecem preservados. A operação é exclusiva do laboratório local, sem integração à UI ou ao servidor de produto. `human_evaluation_status=NOT_PERFORMED` e `general_learning_status=NOT_ESTABLISHED` continuam explícitos.

## Próxima etapa

Realizar a avaliação humana usando exemplos com proveniência real. Registrar a escolha do operador, inclusive quando ele mantém a dúvida, e avaliar separadamente a pertinência da escolha e o efeito posterior na recuperação. Manter visíveis os casos de marcação sem melhora e melhora sem marcação; não converter essa heurística em registro ou seleção automática.

O registro persistente de escolha, adiamento e rejeição está disponível em [trajectory-review-decisions.md](trajectory-review-decisions.md). Ele preserva o recibo exato sem incorporar os exemplos à região de aprendizagem. A avaliação humana continua pendente.
