# Inferência de relações sem `reply_to`

Continuação de `5f921e9`, cujos sete workflows aplicáveis passaram, incluindo trajetória `37644341652`. Este incremento compara três regras diagnósticas de inferência com referências de relações mantidas exclusivamente no avaliador. Acrescenta script, oito testes, dois resumos e passo de CI; mantém o PR #374 em rascunho e os seletores/runtime anteriores intactos.

## Entrada, regras e proveniência

`inferred_relations(rows, region, query)` recebe observações e uma região/consulta bruta explícitas. Antes de adaptar ou aprender, copia somente `hierarchy_id`, `source_id`, `sequence`, `text` e `source_kind`. `reply_to`, metadados de vizinhos nativos e papéis do avaliador não alcançam o aprendizado. A adaptação Unicode e o pacote estrutural regional reutilizam os experimentos existentes, com raízes observadas, proveniência e paridade fria. Região escolhida pelo chamador e igualdade bruta da consulta não representam intenção aprendida.

As regras novas são explícitas, sem vocabulário de perguntas, distância ajustada ao fixture ou classificador de respostas:

| Rota | Hipóteses por ocorrência exata da consulta |
| --- | --- |
| `adjacent` | próximo usuário no segmento local |
| `structural_adjacent` | mesmo próximo usuário, somente se sua raiz integra os candidatos estruturais |
| `structural_successors` | todas as ocorrências posteriores de candidatos estruturais no segmento local |

Conteúdo `assistant_generated` não participa das raízes/proveniência e interrompe o segmento. Nenhuma rota atravessa essa barreira ou busca sucessores em outra região. Há uma hipótese endereçada por par alvo/origem, com `INFERRED_SEQUENCE_RELATION` e `observed_reply_to:false`. As hipóteses não são inseridas no banco como vínculos observados. Cada episódio mantém alternativas por payload e todas as ocorrências; cópias não votam para resolver conflito.

Somente um episódio e uma raiz inferida permitem `proposal_payload_id`. Ausência de alvo, alvo múltiplo, ausência de relação e raízes concorrentes produzem motivos próprios de abstenção. Sempre permanecem `answer:null`, `qualified:false`, `selected_target:null`, `selection_used:false`. Essa proposta não estabelece relação efetiva, intenção ou verdade.

## Referência nativa e resultados negativos

Cada fixture é persistido nativamente sem vínculos. O diagnóstico lê as linhas, calcula a hipótese e verifica que não as modificou. Somente depois, o avaliador acrescenta seus vínculos de referência. A nova leitura deve produzir exatamente o mesmo diagnóstico completo, inclusive hash da entrada mascarada. Flush/fechamento/reabertura também preservam a saída completa. O avaliador compara pares de endereços, não apenas conteúdo: ausência de vínculo na referência é negativa por construção **destes fixtures**, não uma regra para classificar todo dado real sem `reply_to`.

Os treze casos cobrem relação adjacente, vizinho sem relação (gêmeo com entrada idêntica), candidato único, relação não adjacente, texto opaco próximo, conflito, 21 cópias de uma raiz, conflito 21 contra 1, dois episódios, barreira gerada, cópia estrangeira, consulta sem alvo e alvo terminal. O nome histórico do caso `outside_frame` descreve o texto opaco do fixture; não garante exclusão do pacote estrutural. Nestes seeds, esse texto foi admitido como candidato, e essa admissão permanece visível no flag de cada hipótese.

| Rota | Vínculos corretos | Falsos vínculos | Vínculos perdidos | Conjuntos exatos | Proposta/abstenção conforme referência |
| --- | ---: | ---: | ---: | ---: | ---: |
| vizinho imediato | 9 | 2 | 44 | 7/13 | 8/13 |
| vizinho com filtro estrutural | 9 | 2 | 44 | 7/13 | 8/13 |
| candidatos estruturais posteriores | 52 | 9 | 1 | 6/13 | 8/13 |

Seeds 20261215/20261216 produziram as mesmas contagens e passaram **80/80 controles de integridade em cada seed**. Os seeds renomeiam o mesmo conjunto; não constituem avaliação independente de generalização. As contagens por ocorrência são dominadas pelas cópias: a referência tem 53 vínculos, dos quais 43 pertencem aos dois casos com repetição. Não são 53 fatos independentes nem precisão semântica geral. Sem os dois casos de repetição, há dez vínculos de referência em onze situações: as rotas adjacentes têm 7 corretos, 2 falsos e 3 perdidos; a rota de candidatos posteriores tem 9 corretos, 9 falsos e 1 perdido. O relatório conserva os resultados por caso para evitar essa interpretação.

O vizinho imediato erra quando o próximo texto não é resposta e não recupera a resposta distante ou as demais ocorrências ligadas. O filtro estrutural admite os mesmos vizinhos neste conjunto e não reduz falsos vínculos. Buscar todas as raízes posteriores recupera respostas distantes e mantém os conflitos, mas liga também alternativas não relacionadas; no caso adjacente verdadeiro, uma rival posterior cria conflito e impede a proposta que a referência permitiria. Preservar abstenção não significa que os vínculos inferidos sejam corretos.

A barreira gerada elimina o vínculo inferido mesmo quando o avaliador observa uma relação explícita que a atravessa. Essa ocorrência perdida é registrada; não relaxamos a barreira para melhorar o placar. Alvos múltiplos mantêm identidades distintas mesmo com a mesma raiz de resposta.

Nos dois casos indistinguíveis, todas as rotas recebem a mesma entrada e produzem a mesma saída; apenas a referência posterior muda. As rotas adjacentes acertam **1/2 conjuntos de relações**, e a rota de todos os candidatos posteriores acerta **0/2**, porque inclui uma rival até no caso positivo. Os relatórios mantêm `relation_quality_status:FAIL_FALSE_OR_MISSING_RELATIONS`, `semantic_quality_status:FAIL_HIDDEN_RELATION_TWINS` e qualidade factual `NOT_EVALUATED`. Não comprovamos inferência autônoma de intenção ou resposta factual.

## Verificação e continuidade

Regressão local: **298 passed, 1 optional BDR skip**, em 405,89 segundos. Os oito testes novos passaram, incluindo ambos os seeds nativos e os resultados negativos esperados. Os dois resumos e seus hashes do relatório completo reproduziram byte a byte. Compilação Python e `git diff --check` passaram. A CI deste incremento ainda precisa executar.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so python -m unittest discover -s tests -p test_trajectory_inferred_relation_probe.py
python scripts/trajectory_inferred_relation_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261215 --summary
python scripts/trajectory_inferred_relation_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261216 --summary
```

BDR permanece fixado em `317882a00f041fc1568ff986af8016b09453f21a`. Resumos em `benchmark-results/trajectory-inferred-relation-{development,reserved}.json`; sem `--summary`, conserva-se o pacote estrutural completo. A inferência atua sobre um snapshot fornecido pelo chamador, sem prometer observação atômica global ou nova proteção contra escritores concorrentes. As fronteiras regionais anteriores não se tornam garantia de intenção.

Próximo problema: investigar evidência de continuidade contextual que elimine falsos vínculos entre candidatos, preservando conflitos, barreiras e os gêmeos indistinguíveis. Não houve geração de linguagem, promoção factual, integração com OFF.IA ou mudança do núcleo estável. Os FAILs e limites históricos permanecem.
