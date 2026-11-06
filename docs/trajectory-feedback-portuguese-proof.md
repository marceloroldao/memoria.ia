# Sessão de feedback: diagnóstico em português

Continuação do fluxo unificado do PR #382. Esta bateria executa 32 consultas sintéticas: quatro domínios (animais, carros, tensão de dispositivos e agenda), cada um com três demonstrações observadas de pergunta/conteúdo, duas informações concorrentes e controles de conteúdo gerado e de outro escopo. Não houve participação humana nesta avaliação. As referências são exclusivas da pontuação: não são enviadas ao motor ou usadas para escolher o alvo de feedback.

## Resultados de recuperação

| Tipo de consulta | Consultas | Conjuntos exatos | Conteúdos recuperados / esperados | Extras |
|---|---:|---:|---:|---:|
| Mesma moldura observada, entidade nova e conflito | 4 | 2 | 6 / 8 | 0 |
| Paráfrase não demonstrada | 4 | 0 | 0 / 8 | 0 |
| Pergunta em maiúsculas não demonstrada | 4 | 0 | 0 / 8 | 0 |
| Atributo, entidade ou conteúdo válido ausente; origem gerada/estrangeira; sem sobreposição | 20 | 20 | 0 / 0 | 0 |
| Total | 32 | 22 | 6 / 24 | 0 |

Há **18 conteúdos esperados ausentes**. O total 22/32 não deve ser chamado de precisão geral: vinte resultados exatos são listas vazias em controles negativos. Entre as doze consultas com conteúdo de referência, apenas duas recuperam o conjunto completo. As perguntas são correlacionadas e os exemplos são curados, não um benchmark independente.

Nos domínios animais e carros, a pergunta com a mesma moldura recupera as duas informações concorrentes. Nos domínios dispositivos e agenda, recupera apenas uma delas. Nenhuma das quatro paráfrases ou das quatro perguntas em maiúsculas recupera o conteúdo esperado. Não foi acrescentado normalizador, filtro por vocabulário, limiar, ranking ou nova regra ao leitor para contornar as falhas.

Esse resultado refere-se ao leitor experimental de molduras da sessão de feedback. Ele não substitui a bateria de recuperação nativa HTTP de 37 perguntas do MVP: são leitores, entradas e consultas diferentes, e seus totais não permitem comparação direta de superioridade.

## Efeito do feedback

O operador simulado escolhe o primeiro recibo retornado, sem consultar a referência, registra oposição e depois retira esse evento exato. O ciclo executa nos quatro domínios. Neste conjunto, o alvo escolhido era conteúdo esperado em todos os quatro ciclos: a oposição incorreta retira um conteúdo útil e piora a cobertura. A retirada restaura o conjunto anterior, sem corrigir as perdas que já existiam.

| Domínio | Esperados recuperados antes | Após oposição | Após retirada |
|---|---:|---:|---:|
| Animais | 2 | 1 | 2 |
| Carros | 2 | 1 | 2 |
| Dispositivos | 1 | 0 | 1 |
| Agenda | 1 | 0 | 1 |

O feedback demonstra controle de ocorrência, não julgamento autônomo nem melhora garantida. As candidatas continuam no `raw_view`; o leitor não cria conteúdo ausente. A consulta inicial é pontuada antes dos controles. Os recibos e históricos completos permitem auditar o ciclo posterior separadamente.

## Integridade e reprodução

Passaram **92/92 verificações**: consultas sem escrita, repetição integral, origem observada no escopo, ausência de qualificação, raw view preservado, suspensão exata de uma candidata, restauração do conjunto e igualdade completa após fechar/reabrir o handle. Históricos de feedback e retirada também são comparados após reabertura.

```sh
PYTHONPATH=src python scripts/trajectory_feedback_portuguese_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output benchmark-results/trajectory-feedback-portuguese.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m pytest -q tests/test_trajectory_feedback_portuguese_probe.py tests/test_trajectory_feedback_session.py
```

O gate retorna falha de processo somente por quebra de integridade; conserva `retrieval_status=EXTRA_OR_MISSING_CONTENT`, `human_evaluation_status=NOT_PERFORMED` e `general_learning_status=NOT_ESTABLISHED`. CI verde não aprova compreensão de português. BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`.

Relatório: `benchmark-results/trajectory-feedback-portuguese.json`, com saídas completas e ciclo de feedback. SHA-256 do conteúdo canônico, excluindo o próprio campo de hash: `61c71b900e69351cc0e2fc6422cd1624d97c1ab905fc4281142b66c54feb3548`.

## Próxima investigação

Medir, em outro catálogo reservado, se demonstrar explicitamente variações de pergunta permite recuperar conteúdo em novas entidades sem aumentar respostas a atributos ausentes. Separar o efeito de molduras demonstradas, variações em maiúsculas e paráfrases novas; preservar esses 32 resultados como baseline. A avaliação com operadores humanos permanece pendente e poderá usar o ciclo documentado em `trajectory-feedback-session.md`.

A ablação correspondente está registrada em [trajectory-feedback-variants-proof.md](trajectory-feedback-variants-proof.md), com resultados separados por catálogo e por tipo de demonstração. O diagnóstico inicial acima permanece preservado.
