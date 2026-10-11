# Retirada explícita de feedback sem apagar o histórico

O novo laboratório permite retirar uma ocorrência exata de apoio ou oposição. A retirada é um evento nativo separado, com endereço próprio e referência ao endereço, ID, recibo e digest integral do feedback original. Nenhum registro de feedback, observação ou conteúdo da candidata é apagado ou reescrito.

O leitor novo aplica as retiradas antes da política de continuidade. Os leitores anteriores conservam seus contratos e não consultam esse campo novo. O recurso fica desativado por padrão e não foi integrado ao MVP ou à UI.

## Contrato da operação

`withdraw()` recebe região, ID da operação, identidade do chamador e o evento completo retornado por `events()`. O alvo precisa coincidir integralmente com uma ocorrência armazenada naquela região. O chamador informado precisa coincidir com o originador informado no feedback. Isso é consistência de identidade fornecida pelo chamador, **não autenticação ou proteção contra alguém que use o mesmo identificador**.

| Operação | Resultado |
|---|---|
| Retirada nova de feedback ativo | Acrescenta evento de controle e inativa somente aquela ocorrência |
| Mesmo ID de retirada e conteúdo idêntico | `EXACT_REPLAY`, sem nova ocorrência |
| Mesmo ID com alvo ou conteúdo diferente | Rejeita conflito de identidade |
| Novo ID tentando retirar ocorrência já retirada | Rejeita duplicação de alvo |
| Alvo alterado, endereço indevido, região diferente ou outro originador informado | Rejeita antes de gravar |
| Reenvio exato do feedback original depois da retirada | Continua idempotente; não reativa o feedback |
| Novo feedback com ID novo e recibo atual válido | Cria ocorrência independente, que pode voltar a vetar |
| Retirada de feedback histórico após append da memória | Permitida; o alvo é o evento armazenado, não um novo recibo de recuperação |

Não há retirada de retirada ou reativação automática. Uma nova decisão exige novo evento explícito. Retirada seguida de novo feedback não é uma substituição atômica: o chamador deve serializar as operações e aceitar o estado intermediário.

O campo `feedback-withdrawals:<hash da região>` usa envelope versionado de JSON canônico/UTF-8/Base64. Sua janela usa a guarda nativa de paginação existente. O novo leitor rejeita os campos de feedback e retirada como regiões de aprendizado, inclusive com o filtro desativado.

`feedback_projection()` preserva cada evento original e indica `active` e sua retirada correspondente. Valida endereço, digest, ID de feedback, ID de recibo, originador e unicidade dos controles. Histórias de retirada inválidas ou conflitantes são rejeitadas, em vez de produzir uma lista parcialmente filtrada.

`withdrawal_read()` usa somente os eventos ativos na política de continuidade já testada. A saída também transporta a projeção completa e todos os eventos de retirada. Se outra oposição compatível permanecer ativa, o veto permanece. Retirar um apoio não cancela oposição; apenas muda o estado de disputa para oposição quando apropriado.

Todas as candidatas e evidências continuam em `raw_view`. Disponibilidade não significa verdade: o envelope mantém resposta, proposta e seleção nulas, `qualified=false`, `selection_used=false` e qualidade factual `NOT_EVALUATED`.

## Resultados positivos e negativos

Desenvolvimento `20270107` e reservado `20270108`: quatro cenários em símbolos legíveis e em renomeação injetiva, oito experimentos por seed. Cada cenário registra feedback, acrescenta observação isolada, confirma o veto histórico, retira a ocorrência indicada e reabre o armazenamento. Os alvos são escolhidos por endereços observados; as referências são usadas somente para pontuar o resultado depois das operações.

| Cenário | Antes: esperados / extras / perdas | Depois: esperados / extras / perdas | Interpretação |
|---|---|---|---|
| Retirar oposição indevida à candidata correta | 0 / 0 / 1 | 1 / 0 / 0 | Restaura a recuperação correta sem apagar experiências |
| Retirar oposição válida à candidata extra | 1 / 0 / 0 | 1 / 1 / 0 | Restaura também um erro; retirada não sabe o que é verdade |
| Retirar uma de duas oposições independentes | 0 / 0 / 1 | 0 / 0 / 1 | Outra oposição continua mantendo o veto |
| Retirar apoio, mantendo oposição | 0 / 0 / 1 | 0 / 0 / 1 | Não remove o veto de outro evento |

Os resultados coincidem nos dois seeds e sob renomeação. Não há melhora geral estimada: um cenário melhora, outro piora e dois mantêm uma perda. A retirada demonstra controle explícito sobre o feedback, não julgamento autônomo da correção.

Passaram **145/145 verificações de integridade por seed**. Elas incluem histórico intacto, aprendizado e leitura bruta inalterados, alvo nativo exato, apenas uma inativação, reenvios, ausência de reativação acidental, modo desativado, três operações inválidas por cenário e igualdade completa após reabertura. As três outras consultas de cada experimento preservam suas leituras brutas: **24 controles por seed**.

Passaram **103 testes**: **13 novos** e as **90 regressões anteriores**. A suíte cobre também novo feedback independente após retirada, múltiplas oposições, reaproveitamento indevido de ID de retirada, escopos diferentes, adulteração de histórico de controle, campos reservados e request ID com Unicode, aspas, barras e quebra de linha.

Os relatórios completos foram repetidos e coincidiram byte a byte: `benchmark-results/trajectory-feedback-withdrawal-{development,reserved}.json`. Preservam observações, append, recibo inicial, evento-alvo, projeção, controle nativo, provas históricas de feedback restante, leitura completa e scores separados. O SHA-256 exclui o próprio campo `report_content_sha256`:

| Relatório | SHA-256 |
|---|---|
| Desenvolvimento | `3ad07cde156c32c8246ea5a0bc99eb4c96a7c1bee9a0e4f252035eeee99db46e` |
| Reservado | `05ffb0afee245367888ec5b3c8ca39a946c24743db4e2e6fe078ab29eefba721` |

## Limites e próximo passo

O sistema não decide quando uma retirada é adequada. O controle negativo demonstra que ela pode piorar a recuperação. Identidades não são autenticadas; não há múltiplos escritores, transação atômica entre campos, NLP de feedback, penalização aprendida, generalização semântica ou integração operacional.

As retiradas só têm efeito no novo leitor opt-in. Um consumidor que use o leitor antigo de continuidade continuará vendo a oposição original; o teste preserva essa diferença deliberadamente. Antes de uso real, será necessário um contrato único de serviço para que todos os consumidores apliquem a mesma projeção de controles.

O replay histórico ainda busca prefixos e reconstrói leituras; não há garantia de eficiência ou escala. Conteúdo ausente não é criado. Feedback restante pode estar errado. Os resultados negativos anteriores, inclusive intenção oculta indistinguível, continuam válidos. `general_learning_status=NOT_ESTABLISHED`.

O próximo passo é consolidar um fluxo experimental único de registrar, consultar, dar feedback e retirar feedback, mantendo a baseline preservada e avaliando o ciclo com operadores humanos. Aprender uma penalização de rota generalizável continua uma investigação separada.

## Reprodução e CI

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_feedback_withdrawal_probe.py

python scripts/trajectory_feedback_withdrawal_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --seed 20270107 --output /tmp/feedback-withdrawal-development.json
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. No commit anterior `385dd22`, **sete workflows passaram**. O workflow de trajetória, run `38095264122`, teve o job `proof` aprovado, mas `native-bridge` foi cancelado ao atingir 25 minutos, na etapa antiga de filtros contextuais iniciada às 23:51:08 UTC. As etapas de ledger, veto e continuidade já haviam passado; continuidade executou entre 23:35:51 e 23:38:16 UTC. A etapa contextual foi interrompida às 23:55:30 UTC e a etapa antiga seguinte não executou. Isso não é aprovação integral daquele workflow.

O limite de `native-bridge` passa de 25 para **40 minutos**, para acomodar a bateria cumulativa e as novas etapas. Não removemos testes ou controles de qualidade. O histórico do cancelamento permanece. A CI nova inclui os testes e ambos os seeds de retirada; sua aprovação completa fica pendente até executar. Núcleo, ABI, seletores padrão, MVP e PR draft permanecem preservados.
