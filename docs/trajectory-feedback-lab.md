# Laboratório local unificado de feedback

`scripts/trajectory_feedback_lab.py` reúne registro, consulta, feedback, retirada e histórico numa única interface JSONL. Cada linha de entrada contém um objeto JSON; cada linha de saída contém sua resposta. Os dados persistem no BDR nativo. É uma ferramenta local de laboratório, sem endpoint de rede, LLM ou integração ao MVP/OFF.IA.

Todas as consultas desta interface usam o leitor que conhece as retiradas. Isso elimina, dentro deste laboratório, a divergência entre consultar com a política antiga e retirar com a política nova. Os leitores anteriores mantêm seus contratos. Não é um contrato de serviço de produção nem uma interface gráfica.

## Iniciar

Use Linux, Python e a biblioteca nativa compilada com o BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`, conforme o workflow `trajectory-generation-proof.yml`:

```bash
python scripts/trajectory_feedback_lab.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --data-dir /tmp/meu-laboratorio-memoria \
  --enable-feedback
```

Escolha um diretório novo e exclusivo para o laboratório. A mesma pasta permite retomar o estado em outra execução. Sem `--enable-feedback`, a consulta expõe todas as candidatas brutas e operações de feedback/retirada são recusadas. O histórico ainda mostra quais eventos foram retirados. Essa opção altera a política de disponibilidade, não a evidência armazenada.

Não execute outras ferramentas nativas sobre o mesmo diretório. Um lock consultivo impede dois processos cooperantes deste laboratório; não bloqueia ferramentas externas. Chamadas pela classe `FeedbackLab` são serializadas por um lock local. Cada operação de escrita confirma `flush` antes de retornar sucesso. Uma falha de armazenamento interrompe o processo com resultado incerto; reabra e confira o histórico antes de repetir usando o mesmo ID.

## Comandos

Todos aceitam `scope`, por padrão `principal`. O nome tem de conter 1–64 letras ASCII, números, `_` ou `-`; é convertido numa região privada do laboratório. Nenhum comando aceita um endereço arbitrário de região.

| `op` | Campos adicionais | Efeito |
|---|---|---|
| `observe` | `source_id`, `text`, opcional `source_kind` | Acrescenta observação; ID repetido com conteúdo e tipo iguais retorna `EXACT_REPLAY` |
| `query` | `text` | Retorna leitura integral, candidatas disponíveis/vetadas e recibos exatos; não grava a consulta |
| `feedback` | `receipt`, `event_id`, `actor_id`, `stance` | Registra `support` ou `oppose` no recibo fornecido |
| `withdraw` | `event_id`, `request_id`, `actor_id` | Resolve o evento exato no escopo e registra sua retirada |
| `history` | nenhum | Lista observações, feedback com estado ativo/inativo e retiradas |

Exemplos de linhas de entrada:

```json
{"op":"observe","source_id":"observacao-1","text":"Meu gato se chama Alt."}
{"op":"query","text":"Qual é o nome do meu gato?"}
{"op":"history"}
```

Essas três linhas demonstram o protocolo; uma observação isolada não garante que essa pergunta recupere uma candidata. O laboratório mantém as limitações de recuperação anteriores.

Quando uma consulta retorna candidatas, escolha explicitamente o recibo correspondente em `result.receipts` e envie o objeto integral, sem alterações, no campo `receipt`:

```python
feedback = {
    "op": "feedback",
    "scope": "principal",
    "receipt": resposta_da_consulta["result"]["receipts"][indice_escolhido],
    "event_id": "correcao-1",
    "actor_id": "operador-local",
    "stance": "oppose",
}
```

O índice representa uma escolha do operador; não há seleção automática pelo laboratório. O recibo contém consulta, snapshot e evidência completa. Uma nova observação torna o recibo antigo inválido para feedback novo. Reenvio idêntico de evento já registrado continua idempotente. Cada candidata, inclusive vetada, conserva seu recibo e evidência bruta.

Para retirar essa oposição:

```json
{"op":"withdraw","event_id":"correcao-1","request_id":"retirada-1","actor_id":"operador-local"}
{"op":"history"}
```

O feedback original continua no histórico, agora inativo, com a retirada endereçada. Outro evento de oposição permanece independente. Reenviar o evento original não o reativa; um novo evento exige outro ID e recibo atual válido. `actor_id` é identidade declarada, sem autenticação.

`assistant_generated` é aceito apenas como trilha separada e barreira temporal, nunca como demonstração de aprendizado. Não envie saídas inferidas como `user_turn` automaticamente.

## Limites e interpretação

O laboratório admite no máximo 64 observações somando 4096 caracteres por escopo, 64 eventos de feedback e 64 retiradas. Recusa operações que excedam esses limites, sem leitura parcial. Repetições exatas existentes podem ser reenviadas no limite. A composição e a reconstrução histórica continuam custosas; estes limites não demonstram escala.

A saída mantém `answer=null`, `qualified=false`, `selection_used=false` e qualidade factual `NOT_EVALUATED`. Apoio não promove candidata a fato. Retirada de veto indevido pode restaurar conteúdo correto; retirada de veto válido também restaura um erro. Ausência de evidência não é corrigida por feedback. Não há penalização de rota aprendida, generalização semântica ou transação atômica de retirada seguida de nova decisão.

Comandos JSON inválidos e recusas de contrato retornam `ok=false`; a sessão continua. `ok=true` indica execução da operação, não acerto factual. Erros fatais de armazenamento encerram o processo. A saída pode conter textos e evidências privados: encaminhe-a apenas para destinos escolhidos pelo operador.

## Validação

Oito testes nativos novos passaram, incluindo:

- ciclo completo com observação posterior, veto histórico, retirada e igualdade após reabertura;
- execução real da CLI em quatro processos separados, com recibo atravessando reinícios;
- manutenção de outra oposição e criação de feedback independente após retirada;
- restauração de candidata extra como controle negativo, sempre sem qualificação factual;
- política desativada, isolamento de escopos, recibo adulterado/antigo e identidade incompatível;
- idempotência de observação, feedback e retirada, preservação de histórico, separação de conteúdo gerado, limites e exclusão entre processos.

Também passaram as 44 regressões das suítes de ledger, veto, continuidade e retirada: **52 testes locais aprovados no total**. A biblioteca foi compilada localmente com o pin de BDR acima. Compilação Python e `git diff --check` passaram. A CI inclui a nova suíte, mas sua execução remota precisa ser consultada no commit publicado; estes resultados locais não são aprovação de CI.

```bash
PYTHONPATH=src python -m pytest -q tests/test_trajectory_feedback_lab.py
PYTHONPATH=src python -m pytest -q \
  tests/test_trajectory_feedback_ledger_probe.py \
  tests/test_trajectory_feedback_gate_probe.py \
  tests/test_trajectory_feedback_continuity_probe.py \
  tests/test_trajectory_feedback_withdrawal_probe.py
```

Esses são testes automatizados sobre fixtures controlados. Nenhuma avaliação com operadores humanos foi realizada. O próximo passo é executar sessões supervisionadas sobre esse fluxo e registrar ganhos e perdas por consulta antes de integrar UI ou aprender penalizações generalizáveis. O PR permanece em rascunho; aprovação de integridade não resolve as falhas históricas de qualidade.
