# Maiúsculas na moldura e na entidade: localização da falha

Este diagnóstico separa três mudanças observadas: escrever em maiúsculas somente a parte fixa da pergunta, somente a entidade, ou ambas. Exemplo: `QUAL É O NOME DO coelho?`, `Qual é o nome do COELHO?` e `QUAL É O NOME DO COELHO?`. O leitor continua usando o texto original. As transformações são feitas pelo avaliador para construir perguntas e exemplos explícitos; nenhuma conversão automática foi adicionada ao produto.

Quatro memórias separadas (baseline e as três intervenções), quatro domínios, dois catálogos e um controle adicional de identificadores sensíveis a maiúsculas resultam em **304 consultas**: 288 nos domínios principais e 16 no controle de IDs. As demonstrações não incluem a pergunta-alvo. As referências e as anotações de fronteira e de pares de letras pertencem somente ao avaliador.

## Efeito da demonstração correspondente

| Catálogo | Pergunta original | Ensinar parte fixa e consultar parte fixa em maiúsculas | Ensinar entidade e consultar entidade em maiúsculas | Ensinar tudo e consultar tudo em maiúsculas |
|---|---:|---:|---:|---:|
| Development | 6/8 | 6/8 | 0/8 | 0/8 |
| Reserved | 7/8 | 7/8 | 1/8 | 1/8 |

Cada célula conta conteúdos esperados recuperados entre oito referências. No baseline, todas as mudanças de maiúsculas recuperam zero. A demonstração de maiúsculas somente na parte fixa transporta essa moldura a novas entidades, conservando a cobertura da pergunta original. A demonstração com entidade ou pergunta inteira em maiúsculas permanece frágil. As outras memórias não recebem melhora automática para tipos de mudança que não foram demonstrados.

Isso localiza a diferença observada na mudança de escrita da entidade copiada, em comparação com a parte fixa, mas não identifica a causa interna completa do leitor. O sistema não comprovou uma regra geral de equivalência de maiúsculas/minúsculas.

## Pares de letras: cobertura não é condição suficiente

O relatório enumera, fora do motor, os pares `letra.upper() → letra` presentes nas entidades das demonstrações e os necessários para o alvo. Isso descreve exposição textual; não certifica que o leitor tenha aprendido ou usado cada transformação.

No reservado, o domínio de dispositivos tem todos esses pares presentes e recupera um conteúdo após ensinar mudança na entidade. Outros domínios têm pares ausentes e recuperam zero. Porém, no development, o domínio de carros também tem todos os pares presentes e recupera zero. Portanto, esses resultados **não autorizam concluir que completar o alfabeto resolverá a falha**. É necessário inspecionar os testemunhos e a admissão das rotas para separar outras restrições.

## Identidades distintas e controles negativos

O controle guarda `O código do abc é 1.` e `O código do ABC é 2.` como conteúdos diferentes. As duas perguntas com suas escritas originais recuperam somente o conteúdo correspondente nos quatro braços: **16/16 consultas de IDs**, sem extra ou perda. O controle é repetido nos dois relatórios, com a mesma fixture; essas repetições não são duas amostras independentes. Essa verificação preserva distinção literal neste conjunto; não comprova todas as identidades possíveis.

Os cinco controles negativos por domínio (atributo ausente, entidade ausente, gerado, estrangeiro e sem sobreposição) conservam listas vazias: **160 consultas**, sem extras. Não houve extra em nenhuma das 304 consultas. A ausência de extras não elimina perdas de conteúdo esperado.

## Integridade e reprodução

Passaram **140/140 verificações por catálogo, 280 no total**: consultas e repetição sem escrita, histórico sem feedback implícito, proveniência aceita no escopo, envelopes sem qualificação, igualdade de histórico e de saídas completas após fechar e reabrir o handle. O baseline e as baterias anteriores permanecem intactos.

Validação local: **23 testes passaram**, incluindo sete novos e dezesseis regressões da sessão e da ablação anterior. Os dois relatórios foram repetidos e coincidiram byte a byte. Foram comparadas as **48 consultas comuns de baseline** com os relatórios anteriores dos dois catálogos: saídas completas e scores idênticos. Compilação Python e `git diff --check` passaram. A CI do novo incremento fica pendente após publicação.

| Relatório | Hash canônico sem o próprio campo de hash |
|---|---|
| `trajectory-feedback-case-development.json` | `5c62afb5a85b020d5d62625f788d52d41a7f07d8cdba3c095d0aabfece19c870` |
| `trajectory-feedback-case-reserved.json` | `0fef2c6106edb8f751c608dbc8f00d7fc1bd9e37293e9e9120184cdf10b8bd46` |

```sh
PYTHONPATH=src python scripts/trajectory_feedback_case_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --split reserved --output /tmp/feedback-case-reserved.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m pytest -q tests/test_trajectory_feedback_case_probe.py
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. CI verde significa integridade deste laboratório, não compreensão geral, normalização de IDs, resposta factual ou avaliação humana. `general_learning_status=NOT_ESTABLISHED` e `human_evaluation_status=NOT_PERFORMED` permanecem explícitos.

## Próxima investigação

Rastrear a composição e a admissão de transformações da entidade nos casos com cobertura de pares completa e incompleta. Comparar o caso de carros que falha mesmo com cobertura completa ao de dispositivos que recupera somente um conteúdo. Preservar a distinção de IDs e exigir evidência explícita antes de qualquer equivalência aprendida. Nenhuma normalização global deve ser deduzida desses resultados.

O rastreamento está documentado em [trajectory-entity-transform-trace-proof.md](trajectory-entity-transform-trace-proof.md). Identificou `F → F` ausente no caso de carros (o diagnóstico anterior contava somente pares que mudavam) e o sufixo ` V.` excessivamente específico no caso de dispositivos. Intervenções observadas e seus contrastes são registrados separadamente, preservando os resultados acima.
