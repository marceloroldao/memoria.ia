# Sessão de operador: console e avaliação separada

O console `scripts/trajectory_feedback_console.py` permite usar o laboratório por um menu em português, sem copiar recibos JSON. Uma consulta mostra candidatas numeradas e identifica quais estão disponíveis e quais estão vetadas. O operador escolhe explicitamente uma candidata para apoiar ou opor. A retirada usa o ID do feedback exibido na operação e preservado no histórico.

## Iniciar uma sessão

Na branch experimental do PR #374, com a biblioteca nativa compilada e o BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`:

```bash
python scripts/trajectory_feedback_console.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --data-dir /tmp/memoria-avaliacao-operador \
  --actor roldao \
  --enable-feedback
```

Use uma pasta exclusiva do laboratório e a mesma pasta para retomar depois. O console usa o lock e os limites da [interface JSONL](trajectory-feedback-lab.md). Não compartilhe essa pasta com outra ferramenta nativa. A identidade do operador é declarada; não há autenticação. Sem a opção de feedback, o menu de consulta funciona, mas apoio, oposição e retirada são recusados.

| Opção | Ação |
|---|---|
| 1 | Registrar texto, escolhendo observação do usuário ou conteúdo gerado |
| 2 | Consultar e ver as candidatas numeradas |
| 3 / 4 | Apoiar ou opor a candidata escolhida na consulta atual |
| 5 | Retirar um feedback identificado pelo seu ID |
| 6 | Consultar observações, eventos ativos/inativos e retiradas |
| 7 | Avaliar a consulta atual com referências explícitas |
| 8 | Ver o relatório agregado das avaliações salvas |
| 9 | Inspecionar o pacote integral da consulta, recibos, origens e evidências |
| 0 | Encerrar, mantendo o estado persistido |

Após registrar, dar feedback ou retirar feedback, é necessário consultar novamente antes de escolher candidata ou avaliar. Isso evita usar um painel desatualizado. A validação nativa do recibo continua ativa. O console não transforma uma candidata em resposta factual.

## Roteiro supervisionado

1. Registre observações e demonstrações escolhidas pelo operador. Não há importação automática de avaliações nem treinamento a partir das saídas.
2. Consulte. Use a opção 9 para inspecionar conteúdo, origens e evidências; uma candidata disponível pode estar errada.
3. Use a opção 7 e informe uma lista JSON dos conteúdos completos que deveriam ser recuperados, por exemplo `["A cor do drone é verde."]`. Para uma pergunta sem conteúdo esperado, use `[]`. Um conteúdo esperado ausente também pode ser informado: ele contará como perda, sem ser criado na memória.
4. Se quiser testar uma oposição, escolha a opção 4 e o número da candidata. Anote o ID exibido. Consulte e avalie novamente.
5. Feche com 0 e reabra usando a mesma pasta. Consulte para conferir persistência e examine o histórico.
6. Retire o feedback pelo ID usando a opção 5, consulte e avalie novamente. Inclua um controle em que a oposição era válida: sua retirada pode trazer o erro de volta.
7. Verifique a opção 8 e preserve tanto melhorias quanto perdas. Não escolha somente exemplos positivos.

Uma observação isolada como “Meu gato se chama Alt.” não garante recuperação para “Qual é o nome do meu gato?”. As limitações dos leitores anteriores continuam presentes. Teste perguntas sem treinamento, paráfrases, informação ausente, conflitos e conteúdo gerado. Apoio não promove candidata; retirada não decide se a oposição estava correta.

## O que o relatório mede

Cada avaliação salva a consulta, o pacote integral lido, as referências fornecidas e a identidade declarada do avaliador em `operator-reviews.jsonl`, fora do BDR. O console nunca transforma referências em observações, feedback ou pesos. É possível avaliar o mesmo pacote com referências diferentes, sem qualquer efeito na recuperação.

São comparados os conjuntos de textos das candidatas brutas e disponíveis **na mesma leitura salva**. Os números contam conteúdos recuperados por ocorrência de consulta, não fatos distintos. Há três contagens para cada conjunto:

| Campo | Interpretação relativa às referências declaradas |
|---|---|
| `true_positive` | Conteúdos esperados recuperados |
| `false_positive` | Conteúdos recuperados que não estão nas referências |
| `false_negative` | Conteúdos esperados ausentes |
| `extra_removed` | Extras brutos retirados pelo filtro |
| `expected_removed` | Conteúdos esperados retirados pelo filtro: custo da decisão |

`effect` compara a soma de extras e perdas: menos erros (`FEWER_ERRORS`), mais erros (`MORE_ERRORS`) ou a mesma contagem (`SAME_ERROR_COUNT`). O relatório também mantém as contagens separadas; igualdade no total pode esconder uma troca de erro por perda. Avaliações repetidas entram novamente no agregado; não há deduplicação de fatos, teste estatístico ou estimativa de acurácia geral.

A comparação mede o efeito do filtro naquele pacote. Não compara automaticamente dois momentos com estados diferentes de memória, não prova ganho causal de aprendizado e não decide a validade das referências. Como o operador vê as candidatas antes de avaliar, este protocolo é exploratório e não cego. Para um estudo controlado, as referências e o conjunto de consultas devem ser definidos previamente e analisados fora do aprendizado.

O arquivo acrescenta avaliações com sequência e checksum encadeado, confirma gravação com `fsync` e é relido com recálculo de métricas. Uma linha parcial ou inconsistente é recusada. Os checksums detectam alterações acidentais; não autenticam o avaliador nem impedem reescrita completa ou remoção do final. Não há transação entre o BDR e o arquivo de avaliações. Uma falha ao salvar avaliação não desfaz operações nativas anteriores. O arquivo contém textos e evidências da sessão, portanto é privado por padrão.

O relatório marca `reference_source=CALLER_SUPPLIED` nas avaliações, `human_participation=NOT_VERIFIED` e `factual_quality_status=NOT_EVALUATED`. Nenhuma participação humana foi presumida ou simulada como real.

## Validação automatizada e situação

Dez testes novos passaram. Eles cobrem rótulos divergentes sem aprendizado, ausência com perda registrada, referências inválidas, veto correto e incorreto, retirada, persistência das avaliações, journal adulterado/truncado, menu com recibos exatos, exigência de nova consulta e reinício da CLI em processos distintos. Os oito testes anteriores da interface também passaram, assim como as 44 regressões de ledger, veto, continuidade e retirada: **62 testes locais aprovados**. Compilação Python e `git diff --check` passaram.

Os participantes dos testes são entradas programadas identificadas como `scripted-test`; isso não é avaliação humana. As métricas demonstram que o instrumento registra os efeitos previstos nesses casos, incluindo piora deliberada. Nenhuma melhora factual geral ou generalização semântica foi demonstrada.

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_trajectory_feedback_console.py \
  tests/test_trajectory_feedback_lab.py
```

A CI incorpora a suíte do console. O PR continua em rascunho; o resultado remoto deve ser consultado para o commit publicado. Próxima dependência: executar uma sessão real com o operador e analisar o arquivo produzido, sem incorporar referências de avaliação ao aprendizado.
