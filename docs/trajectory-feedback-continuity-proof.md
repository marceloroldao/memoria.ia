# Continuidade de feedback com evidências idênticas

O novo laboratório permite transportar uma oposição histórica através de uma mudança de snapshot quando a consulta, região, candidata e suas evidências permanecem integralmente iguais. Isso evita perder o veto por uma observação isolada sem relação com a recuperação. A política anterior de recibo exato continua disponível e inalterada; ambas ficam desativadas por padrão e não foram integradas ao MVP.

É continuidade de uma decisão explícita, não aprendizado de uma regra geral. Feedback incorreto também pode persistir. Mudança de intenção ou relevância não é reconhecida semanticamente.

## Como a evidência é verificada

A comparação exige igualdade canônica do texto e payload da candidata, todas as suas origens, IDs das molduras, pares de testemunhos e evidências por rota. Além disso, compara o texto e **todas as origens nativas dos payloads dos testemunhos**, não somente seus hashes. Uma ocorrência nova de testemunho pode deixar o pacote da candidata igual e ainda assim impedir a continuidade.

O recibo histórico original contém hashes da janela projetada e da leitura completa, mas não carrega diretamente toda a proveniência dos testemunhos. Para verificá-la, o laboratório procura um prefixo da janela bruta atual com o hash daquele snapshot. Reconstrói a leitura desse prefixo, exige igualdade de seu hash com o recibo histórico e encontra a candidata inteira correspondente. A proveniência reconstruída deve coincidir com a atual. Sem prefixo recuperável, sem leitura reproduzível ou com proveniência diferente, não transporta o veto.

O procedimento pressupõe histórico append-only, único escritor serializado e o contrato atual dos cinco campos projetados. Não é uma transação atômica entre janelas. A busca de prefixos recalcula hashes e leituras históricas; é um procedimento de laboratório, sem garantia de custo constante, escala ou eficiência em produção.

Cada decisão expõe o recibo atual, identidade de evidência, eventos completos e seu tipo de correspondência: `EXACT_RECEIPT` ou `IDENTICAL_CANDIDATE_EVIDENCE`. Inclui o prefixo histórico validado, digest da leitura e proveniência dos testemunhos. A distinção evita apresentar um evento antigo como se tivesse sido dado no snapshot atual.

Uma oposição continua suficiente para suspender a candidata. Apoio em um recibo atual não anula oposição histórica compatível; ambos ficam `DISPUTED`. Não há maioria, pesos, confiança factual ou autenticação dos chamadores. O histórico é preservado, e novas consultas, regiões ou candidatas não recebem o veto automaticamente.

O envelope mantém `answer=null`, `proposal_payload_id=null`, `selected_target=null`, `qualified=false` e `selection_used=false`. A filtragem é explícita em `candidate_filter_used`. `raw_view` preserva todas as candidatas, propostas brutas, molduras e proveniência, inclusive as candidatas suspensas.

## Resultados positivos e negativos

Desenvolvimento `20270105` e reservado `20270106`: seis cenários em símbolos legíveis e em renomeação injetiva, totalizando doze experimentos por seed. Os sinais são operações explícitas programadas e escolhem alvos por endereço de origem. As referências do avaliador entram somente na pontuação depois das operações.

| Mudança após registrar oposição | Gate anterior: esperados / extras / perdas | Continuidade: esperados / extras / perdas | Resultado |
|---|---|---|---|
| Observação de usuário isolada, evidência igual | 1 / 1 / 0 | 1 / 0 / 0 | Veto da candidata extra sobrevive |
| Barreira gerada posterior, evidência igual | 1 / 1 / 0 | 1 / 0 / 0 | Veto sobrevive sem aprender conteúdo gerado |
| Nova ocorrência da candidata extra | 1 / 1 / 0 | 1 / 1 / 0 | Proveniência mudou; veto não é transportado |
| Nova candidata concorrente | 1 / 2 / 0 | 1 / 1 / 0 | Veto antigo permanece, candidata nova continua extra |
| Oposição indevida à candidata correta | 1 / 0 / 0 | 0 / 0 / 1 | Continuidade mantém uma perda indevida |
| Gêmeo com relevância diferente oculta no avaliador | 1 / 1 / 0 | 0 / 1 / 1 | Mesmas entradas/feedback não distinguem outra intenção |

Os dois primeiros cenários demonstram o efeito procurado, dentro do contrato restrito. O quarto demonstra redução de um extra, sem resolver o extra novo. O terceiro revela o preço da política conservadora: mesmo repetição do conteúdo já rejeitado muda as origens e torna o veto inaplicável. O quinto mostra que persistir correção não significa corrigir verdade.

O sexto usa exatamente as mesmas observações, append, consulta, recibo inicial e eventos do primeiro, mas muda somente a referência oculta do avaliador. As leituras completas são idênticas nos dois casos. Não houve uma mudança de intenção expressa que o sistema pudesse aprender: o controle demonstra que identidade estrutural não basta para garantir relevância sob intenção oculta. O relatório registra `semantic_context_status=FAIL_INDISTINGUISHABLE_INPUTS`, não interpretação factual ou compreensão de contexto.

Em ambos os seeds passaram **175/175 verificações de integridade**. Os resultados coincidem sob renomeação. Quatro cenários por modo verificam as três outras consultas: **24 controles de comportamento por seed** mantêm leitura bruta, listas e estados iguais. Seus recibos atuais mudam legitimamente com o snapshot, por isso não exigimos identidade desses IDs. Nos cenários que acrescentam conteúdo recuperável, as outras consultas são verificadas quanto à ausência de herança do feedback.

Os **80 testes anteriores de regressão passaram**. As verificações finais passaram nos **10 testes novos**, incluindo reabertura, ocorrência nova da candidata, nova rota na mesma raiz, nova ocorrência de testemunho com pacote de candidata idêntico, apoio atual contra oposição histórica, escopo/consulta, modo desativado, falta de prefixo histórico recuperável e proveniência divergente. Nenhuma alteração foi necessária nos leitores ou no ledger anteriores.

Os dois relatórios completos foram repetidos e coincidiram byte a byte. Arquivos: `benchmark-results/trajectory-feedback-continuity-{development,reserved}.json`. Preservam observações, append, recibo inicial, candidatas anteriores, leitura posterior completa, eventos, provas históricas e scores separados. O digest anterior e as observações permitem reproduzir a leitura inicial. O campo `report_content_sha256` exclui seu próprio valor no cálculo.

| Relatório | SHA-256 |
|---|---|
| Desenvolvimento | `760e8c2618fc4ef0f0cde7bdf97279c05a9bac0e545f49b588b8db33ebaf8f87` |
| Reservado | `d251f70d7a2011e8d236ad0b37125fc5c196576471fa0c4a7ceedbbb925e26c0` |

## Limites e próxima dependência

Continuidade não aprende por que uma rota está errada. Não transfere a oposição para perguntas equivalentes, novos payloads, novas ocorrências ou novas rotas. Não gera o conteúdo ausente, não reconhece mudança legítima de intenção e não oferece revogação explícita de feedback. Uma oposição injustificada pode persistir indefinidamente enquanto suas evidências ficarem iguais.

`general_learning_status=NOT_ESTABLISHED` e qualidade factual permanecem `NOT_EVALUATED`. Os exemplos são pequenos e correlacionados; não demonstram inteligência geral, recuperação universal ou desempenho operacional. Os resultados negativos anteriores continuam válidos, inclusive erros de transformação, conteúdos extras, perdas e gêmeos de relevância indistinguíveis.

A próxima dependência é tornar a retirada ou substituição de um feedback uma operação explícita, endereçada e auditável, com testes de reversão de veto incorreto. Depois será possível investigar generalização de penalizações estruturais com controle de regressões; manter um veto histórico não comprova essa generalização.

## Reprodução e CI

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_feedback_continuity_probe.py

python scripts/trajectory_feedback_continuity_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --seed 20270105 --output /tmp/feedback-continuity-development.json
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. O commit anterior `8ddc632` passou nos oito workflows aplicáveis, incluindo trajetória no run `38094045735`; workflow condicional ignorado. A CI inclui os testes e ambos os seeds deste incremento, pendentes até executar remotamente. Núcleo estável, ABI, seletores padrão, MVP e PR draft permanecem preservados.

Atualização de CI: `385dd22` passou em sete workflows, mas trajetória no run `38095264122` terminou cancelada por atingir o limite de 25 minutos do job `native-bridge`. O job `proof` passou. As etapas de ledger, veto e continuidade passaram, incluindo esta suíte e ambos os seeds; o cancelamento ocorreu depois, na etapa antiga de filtros contextuais, e impediu a etapa seguinte. A execução integral não está aprovada. O incremento de retirada amplia o limite para 40 minutos e mantém o cancelamento documentado.
