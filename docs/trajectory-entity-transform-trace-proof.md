# Admissão da transformação: identidade de símbolo e terminação do valor

O rastreador explica a admissão das molduras de transformação que o leitor já aprendeu. Recebe somente a consulta, as observações e a leitura bruta: não recebe respostas de referência. Registra a contagem de ocorrências do prefixo, a variável extraída, os símbolos sem mapeamento, os pares exigidos, o prefixo convertido e a decisão para cada conteúdo observado. Seu conjunto de textos admitidos é comparado ao conjunto retornado pela rota real `symbol_transform`.

As molduras originais e seus testemunhos com proveniência permanecem nas saídas completas. O rastreador não escolhe candidatas, não modifica observações ou molduras e não muda o leitor. Os scores com referências são calculados separadamente, depois das leituras.

## Causa do caso de carros: o par identidade ausente

No development, a consulta `Qual é a cor do FIESTA?` produz a variável `FIESTA`. A única moldura correspondente possui mapeamentos para as outras letras, mas não contém o símbolo `F` como chave. O leitor exige mapeamento para **todo** símbolo da variável, inclusive aquele cuja saída seria idêntica. Ele rejeita a rota antes de procurar conteúdos de destino.

O diagnóstico anterior listava pares de letras que mudam com `.upper()`; não incluía pares identidade como `F → F`. Portanto, sua anotação de cobertura completa desses pares não certificava a cobertura do mapeamento integral exigido pelo leitor. O relatório antigo fica preservado como histórico; a insuficiência da medida é identificada aqui.

Em memórias separadas, acrescentamos somente observações explícitas:

| Intervenção | Conteúdos esperados recuperados | Efeito observado |
|---|---:|---|
| Baseline | 0/2 | `F` não está no mapeamento |
| Observação isolada, sem demonstração | 0/2 | Nenhuma melhora |
| `Qual é a cor do FORTE?` seguido de `A cor do Forte é verde.` | 2/2 | Uma nova moldura inclui `F → F` e cobre a variável inteira |
| Mesma pergunta seguida de `A cor do forte é verde.` | 0/2 | A nova moldura converte para `fiesta`; não há conteúdo com esse prefixo |

Nenhuma demonstração acrescentada contém a entidade Fiesta, sua pergunta ou seu payload. Não houve normalização de maiúsculas/minúsculas. O contraste mostra que os valores exatos do mapa importam; ele não ensina que toda letra deve ser preservada.

## Causa da perda em dispositivos: sufixo comum aprendido

No reserved, a moldura para `Qual é a tensão do CONVERSOR?` cobre todos os símbolos da variável e converte corretamente para `conversor`. Entretanto, seus três testemunhos têm valores que terminam em ` V.`. Esse final torna-se parte fixa da moldura. O conteúdo observado `A tensão do conversor é desconhecido.` passa pelo prefixo de destino e falha na exigência do sufixo. A perda decorre dessa fronteira aprendida, e não de desconhecimento dos símbolos da entidade.

| Intervenção | Conteúdos esperados recuperados | Efeito observado |
|---|---:|---|
| Baseline | 1/2 | Sufixo ` V.` exclui o conteúdo concorrente |
| Observação isolada | 1/2 | Nenhuma melhora |
| `Qual é a tensão do ADAPTADOR?` seguido de `A tensão do adaptador é desconhecido.` | 2/2 | Nova moldura com sufixo mais curto admite ambos os conteúdos |
| Mesma pergunta seguida de `A tensão do adaptador é 18 V.` | 1/2 | A diversidade de entidades aumenta, mas o final ` V.` permanece |

O avaliador trata os dois conteúdos concorrentes como referências de recuperação, sem julgar qual é verdadeiro ou qual redação é desejável. Esta intervenção foi escolhida após inspecionar a falha: é um teste causal direcionado, não desempenho em um conjunto reservado independente.

## Integridade, limites e reprodução

São oito memórias independentes, duas falhas conhecidas e quatro braços por falha, com nove consultas por memória: **72 consultas**, incluindo **40 controles negativos** que retornam listas vazias. Passaram **80/80 verificações de integridade**: leitura/repetição sem escrita, proveniência, ausência de feedback implícito, envelope sem qualificação, paridade de reabertura, paridade entre rastreador e rota real e preservação da leitura durante o rastreamento. As **18 saídas completas e scores dos braços baseline** coincidem com os relatórios anteriores.

Passaram **18 testes locais**: três novos do rastreador/intervenções e quinze regressões da localização de maiúsculas e da rota original de transformação. O relatório foi repetido e coincidiu byte a byte. Compilação Python e `git diff --check` passaram.

As intervenções acrescentam observações programadas pelo avaliador. Não são aprendizagem autônoma a partir das próprias inferências. Nenhuma saída gerada é promovida a fato. Não há alteração no motor, na ABI ou no produto. O acerto dos dois casos não estima desempenho geral de linguagem ou de identidade.

Relatório: `benchmark-results/trajectory-entity-transform-trace.json`. SHA-256 canônico sem o próprio campo de hash: `a9f0aaebe21a247a444ebfbedec19eac66c193b776eaf3485387f2c147c9af2e`.

```sh
PYTHONPATH=src python scripts/trajectory_entity_transform_trace.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output /tmp/entity-transform-trace.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m pytest -q tests/test_trajectory_entity_transform_trace.py
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. `general_learning_status=NOT_ESTABLISHED` e `human_evaluation_status=NOT_PERFORMED` permanecem explícitos. O commit anterior `c3b1832` completou a CI de trajetória com sucesso, run `38342492716`; a CI deste incremento fica pendente após publicação.

## Próxima etapa

Medir em um catálogo novo a separação entre símbolo nunca observado, símbolo observado com mapa conflitante e fronteira de valor excessivamente específica. Incluir controles de IDs sensíveis à escrita. Só então avaliar uma política que solicite demonstrações adicionais com base na lacuna estrutural, sem criar respostas nem retirar restrições sem evidência.
