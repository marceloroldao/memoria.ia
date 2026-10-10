# Veto por feedback endereçado: efeito local e controles negativos

O laboratório agora pode usar o feedback persistido para suspender a reutilização de uma candidata na mesma consulta e no mesmo snapshot. Uma oposição explícita basta para o veto. Apoios não anulam oposição, não qualificam fatos nem criam candidatas. O recurso fica desativado por padrão em `gated_read(..., enabled=False)` e não foi integrado ao MVP, UI ou núcleo estável.

Este incremento demonstra mudança de comportamento por uma regra explícita e local. Não demonstra aprendizado de uma penalidade estrutural, transferência para outras consultas ou compreensão da correção.

## Política e rastreabilidade

O leitor original continua intacto em `raw_view`: todas as candidatas, propostas brutas, molduras, testemunhos e origens são preservadas. A política cria duas listas separadas, `available_candidates` e `withheld_candidates`, e decisões com os eventos completos que as justificam. Disponibilidade significa apenas ausência de veto; não significa relevância ou verdade. O envelope externo mantém resposta, seleção e proposta nulas, `qualified=false` e `factual_quality_status=NOT_EVALUATED`. `candidate_filter_used` expõe quando houve filtragem.

| Eventos para o recibo integral atual | Estado | Reutilização |
|---|---|---|
| Nenhum | `NO_FEEDBACK` | Candidata disponível, sem qualificação |
| Somente apoio | `SUPPORTED` | Candidata disponível, sem promoção |
| Somente oposição | `OPPOSED` | Candidata suspensa |
| Apoio e oposição | `DISPUTED` | Candidata suspensa; todos os sinais preservados |

O veto exige igualdade integral do recibo: região, consulta exata, snapshot projetado, digest da leitura, candidata e evidências. Nem consulta semelhante, região diferente, nova observação ou barreira gerada posterior herdam a oposição. O histórico continua disponível no ledger. Reabertura restaura o veto enquanto o recibo ainda corresponde à memória atual. Reenvio do mesmo evento não acrescenta ocorrências nem altera a decisão.

Não há votação por frequência. O cenário completo inclui três apoios contra uma oposição; o teste específico inclui vinte apoios contra uma oposição. Ambos permanecem `DISPUTED` e suspensos. Identidades são fornecidas pelo chamador, sem autenticação ou atribuição de confiabilidade.

## Experimentos positivos e negativos

Desenvolvimento `20270103` e reservado `20270104`: quatro cenários, em símbolos legíveis e em renomeação injetiva, totalizando oito experimentos por seed. Os retornos são operações explícitas programadas: o alvo é escolhido por endereço de origem observado, não pelo texto esperado do avaliador. Referências entram somente na avaliação final, após leituras, feedback, controles e reabertura.

| Cenário | Antes: esperados / extras / perdas | Depois: esperados / extras / perdas | Interpretação |
|---|---|---|---|
| Rejeitar a candidata extra | 1 / 1 / 0 | 1 / 0 / 0 | Correção local do conjunto reutilizável |
| Rejeitar a candidata correta | 1 / 0 / 0 | 0 / 0 / 1 | Feedback incorreto cria uma perda |
| Rejeitar extra e receber três apoios nela | 1 / 1 / 0 | 1 / 0 / 0 | Suspensão cautelosa preserva a disputa; não decide verdade |
| Apoiar a candidata da transformação errada | 0 / 1 / 1 | 0 / 1 / 1 | Apoio não corrige a recuperação nem recupera o conteúdo ausente |

Os resultados coincidem em ambos os seeds e sob renomeação. Há duas melhorias locais, uma regressão e um resultado errado inalterado por grupo de quatro cenários. Essa bateria pequena e correlacionada não estima precisão em uso real. O cenário disputado ter resultado correto segundo o avaliador não demonstra que vetar toda oposição seja uma política universalmente boa.

Cada cenário verifica as três outras consultas da fixture sem mudanças: **24 controles por seed**. Também verifica preservação completa da leitura bruta, ausência de gravação durante consulta, comportamento desativado, reenvio idempotente, reabertura, expiração após append e preservação do ledger. Passaram **113/113 verificações de integridade por seed**. A suíte anterior de 73 testes e os sete testes novos foram usados na regressão; o teste de variação de consulta foi corrigido para usar um prefixo admitido pelo leitor, pois espaço final muda a cobertura estrutural existente.

Relatórios completos em JSON compacto, sem remoção de evidências: `benchmark-results/trajectory-feedback-gate-{development,reserved}.json`. Ambos foram reproduzidos. O campo `report_content_sha256` é calculado sobre o objeto canônico antes de acrescentar esse próprio campo:

| Relatório | SHA-256 |
|---|---|
| Desenvolvimento | `038069630e234162b1823ef1d20070e7c426494a6d506a42401b1faffd98e1c0` |
| Reservado | `96cdaef2de1d88883852567a8eaafea4fc57a12484b0d34e9b315ebd59f5d99d` |

## O que continua faltando

O erro bruto permanece em `raw_view`; o veto impede reutilização somente no recibo exato. O sistema não descobriu por que uma rota estava errada nem aprendeu a evitar uma nova instância do mesmo padrão. Não adiciona o conteúdo correto quando ele está ausente. Um append irrelevante também expira o veto e pode tornar a candidata novamente disponível. Feedback indevido bloqueia conteúdo correto, como mostra o controle negativo.

Não há pesos incrementais, penalização aprendida de rota, revogação de um evento, transferência semântica, reconhecimento de feedback em linguagem natural, autenticação ou política factual. `general_learning_status=NOT_ESTABLISHED`. O fluxo exige um único escritor serializado pelo chamador e não oferece transação atômica entre memória e ledger. Nenhuma melhoria de escala, linguagem geral ou AGI foi demonstrada.

Os resultados negativos anteriores continuam válidos: extras e perdas na recuperação composta, 16/20 extras sem divergência e gêmeos de relevância indistinguíveis. A etapa seguinte deve investigar quando uma correção pode atravessar mudanças de snapshot sem contaminar outras consultas, com testes explícitos de feedback incorreto, mudança legítima de contexto e regressões. Só depois haverá base para investigar penalizações estruturais generalizáveis.

## Reprodução e CI

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_feedback_gate_probe.py

python scripts/trajectory_feedback_gate_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --seed 20270103 --output /tmp/feedback-gate-development.json
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. O commit `8ddc632` passou nos oito workflows aplicáveis, incluindo trajetória no run `38094045735` com estes testes e ambos os seeds. O anterior `afee837` também passou, incluindo trajetória no run `38088721518`; workflow condicional ignorado. O PR permanece draft; baseline, seletores padrão, ABI e MVP permanecem preservados.
