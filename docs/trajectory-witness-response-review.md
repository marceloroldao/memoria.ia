# Resposta recebida primeiro em revisão durável

O novo fluxo conecta os [pedidos de testemunho](trajectory-witness-requests.md) ao diário de revisão já existente. Uma resposta recebida fica preservada com o pedido, a pergunta de avaliação, o conteúdo do exemplo, sua origem declarada e a revisão daquele estado. Não é incorporada automaticamente à região de aprendizagem.

No assistente local, a opção **[7] revisar resposta a pedido** permite realizar esse percurso sem JSON manual ou cópia do ID do pedido. A revisão continua oferecendo seleção, adiamento e rejeição, com justificativa. Uma seleção registra a escolha do operador; a incorporação continua sendo outra ação explícita.

## Vínculo e persistência

`open_response(session, scope, query, request_id, response_text, source_kind)` reconstrói os pedidos atuais a partir do histórico do escopo e recusa um ID que não esteja disponível para aquela consulta. A resposta deve ser texto não vazio de até 2000 caracteres, com origem explícita `user_turn` ou `assistant_generated`.

O par oferecido contém a pergunta construída do pedido e a resposta recebida. O campo de proveniência usa a convenção `witness-response-v1|request_id|source_kind|request_sha256`, dentro do limite anterior de 256 caracteres. O identificador da oferta depende desses campos e dos dois textos. O recibo de revisão preserva a oferta exata e o estado da leitura. O JSON completo da proposta não é duplicado no recibo: ficam preservados seu ID, seu hash, a pergunta construída e a origem da resposta.

É uma convenção validada sobre o formato anterior de ofertas, sem novo codec ou diário nativo. Os hashes conferem consistência do vínculo e não autenticam quem declarou a origem. Uma resposta diferente ou outra origem declarada gera outra oferta; não substitui o recibo anterior.

No mesmo estado de aprendizagem, reabrir a mesma resposta retorna o recibo existente (`EXACT_REPLAY`), inclusive depois de fechar e reabrir o armazenamento. Uma mudança de estado exige nova revisão antes de registrar uma nova decisão com um recibo antigo. A retomada de decisões históricas continua seguindo o protocolo anterior e preserva seu recibo original.

## Origem gerada e ação separada

O assistente mostra a origem em linguagem legível, sem exigir que o operador interprete o marcador de proveniência. Para uma resposta declarada como gerada, oferece somente registrar como gerada ou pular. O preparo da incorporação também valida o vínculo e recusa a troca para observação de usuário, antes de qualquer `observe`, tanto na primeira incorporação quanto na retomada.

Se o operador decidir registrar o conteúdo gerado, o par e sua barreira permanecem gerados e excluídos da aprendizagem. O pedido continua pendente nos casos testados. A proteção se aplica ao fluxo identificado de resposta a pedido e não autentica entradas manuais ou impede que alguém declare uma origem falsa fora dele.

Para uma resposta declarada como observação, a escolha do conjunto não a incorpora. O registro explícito posterior ainda pode ensinar uma rota incorreta se o conteúdo estiver errado. O teste mantém esse resultado negativo: duas consultas acabam com uma candidata extra e um conteúdo esperado ausente em cada uma, após a incorporação explícita de uma resposta incorreta. O fluxo controla a ação e conserva sua proveniência; não verifica a verdade da observação.

## Avaliação da auditoria

Foram executadas **72 rodadas em memórias novas**: duas sementes sintéticas, caixa alta e uma paráfrase, dois cenários de mapa, três tipos de resposta e três decisões. O domínio desta rodada é umidade; são dados reutilizados após diagnóstico, sem amostras independentes de precisão geral.

| Resposta recebida | Decisões testadas | Respostas preservadas | Exemplos incorporados na matriz |
|---|---|---:|---:|
| Adequada, declarada como observação | Selecionar, adiar e rejeitar | 24 | 0 |
| Incorreta, declarada como observação | Selecionar, adiar e rejeitar | 24 | 0 |
| Declarada como gerada | Selecionar, adiar e rejeitar | 24 | 0 |

Cada rodada registra também um resultado programado como incerto, comparando o mesmo recibo antes/depois porque não houve incorporação. Não representa avaliação humana ou melhora. O histórico de aprendizagem, as leituras completas das consultas e o pedido pendente permanecem iguais, e o escopo estrangeiro fica preservado.

Passaram **1168 verificações de integridade**: vínculo do pedido, texto e origem, decisão e avaliação declaradas, ausência de aprendizagem, reenvio idempotente e igualdade de auditoria/leituras após reiniciar. Oito casos com resposta gerada e seleção verificam adicionalmente o veto à incorporação como observação antes de qualquer escrita de aprendizagem.

Passaram **16 testes unittest**, oito novos e oito regressões dos pedidos. Incluem recibo estável após reinício, decisões sem aprendizagem, entradas inválidas sem auditoria nova, recibo obsoleto, inconsistência de metadados/conteúdo, proteção da origem na primeira aplicação e na retomada, aplicação explícita de observação incorreta e um percurso real do terminal.

Os oito percursos anteriores do assistente passaram nas **72 verificações** existentes, comparados ao controlador da revisão publicada. Auditorias e linhas de saída permaneceram iguais. O prompt do menu mudou para incluir a opção 7; o relatório completo antigo não foi reescrito. Essas verificações se sobrepõem aos demais testes e não devem ser somadas como evidência independente de qualidade.

## Reproduzir e interpretar

```sh
PYTHONPATH=src python scripts/trajectory_witness_response_review_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output /tmp/witness-response-review.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m unittest discover -s tests -p test_trajectory_witness_response_review.py -v
```

Relatórios: `benchmark-results/trajectory-witness-response-review.json` e `benchmark-results/trajectory-witness-response-review-validation.json`. Compilação Python e `git diff --check` passaram. A execução usa a biblioteca nativa recuperada e verificada na etapa anterior, sem alteração da ABI ou do motor. As suítes pytest anteriores não foram repetidas localmente nesta rodada. A CI do incremento fica pendente após publicação.

A CI da revisão anterior `0924a3da` concluiu com sucesso na execução `42130923709`.

O sucesso da auditoria não aprova respostas factuais, aprendizagem geral, facilidade de uso por pessoas, escala ou produção. As respostas são programadas e a identidade do operador é declarada. A proposta de testemunho continua sem enviar solicitações a serviços externos.
