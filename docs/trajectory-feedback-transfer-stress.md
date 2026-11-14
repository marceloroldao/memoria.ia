# Transferência de feedback: consultas reservadas e redundância

Continuação: [registro de hipóteses antes de observações posteriores](trajectory-prediction-audit.md), com corte temporal imutável, vínculos nativos e controles de recorrência sem confirmação factual.

Esta etapa amplia a avaliação dos leitores existentes sem mudar suas regras. `scripts/trajectory_feedback_transfer_stress.py` mede o efeito de uma oposição local ao conteúdo, de uma oposição à moldura e de uma oposição a uma ocorrência de testemunho em combinações de símbolos não usadas nas demonstrações.

São comparados retornos programados que rejeitam o extra e retornos programados que rejeitam o conteúdo esperado. Isso controla a qualidade da decisão fornecida ao sistema; **não estima a confiabilidade real de uma pessoa, fonte ou agente**. Nenhum peso ou limiar de confiança foi acrescentado ao núcleo.

## Dados e protocolo

Cada seed sorteia quatro símbolos de origem e quatro símbolos de destino disjuntos. Três demonstrações sobre pares sobrepostos ensinam uma cópia literal e uma transformação finita injetiva. Os nomes das variáveis, a transformação e a pontuação são produzidos sem LLM. Os dois formatos são:

- pergunta `Q[variável]?`, conteúdo `R[variável]=valor.`;
- pergunta `?(variável)::`, conteúdo `$(variável) -> valor!`.

Cada variável consultada tem dois conteúdos isolados previamente observados: o conteúdo que o contrato do avaliador exige e o conteúdo transformado que esse contrato considera extra. A referência oposta também é pontuada sobre a mesma leitura, para preservar que outra intenção oculta pode atribuir relevância diferente aos mesmos dados. Não há inferência de verdade factual desses rótulos.

Há três regimes de suporte:

| Regime | Demonstrações de cópia | Demonstrações de transformação |
|---|---:|---:|
| `minimal` | 3 | 3 |
| `extra_redundant` | 3 | 4 |
| `both_redundant` | 4 | 4 |

A quarta demonstração fecha o ciclo de símbolos e permite molduras alternativas que continuam cobrindo as variáveis consultadas. O regime assimétrico é deliberado: ele verifica o efeito de redundância concentrada na trajetória que o avaliador chama de extra. O regime simétrico impede interpretar esse caso como uma vantagem geral do erro sobre o acerto.

Cada experimento registra os dados em um BDR novo, consulta, aplica uma única oposição endereçada, consulta novamente, reabre o BDR e compara as leituras completas. Depois retira a oposição e confere restauração da disponibilidade e preservação do evento original. O alvo vem do endereço de origem `expected-anchor` ou `extra-anchor`; para `WITNESS`, os endereços exatos do par são derivados da evidência da moldura. O seletor recebe somente a consulta âncora, tipo de alvo e operação programada, sem referências de avaliação.

O conjunto por experimento contém uma consulta âncora, três consultas reservadas com novas combinações dos símbolos já demonstrados, uma consulta ausente composta de símbolos conhecidos e uma contendo símbolo não coberto. Nenhuma dessas perguntas é ingerida. Os conteúdos isolados já estão observados: o experimento mede recuperação e efeito do filtro, não criação de fatos novos.

Por seed: **36 experimentos, 216 ocorrências de consulta**, sendo 36 âncoras, 108 avaliações reservadas e 72 controles de ausência. São **12 textos distintos de pergunta**, dos quais seis são reservados, repetidos entre políticas, ações e regimes. Não são 216 fatos ou perguntas independentes. Os dois seeds `20270115` e `20270116` mudam alfabetos/transformações, mas preservam os mesmos dois templates; não constituem uma amostra geral de linguagem natural.

## Resultados em consultas reservadas

Cada grupo abaixo reúne as duas famílias e três consultas reservadas por família: seis avaliações. Antes do feedback, todos os grupos têm **6 esperados recuperados / 6 extras / 0 perdas**.

| Política e decisão programada | Suporte mínimo | Extra redundante | Ambos redundantes |
|---|---|---|---|
| `CONTENT`, rejeitar extra ou esperado | 6 / 6 / 0 | 6 / 6 / 0 | 6 / 6 / 0 |
| `FRAME`, rejeitar extra | 6 / 0 / 0 | 6 / 6 / 0 | 6 / 6 / 0 |
| `WITNESS`, rejeitar extra | 6 / 0 / 0 | 6 / 6 / 0 | 6 / 6 / 0 |
| `FRAME`, rejeitar esperado | 0 / 6 / 6 | 0 / 6 / 6 | 6 / 6 / 0 |
| `WITNESS`, rejeitar esperado | 0 / 6 / 6 | 0 / 6 / 6 | 6 / 6 / 0 |

Os dois seeds produzem essa mesma tabela. `CONTENT` continua afetando a consulta âncora sem transferir para as demais; a âncora foi excluída da tabela de transferência. Uma rejeição correta de moldura/testemunho ajuda quando esgota o único suporte do extra. Uma rejeição incorreta pode retirar o conteúdo esperado enquanto deixa o extra. Quando há suporte alternativo dos dois lados, uma única rejeição não elimina nenhum dos dois.

Portanto, redundância estrutural protege disponibilidade, mas não identifica qual conteúdo é correto. A preservação de um erro por outro caminho continua registrada como extra; não é contada como melhora. Apoio, frequência e quantidade de trajetórias não foram convertidos em confiança factual.

## Consequência condicional para confiabilidade

É possível derivar um limite apenas para este modelo controlado. No regime mínimo, uma decisão correta remove o único extra sem perda; uma incorreta conserva o extra e adiciona uma perda. Se `p` for uma probabilidade externa hipotética de a oposição escolher o extra, e ambos os erros tiverem custo unitário:

\[
E[\text{erros após oposição}]=2(1-p),\qquad
\text{erros sem oposição}=1.
\]

A oposição melhora essa contagem somente se `p > 1/2`. Com custo de extra \(C_E\) e custo de perda \(C_P\), a condição fica:

\[
p>\frac{C_P}{C_E+C_P}.
\]

Isso não é uma estimativa de `p`, nem um limiar implementado. Depende da configuração de um esperado/um extra, de uma decisão e dos custos escolhidos. No regime com redundância só do extra, a decisão correta não retira o extra e a incorreta ainda causa perda; o custo esperado é \(C_E+(1-p)C_P\). No regime com ambos redundantes, a disponibilidade fica igual nos casos testados. Esses contrastes mostram por que um único limiar numérico não resolve a confiabilidade a partir da estrutura observada.

## Separação do avaliador e integridade

O teste de isolamento troca todas as referências por texto exclusivo do avaliador e confirma que a operação persistida, as observações e **todas as leituras completas antes/depois permanecem iguais**. Somente os scores mudam. As referências opostas também reutilizam as mesmas leituras, sem nova operação ou treinamento.

Cada experimento confere os dez contratos: dados de aprendizado intactos, consultas sem novos eventos, leitura bruta preservada, somente a âncora endereçada, perguntas não ingeridas, saída não qualificada, ausência vazia, igualdade completa após reabertura, disponibilidade restaurada após retirada e feedback original preservado.

Ambos os seeds passaram em **360/360 verificações de integridade**. As perdas e os extras da tabela permanecem resultados de qualidade negativos; sucesso de integridade não os resolve. O primeiro marcador de barreira, composto só de pontuação (`---`), foi recusado pela ingestão estrutural nativa; o workload usa `GAP` em trilha gerada, que quebra o fluxo sem ensinar conteúdo. Nenhuma alteração de ABI foi feita e não se afirma suporte irrestrito a dados arbitrários.

## Relatórios completos e reprodução

Os relatórios preservam todos os dados brutos, operações e pacotes completos por consulta, antes/depois, além dos scores e referências exclusivos do avaliador. São JSON comprimidos sem perda. Cada um expande para cerca de 14,9 MB e ocupa cerca de 564 KB comprimido; as repetições de evidências continuam recuperáveis integralmente. O cabeçalho gzip não inclui nome de arquivo ou horário variável.

| Relatório | Digest do conteúdo, excluindo `report_content_sha256` |
|---|---|
| `trajectory-feedback-transfer-stress-development.json.gz` | `fc938a8d644ffbfacdb4526816c174cf5b90795209bbb4749d6314e2072c6d96` |
| `trajectory-feedback-transfer-stress-reserved.json.gz` | `871fe6f754f9ba8d1cdc467433a033daeef95c2f92b8a15c57384bfb437cd45b` |

Os arquivos ficam em `benchmark-results/`. A repetição local compara os arquivos finais byte a byte; a CI compara os JSON descomprimidos, sem exigir que versões diferentes de zlib produzam os mesmos bytes de compressão.

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_feedback_transfer_stress.py

PYTHONPATH=src python scripts/trajectory_feedback_transfer_stress.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --seed 20270115 --output /tmp/transfer-stress-development.json.gz
```

Para ler o relatório:

```python
import gzip, json
with gzip.open("benchmark-results/trajectory-feedback-transfer-stress-development.json.gz", "rt", encoding="utf-8") as source:
    report = json.load(source)
print(report["heldout_summary"])
```

**22 testes locais passaram:** duas verificações dos workloads, 18 combinações nativas de política/decisão/regime, isolamento do avaliador e preservação dos pacotes completos na compressão. Compilação Python e `git diff --check` passaram. Em ambiente sem biblioteca implícita, duas verificações passaram e os 20 contratos nativos foram pulados; o job nativo exige caminho explícito. O job novo `feedback-transfer-stress` compila o BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`, executa os testes, reproduz os dois seeds e compara os relatórios integrais. O resultado remoto deve ser conferido no commit publicado.

O commit anterior `a2582ba` concluiu os oito workflows aplicáveis com sucesso; o condicional foi ignorado. As políticas anteriores e seus relatórios não foram modificados nesta etapa.

## Limites e próximo problema

Este incremento é uma avaliação ampliada, não uma mudança no motor de recuperação. O parâmetro de qualidade do retorno é controlado pelo roteiro; o sistema ainda não estima se um chamador está correto. As referências representam contratos sintéticos, não verdade factual verificada. Não há participantes humanos, exemplos independentes de linguagem natural, dados multimodais, confiança calibrada ou pesos aprendidos.

Qualidade factual permanece `NOT_EVALUATED`, aprendizado geral `NOT_ESTABLISHED` e `caller_reliability_estimated=false`. A próxima etapa deve buscar observações posteriores verificáveis que possam contradizer ou confirmar uma hipótese, mantendo separadas a previsão, a evidência observada e a decisão de aprender. Não há justificativa para promover feedback declarado a fato automaticamente. O PR permanece em rascunho.
