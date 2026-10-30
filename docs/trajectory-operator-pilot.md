# Piloto local: consolidação e avaliação com operador

Este é um roteiro de execução do laboratório, com registro das limitações e da correção de recuperação após interrupção. Não representa uma avaliação humana já realizada nem uma versão estável publicada.

## Correção encontrada na consolidação

A retomada anterior conferia IDs, conteúdo, origem e limites. Porém, podia acrescentar os pares restantes mesmo quando uma observação havia sido inserida entre os registros do lote interrompido ou quando já existia um registro posterior sem o prefixo inicial. Isso preservava IDs sem preservar a sequência prevista de pergunta/conteúdo.

Três testes reproduziram a falha no estado anterior: contexto depois do trecho parcial, contexto no meio de registros do lote e presença de um registro sem seu prefixo. Antes da correção, os três testes falharam porque a continuação não era recusada. Esse histórico negativo permanece documentado; os relatórios antigos não foram reescritos.

O preparo do lote agora exige que os IDs já existentes:

- apareçam exatamente uma vez, com conteúdo e origem esperados;
- formem um prefixo do plano, na ordem original e sem registros intercalados;
- terminem a região local quando ainda houver registros pendentes.

Uma situação ambígua é recusada antes de novas observações. Os recibos, a decisão e as entradas anteriores permanecem preservados. A correção não cria um rollback, não reordena o passado e não transforma uma incorporação em transação de lote.

Os testes simulam falha antes de cada uma das três operações de um par (origem, conteúdo e barreira) e perda de resposta depois do flush de cada uma. Fecham e reabrem o armazenamento e retomam a decisão. Esses seis casos verificam prefixo preservado, ausência de duplicação e resultado persistente. São falhas injetadas na camada Python antes da chamada ou depois do flush, não testes de queda de energia ou interrupção durante uma gravação nativa.

Outros testes cobrem os três históricos ambíguos e o reenvio de um lote completo após contexto posterior. O percurso normal do assistente continua reproduzindo o relatório anterior byte a byte.

## Preparar a rodada

Para conferir ferramentas, compilar com a dependência fixada e abrir o assistente sem configurar `PYTHONPATH` manualmente, use [trajectory-operator-setup.md](trajectory-operator-setup.md). O comando direto abaixo continua disponível para bibliotecas já preparadas.

Use o código da branch `feat/feedback-withdrawal-continuity` e a biblioteca construída com o BDR fixado nas instruções de `trajectory-feedback-session.md`. Para abrir o assistente:

```sh
PYTHONPATH=src python scripts/trajectory_review_wizard.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --data-dir ./data/piloto-operador \
  --scope piloto_marcelo \
  --actor marcelo
```

A identidade e a proveniência são declaradas, sem autenticação. Escolha observações cuja origem possa conferir fora do sistema. Use a opção de origem gerada quando o conteúdo tiver sido produzido por assistente. A marcação estrutural não substitui essa conferência.

As observações e demonstrações devem permanecer dentro dos limites do laboratório: 64 observações e 4096 caracteres por escopo. Cada conjunto acrescentado explicitamente inclui pares e barreiras de sequência. Este roteiro não orienta instalar o experimento sobre o serviço de produção.

## Percursos para observar

| Percurso | O que fazer | O que registrar |
|---|---|---|
| Informação conhecida | Registrar conteúdo de origem conhecida, consultar e inspecionar candidatas/origens | Se atende à pergunta, se falta demonstração de uma moldura e onde aparece informação extra |
| Informação não observada | Perguntar por atributo ou entidade não informados | Lista vazia ou conteúdo inadequado; preservar o caso como falha se houver excesso |
| Alternativas concorrentes | Registrar conteúdos distintos sobre o mesmo assunto | Se ambas as origens ficam visíveis e se a leitura permite decidir ou mantém dúvida |
| Demonstração explícita | Oferecer exemplos de origem conhecida, escolher ou adiar, registrar separadamente se decidir | O motivo da escolha, as diferenças antes/depois e a avaliação declarada |
| Conteúdo gerado | Identificar a origem como gerada ao registrar | Preservação no histórico e exclusão da aprendizagem |
| Retomada | Usar a opção de registrar resultado depois, sair normalmente e reabrir | Mesma decisão, nenhuma duplicação e vínculo ao recibo original |

Não é necessário forçar uma escolha: adiamento, rejeição e dúvida são resultados válidos da rodada. Mais candidatas não é, por si só, melhora. Se não houver rotas suficientes, o sistema pode permanecer sem resolver; registre isso em vez de inventar conteúdo ou tratar recuperação associativa como resposta factual.

## Evidência da rodada

O protocolo preserva a pergunta, os conjuntos oferecidos e sua origem declarada, a revisão exata, a decisão, o motivo e o resultado posterior. Confira as entradas e decisões pelo menu. As operações `review_decisions` e `review_outcomes` continuam disponíveis para auditoria detalhada.

Registre também as dificuldades de uso na justificativa: falta de clareza, excesso de etapas, dificuldade para conferir uma origem, marcação que não ajudou ou exemplo útil sem marcação. Não altere o histórico para remover tentativas malsucedidas. Não atribua utilidade humana com base somente nos testes programados.

O diário de resultados compara recibos escolhidos explicitamente e preserva a avaliação do operador. Ele não verifica que a demonstração escolhida foi a causa da mudança, que os exemplos foram incorporados corretamente ou que os conteúdos são verdadeiros.

## Validação cumulativa

O relatório de consolidação é `benchmark-results/trajectory-operator-pilot-regression.json`. Ele registra os testes de ledger, veto, continuidade, retirada, sessão, rastreamento, diagnóstico, revisão de demonstrações, decisões, resultados, assistente de terminal e recuperação após falhas simuladas. Conserva a lista de casos, a identidade do binário nativo e os hashes dos arquivos diretamente envolvidos na correção.

O relatório é derivado de JUnit de uma execução real. Durações são medições dessa execução; não há promessa de reprodução byte a byte para esse relatório de tempos. O relatório determinístico do percurso normal do assistente é preservado separadamente.

Resultado local: **136/136 testes aprovados**, sem falhas, erros ou testes pulados, em cerca de **159 segundos** na execução. São 126 regressões existentes e dez testes novos de falhas/retomada. Antes da correção, a seleção cumulativa antiga passou 126/126, enquanto os três testes novos de histórico ambíguo reproduziram a falha. Depois da correção, os dez testes novos e os 126 anteriores passaram juntos. Compilação Python e `git diff --check` passaram.

Na consulta de CI feita nesta consolidação, os commits `43f117a1`, `e3220321`, `84b733d2`, `d2ae7fa0` e `3d7c1d71` já tinham concluído a CI de trajetória com sucesso. `b604422a` e `50fba048` estavam em execução; isso não foi apresentado como aprovação. A CI do novo incremento fica pendente após publicação.

Esta consolidação mantém o PR #382 em rascunho. Avaliação humana, uso em produção, versão estável e validação de aprendizagem geral permanecem pendentes. O próximo passo depende das evidências produzidas pela rodada real: corrigir dificuldades observadas ou avançar no motor quando houver casos que demonstrem a necessidade.
