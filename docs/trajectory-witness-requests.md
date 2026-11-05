# Propor a observação que falta a uma hipótese

O experimento anterior mostrou duas regras possíveis compatíveis com as mesmas observações: o mapa de um símbolo poderia ser compartilhado ou mudar entre escritas. O novo componente propõe um exemplo que contenha esse símbolo na nova escrita, sem fornecer resposta esperada, disparar uma solicitação ou registrar conteúdo na memória.

**No corpus sintético, uma resposta adequada ao pedido permite ao leitor padrão recuperar 32/32 consultas nos dois cenários. Uma resposta declarada incorreta também pode ensinar uma rota, mas produz 0/32 acertos, com conteúdo extra e conteúdo esperado ausente. A proposta identifica uma lacuna; não verifica verdade.**

## Como a proposta é construída

`trajectory_witness_requests.propose(rows, region, query)` consulta as hipóteses isoladas de [reaproveitamento de mapas](trajectory-borrowed-map.md). Para cada par ainda não testemunhado na nova escrita, procura uma pergunta testemunhada na moldura doadora cuja variável contenha o símbolo necessário. Constrói outra pergunta usando essa variável e os prefixos/limites da nova escrita.

A pergunta de avaliação e textos já observados de origem admissível são excluídos das propostas. A solicitação conserva seu identificador, os símbolos necessários, os endereços das perguntas doadoras e os IDs das rotas relacionadas. Não inclui `target_text`, gabarito, valor esperado ou resposta sugerida. `source_kind=constructed_request` marca a pergunta construída como solicitação; ela não é uma observação.

Pedidos iguais são agrupados e retornam IDs estáveis. `request_dispatched=false`, `observations_recorded=false` e `learning_performed=false` permanecem explícitos. O componente não recebe respostas nem as incorpora. Não altera a sessão, o assistente, o leitor padrão, a ABI ou os serviços de produto. Não implementa curiosidade autônoma no dispositivo ou no servidor.

Uma proposta cobre símbolos ausentes; não é garantia de que uma resposta será informativa ou correta. Pode não haver proposta quando o laboratório não produz uma hipótese emprestada ou não consegue construir outro exemplo a partir dos testemunhos disponíveis.

## Teste com respostas programadas

São reutilizados os mesmos dois mapas e domínios sintéticos, com caixa alta e uma paráfrase fixa. Para cada contexto, os dois cenários começam com observações e consultas idênticas e diferem somente na referência do avaliador para o símbolo ainda não testemunhado. O pedido é construído antes da resposta e verificado como igual nos dois cenários.

O avaliador então executa uma das cinco condições, em memórias separadas:

| Resposta programada | Recuperação exata das novas consultas | Controles de ausência |
|---|---:|---:|
| Nenhuma resposta | 0/32 | 80/80 |
| Par adequado, declarado como observado | **32/32** | 80/80 |
| Mesmo tipo de par, marcado como gerado | 0/32 | 80/80 |
| Relato sem vínculo com o pedido | 0/32 | 80/80 |
| Par observado com mapa incorreto | **0/32** | 80/80 |

O avaliador registra os pares explicitamente por `observe`, depois da construção do pedido. É uma simulação programada de resposta, sem operador real ou consulta a serviço externo. Nenhuma das perguntas-alvo ou dos fatos-alvo é usada no par adicional; o exemplo tem outra entidade e outro valor. Os fatos-alvo e as alternativas já estavam registrados.

A recuperação posterior usa `FeedbackSession.query`, com o leitor padrão anterior. As duas âncoras já existentes mais o novo par fornecem os três testemunhos exigidos pelo algoritmo. Essa transferência após testemunho explícito não estabelece entendimento de outras paráfrases inéditas.

No controle incorreto, há **32 hipóteses/candidatas extras e 32 conteúdos esperados ausentes**. O pedido deixa de ser produzido depois de um par admissível ou de um veto à hipótese antiga, inclusive com observação incorreta; isso não significa verificação factual. Conteúdo gerado, relato irrelevante e ausência de resposta mantêm o pedido pendente.

## Falha encontrada durante o desenvolvimento

A primeira execução considerava qualquer texto já registrado ao excluir exemplos repetidos. Assim, uma resposta gerada podia suprimir o pedido mesmo sem entrar na aprendizagem: isso ocorreu nos 16 contextos dessa condição. Os controles de persistência passavam, mas ainda não cobriam essa semântica.

A exclusão agora considera somente origens admissíveis (`user_turn` e `user_assertion`). O teste de conteúdo gerado exige que o pedido original permaneça igual depois de fechar e reabrir a memória. O avaliador também passou a verificar o estado pendente de cada condição. A evidência negativa original foi preservada em `benchmark-results/trajectory-witness-generated-filter-regression.json`.

## Execução e limites

```sh
PYTHONPATH=src python scripts/trajectory_witness_requests_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output /tmp/witness-requests.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m unittest discover -s tests -p test_trajectory_witness_requests.py -v
```

O workflow retorna sucesso quando a integridade passa, mantendo as falhas do controle de observação incorreta no relatório. Nenhuma resposta factual é selecionada ou qualificada. O histórico e a leitura completa são conferidos depois de reabrir o armazenamento nativo; as consultas não acrescentam observações.

Passaram **oito testes novos e 1080 verificações de integridade**, em **80 memórias novas e 560 casos de consulta**, com leituras antes, depois e após reabrir. O relatório completo está em `benchmark-results/trajectory-witness-requests.json`; versões, hashes, comandos de compilação e resultados de testes estão em `benchmark-results/trajectory-witness-requests-validation.json`.

Após a recuperação do ambiente, 138 arquivos de origem foram conferidos com seus blobs Git da revisão publicada e 20 arquivos do BDR com o commit fixado. A biblioteca usada nesta rodada foi reconstruída diretamente com o compilador a partir das listas de fontes dos alvos CMake, porque CMake não estava disponível localmente. Isso não revalida o preparador CMake. As suítes pytest anteriores não foram repetidas; os oito testes desta etapa usam unittest e a rodada completa usa persistência nativa real. Compilação Python e `git diff --check` passaram.

A CI da revisão anterior `3ba4d7b2` concluiu com sucesso, execução `41313828007`. A CI deste incremento permanece pendente após publicação.

É uma intervenção posterior ao diagnóstico, com duas sementes e domínios correlacionados. Os cenários pareados não são amostras independentes de precisão geral. A execução combina leitor Python e persistência nativa BDR; não houve avaliação humana, validação de produção, medição de escala ou prova de aprendizagem geral. Conferir a origem e a confiabilidade de novas observações continua sendo uma necessidade separada.
