# Contexto observado e discriminação de raízes

Este experimento testa a próxima condição depois dos gêmeos de papéis latentes: o contexto precisa aparecer nas observações para que o leitor possa usá-lo. Usa o leitor anterior, sem alterar aprendizagem, seletores ou autorização. Os símbolos são inteiros opacos; os nomes de corpo, contexto, resposta e caso pertencem somente ao avaliador.

As demonstrações iniciais têm origem `borda + corpo + borda`, e destino `borda + contexto + separador + corpo + ponte + valor + borda`. Os três contextos variam e só aparecem no destino. Três raízes reservadas têm exatamente o mesmo corpo, com contextos diferentes. Duas delas também têm o mesmo valor: a diferença entre suas raízes está apenas no contexto. Uma quarta raiz observada tem o mesmo corpo/valor, mas omite o contexto do destino.

O estágio seguinte acrescenta três origens com `borda + contexto + separador + corpo + borda`, pareadas aos **mesmos destinos já observados**. Só três raízes de origem são novas; nenhuma raiz de destino é adicionada nessa intervenção. A correspondência de contexto e corpo é aprendida como duas cópias exatas, separadas nas duas representações. Os contextos das consultas reservadas são diferentes dos contextos de treinamento, mas aparecem nas raízes reservadas observadas.

## Controles sequenciais

Cada estágio contém sete consultas: três consultas com o mesmo corpo e contextos distintos; contexto sem raiz correspondente; corpo sem raiz correspondente; contexto omitido na consulta; duas consultas concatenadas. As três primeiras exigem uma hipótese estrutural da raiz completa correspondente. No último estágio, a primeira exige preservar duas raízes concorrentes e suspender a hipótese única.

Depois da adição do contexto à origem, os controles cruzados mudam contexto mantendo corpo, valor mantendo contexto/corpo e corpo mantendo contexto. Dois destinos diferentes passam a competir no mesmo par contexto/corpo. O par cruzado é repetido duas vezes, em novas capturas. Por fim, uma rival para o contexto/corpo reservado da primeira consulta é observada isoladamente. Nenhuma consulta reservada tem continuação exata observada; recuperar os destinos depende dos quadros aprendidos, não da repetição da própria consulta.

| Estágio | Casos corretos, incluindo bijeção | Positivos com hipótese correta | Conflitos preservados | Ausências vazias |
| --- | --- | --- | --- | --- |
| Contexto ausente na origem das demonstrações | 8/14 | 0/6 | — | 8/8 |
| Contexto copiado da origem | 14/14 | 6/6 | — | 8/8 |
| Contexto, corpo e valor cruzados | 14/14 | 6/6 | — | 8/8 |
| Par cruzado repetido | 14/14 | 6/6 | — | 8/8 |
| Mesmo contexto com valor rival | 14/14 | 4/4 | 2/2 | 8/8 |

Trocar apenas o contexto da consulta seleciona outra raiz do mesmo corpo. As três rotas ficam disjuntas, mesmo quando o valor é igual. A raiz sem contexto no destino permanece observada e é excluída dessas recuperações. Contexto/corpo sem destino correspondente, contexto omitido e consultas concatenadas não recebem candidatos. Repetição mantém os conjuntos de raízes e hipóteses; a rival posterior não aparece na proveniência de estágios anteriores.

Cada lote (20261119 desenvolvimento, 20261120 reservado) conserva **64/70 FAIL**: 22/28 hipóteses estruturais positivas, 2/2 conflitos, 40/40 ausências, 24/30 casos com todos os alvos recuperados, zero hipóteses únicas indevidas nesta bateria. As seis falhas iniciais continuam no total. O subconjunto com contexto observado passa **56/56**, e os três controles cruzados com bijeção passam **6/6**, separados do denominador principal. `--strict-quality` retorna 1 pelo FAIL completo.

## Alcance do resultado

O resultado mede discriminação estrutural entre raízes que já estão na memória. Não produz uma resposta autorizada: todos os pacotes permanecem `answer:null`, `qualified:false`. Todos os códigos de contexto são tratados da mesma forma; nenhum significa “resposta válida” para o programa. Uma raiz com outro contexto também é recuperável quando esse contexto é consultado. Isso demonstra transporte de um discriminador observado, não aprendizado da intenção de fala ou validação factual.

Os gêmeos anteriores, com papéis que não aparecem no fluxo, continuam **12/24 FAIL**. A bateria anterior de fronteiras continua **98/126 FAIL**. Esses resultados são referências marcadas `recomputed:false` no relatório novo, e seus próprios testes permanecem na regressão. Não foram substituídos pelos 56/56 do subconjunto enriquecido. Sementes e bijeções são controles correlacionados de endereços, não conjuntos independentes de compreensão.

O experimento exige duas partes copiadas exatamente e separadores explícitos. Não testa contexto fora do payload, três partes copiadas, codificação multimodal real ou contexto presente só em metadados. A aprendizagem não transforma símbolos de um contexto em outros nem infere valores ausentes. A informação adicional usada neste resultado foi inserida nas novas observações pelo avaliador; não foi descoberta a partir dos gêmeos indistinguíveis.

## Reprodução e verificação

Seis testes novos verificam preservação das falhas iniciais, intervenção que adiciona apenas origens, rotas diferentes por contexto e exclusão do destino sem contexto, cruzamentos e competição, repetição/proveniência sem autorização, e bijeção. Toda leitura verifica restauração fria, estado e geração padrão inalterados, raízes endereçadas e testemunhas posicionais.

Relatórios completos: `benchmark-results/trajectory-observed-context-{development,reserved}.json`. Reprodução: `python scripts/trajectory_observed_context_probe.py --seed 20261119` ou `--seed 20261120`. A CI executa os testes e os dois lotes; o comando comum relata as falhas de qualidade sem reprovar a integridade das estruturas. Runtime nativo, seletores anteriores, OFF.IA e gaps pessoais permanecem inalterados.

Próxima investigação: manter os mesmos destinos e corpo de consulta, remover ou tornar ambígua somente a separação entre contexto e corpo, e verificar se a discriminação observada sobrevive sem fixar arbitrariamente o comprimento das partes. A presença de contexto útil não garante que o leitor saiba onde ele termina.

Validação local: **216 testes passaram, um teste opcional de BDR foi pulado**, incluindo seis testes novos, os probes anteriores e os consumidores estruturais. Ambos os lotes reproduziram 64/70 no total, 56/56 no subconjunto com contexto e 6/6 controles cruzados separados. O modo estrito foi confirmado retornando 1 pelo FAIL completo. `git diff --check` passou.
