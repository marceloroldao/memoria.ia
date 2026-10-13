# Sessão local unificada de feedback

Continuação de `7dc43da`: um único leitor experimental aplica continuidade e retirada em todas as consultas desta sessão. O incremento reúne registro, consulta, feedback e retirada em um processo Linux por diretório. Não modifica o MVP, a ABI ou o servidor de produto.

## Execução

Use a biblioteca nativa construída com BDR `317882a00f041fc1568ff986af8016b09453f21a`, conforme `docs/trajectory-local-mvp.md`:

```sh
PYTHONPATH=src python scripts/trajectory_feedback_session.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --data-dir ./data/feedback-session
```

O terminal recebe um objeto JSON por linha e devolve um objeto por operação. Reinicie com o mesmo diretório para reabrir os três históricos. O processo mantém um lock exclusivo até encerrar. Use um diretório exclusivo deste laboratório; outros programas que ignoram o lock não são protegidos por ele. Não há serviço HTTP nem autenticação de identidades de operadores.

| `op` | Campos adicionais | Resultado |
|---|---|---|
| `observe` | `event_id`, `text`, `source_kind` opcional | Registra observação e confirma flush; replay exato não cria ocorrência |
| `query` | `text` | Recuperação bruta, candidatas disponíveis/suspensas, projeção de controles e recibos de todas as candidatas |
| `feedback` | `receipt`, `event_id`, `actor_id`, `stance` (`support`/`oppose`) | Registra evento explícito vinculado ao recibo integral, com flush |
| `withdraw` | `target`, `request_id`, `actor_id` | Retira somente a ocorrência exata, acrescentando controle com flush |
| `history` | Nenhum | Observações, feedback original com estado ativo e histórico completo de retiradas |

Todas as operações aceitam `scope`, por padrão `principal`; o nome permite letras ASCII, números, hífen e sublinhado, até 64 caracteres. A região é derivada internamente. Recibo de outro escopo é rejeitado. Campos desconhecidos são rejeitados, inclusive uma tentativa de desativar a projeção nesta sessão.

## Ciclo para avaliação humana

1. Registre exemplos e conteúdo como observações explícitas. `source_kind` admite `user_turn` ou `assistant_generated`; conteúdo gerado é conservado com sua origem e excluído da aprendizagem pelo leitor experimental.
2. Consulte e inspecione `result.raw_view`, as evidências e `result.receipts`. A consulta não registra a pergunta.
3. Copie um recibo integral para `receipt` em uma operação de feedback. O operador decide `support` ou `oppose`; o laboratório não decide se ele tem razão.
4. Consulte novamente: oposição compatível suspende a candidata. Um append isolado pode manter o veto quando a evidência permanece idêntica.
5. Para retirar o feedback, copie exatamente `address` e `event` do retorno de feedback para `target`. Não copie `status` ou `persisted` para o alvo. Também pode obter esses dois campos em `history`, removendo `active` e `withdrawal` da entrada projetada.
6. Consulte e reabra o programa para verificar o efeito. A retirada não apaga o feedback, não reativa por replay e não cancela outra oposição independente.

Exemplo de comandos iniciais:

```json
{"op":"observe","event_id":"fato-1","text":"Meu gato se chama Alt."}
{"op":"query","text":"Qual nome do meu gato?"}
{"op":"history"}
```

Uma consulta pode não fornecer candidatas úteis. Não se fabrica recibo se nenhuma candidata foi recuperada. Não há seleção automática, resposta factual, interpretação livre de frases de correção, penalização aprendida ou generalização do feedback.

## Limites e validação

Cada escopo admite 64 observações e 4096 caracteres totais, incluindo conteúdo gerado; consultas até 4000 caracteres. A análise não usa um recorte parcial ao exceder limites. Esses limites não representam garantia de desempenho. Históricos de controles não têm limite de aplicação próprio neste incremento. Replay histórico continua custoso.

Todo retorno mantém `answer:null`, `qualified:false`, `selection_used:false`, `factual_quality_status:NOT_EVALUATED` e `general_learning_status:NOT_ESTABLISHED`. Retirar oposição correta pode restaurar um erro, conforme o controle negativo anterior. Falha nativa ou de flush encerra o processo; persistência não confirmada deve ser inspecionada na reabertura.

O teste de integração percorre observação, consulta, oposição, append, continuidade, retirada e reabertura completa do handle. Outros testes cobrem replay, conflito de identidade, recibo obsoleto, isolamento de escopo, origem gerada, leitura sem escrita e exclusão de segundo escritor. O workflow de trajetória inclui essa suíte.

Validação local: **10 testes da sessão passaram**, incluindo execução real do protocolo por subprocesso e reabertura posterior. As **44 regressões** de ledger, veto, continuidade e retirada também passaram com a biblioteca nativa e o BDR fixado. Uma primeira execução reuniu 9 testes novos e 44 regressões (**53 passed**, 77,44 s); após acrescentar o teste do terminal, a suíte da sessão passou **10/10** (1,21 s). `git diff --check` e compilação Python passaram. A CI do novo incremento fica pendente após publicação. A CI do baseline `7dc43da` está concluída: oito workflows aprovados e a regressão experimental condicional pulada, incluindo trajetória [38097881632](https://github.com/marceloroldao/memoria.ia/actions/runs/38097881632).

O próximo passo é executar o ciclo com operadores humanos e exemplos variados, registrando acertos, candidatas extras, ausências e efeitos de feedback incorreto. Essa avaliação ainda não foi realizada.

Uma avaliação preparatória sintética em português está registrada em [trajectory-feedback-portuguese-proof.md](trajectory-feedback-portuguese-proof.md). Ela conserva as falhas de recuperação e não substitui avaliação humana.
