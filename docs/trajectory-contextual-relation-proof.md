# Filtro de raiz contextual: menos falsos vínculos, perda de recuperação

Continuação de `01ba7e4`. Seis workflows desse commit passaram; no workflow de trajetória `37656027785`, o job `proof` passou e `native-bridge` foi cancelado durante o novo ensaio. Seu limite era dez minutos; os logs registram cancelamento, sem falha de asserção demonstrada. Este incremento amplia o orçamento para 25 minutos, sem remover etapas, e acrescenta uma comparação opt-in de rotas contextuais existentes. O PR #374 permanece em rascunho.

## Hipótese e evidência conservada

`contextual_relations` conserva o resultado completo de `inferred_relations` e consulta `contextual_route_hypothesis` com a região explícita. Compara o modo contextual existente e a opção `transported_source_scope`. O aprendizado recebe somente a cópia dos cinco campos brutos já admitidos; `reply_to`, vizinhos nativos e papéis de avaliação não entram.

Uma hipótese contextual pode ser fragmento ou payload completo. O filtro exige igualdade da hipótese com **uma raiz integral observada na região**, e depois conserva somente as relações inferidas de `structural_successors` com essa raiz. Não inventa raiz para um fragmento aprendido, não transforma posição posterior em vínculo observado e não usa vocabulário de perguntas/respostas. Não altera pesos ou seletores; é uma regra diagnóstica explícita sobre a hipótese existente.

Cada rota mantém episódios endereçados, alternativas e motivos. Apenas um episódio com ocorrência posterior da raiz contextual permite uma proposta. Sempre conserva `answer:null`, `qualified:false`, `selected_target:null`, `selection_used:false`. O pacote anterior, todas as relações removidas e o diagnóstico contextual completo permanecem auditáveis. Há comparação fria da memória Python e da leitura nativa, além de verificação de leitura sem alteração de estado.

É importante distinguir candidatos estruturais filtrados de evidência temporal completa: no teste simples com `abc`, `def`, `ghi`, o pacote estrutural admite somente `def`, mas o diagnóstico temporal contém as duas raízes posteriores. O filtro abstém-se por competição contextual e conserva ambas nessa evidência. O teste verifica separadamente as duas coleções, mantendo a competição temporal demonstrada.

## Casos e resultado

Os treze casos anteriores permanecem. Há três controles adicionais: rota única depois da remoção dos dois textos concorrentes; gêmeo com exatamente as mesmas observações e referência negativa; fragmento comum introduzido em dois destinos integrais distintos. As referências só são atribuídas depois do diagnóstico e então persistidas como vínculos nativos pelo avaliador. A intervenção em vínculos e a reabertura devem preservar a saída completa.

| Rota, nos 16 casos | Corretos | Falsos vínculos | Perdidos | Conjuntos exatos | Proposta/abstenção conforme referência |
| --- | ---: | ---: | ---: | ---: | ---: |
| vizinho imediato | 10 | 3 | 44 | 9/16 | 10/16 |
| vizinho com filtro estrutural | 10 | 3 | 44 | 9/16 | 10/16 |
| candidatos estruturais posteriores | 53 | 10 | 1 | 8/16 | 10/16 |
| raiz contextual | 1 | 1 | 53 | 5/16 | 8/16 |
| raiz contextual com escopo transportado | 1 | 1 | 53 | 5/16 | 8/16 |

Seeds 20261217/20261218 produziram as mesmas contagens e passaram **116/116 controles de integridade em cada seed**. São duas renomeações do mesmo conjunto, não uma avaliação independente de generalização. As 54 relações de referência são ocorrências, das quais 43 vêm dos dois casos repetidos; não são fatos independentes. Sem esses dois casos, os filtros contextuais continuam com 1 correto, 1 falso e 10 perdidos em 14 situações. A redução de falsos vínculos decorre principalmente de abstenção; há perda severa de recuperação, e nenhuma melhora geral foi comprovada.

Nos treze casos originais, os filtros contextuais não recuperam nenhum dos 53 vínculos de referência. Mesmo no caso chamado `structural_single`, o diagnóstico contextual conserva um texto opaco como rota temporal concorrente e abstém-se. O controle novo remove tanto a rival quanto esse texto: o motor existente produz `EXISTING_UNIQUE_ROUTE`, a hipótese coincide com a raiz integral e há uma proposta endereçada. Essa proposta é correta na interpretação positiva e falsa no gêmeo negativo. Não se resolveu intenção.

Nos dois pares de gêmeos, as entradas e saídas completas são iguais, as referências diferem, e cada filtro contextual acerta **1/2 conjuntos de relações** por par. No primeiro par, ambos os casos abstêm-se, errando o positivo; no segundo, ambos propõem, errando o negativo. A opção de escopo transportado não muda as contagens neste conjunto; isso não prova equivalência em outros dados.

O controle de fragmento produz `SOURCE_CONTEXT_SUPPORTED_ROUTE` e uma hipótese de três símbolos. Nenhum payload completo observado tem esses símbolos como raiz integral. O resultado mantém o fragmento e retorna `NON_ROOT_CONTEXTUAL_HYPOTHESIS`, sem fabricar proveniência. Essa limitação separa aprendizagem de composição de recuperação de uma ocorrência nativa integral; não declara inválido o fragmento aprendido.

Os relatórios continuam com `FAIL_FALSE_OR_MISSING_RELATIONS`, `FAIL_HIDDEN_RELATION_TWINS` e qualidade factual `NOT_EVALUATED`. Abster-se corretamente em conflitos não implica recuperar suas relações corretamente: o pacote base mantém as alternativas, mas o filtro perde suas ocorrências de referência. Todas as perdas e falsos vínculos continuam nos resumos por caso.

## Verificação e continuidade

Regressão local: **306 passed, 1 optional BDR skip**, em 513,72 segundos. Os oito testes novos passaram, incluindo ambos os seeds nativos e os resultados negativos esperados. Os resumos e hashes do relatório completo reproduziram byte a byte. Compilação Python e `git diff --check` passaram. A CI de `8cb021b` passou nos sete workflows aplicáveis, incluindo trajetória `37659778915`; a regressão condicional experimental foi pulada. O job nativo com orçamento de 25 minutos também passou.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so python -m unittest discover -s tests -p test_trajectory_contextual_relation_probe.py
python scripts/trajectory_contextual_relation_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261217 --summary
python scripts/trajectory_contextual_relation_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261218 --summary
```

BDR permanece fixado em `317882a00f041fc1568ff986af8016b09453f21a`. Resumos: `benchmark-results/trajectory-contextual-relation-{development,reserved}.json`. Sem `--summary`, o relatório conserva a geração/diagnóstico contextual completos e todo o pacote base. Continuam as limitações de snapshot fornecido pelo chamador, região explícita, barreiras geradas, intenção oculta e proveniência. Não houve mudança do núcleo estável, geração de linguagem, integração OFF.IA ou promoção factual.

Próxima questão: testar se contextos **observáveis e diferentes** entre episódios permitem discriminar rotas concorrentes com melhor recuperação, mantendo como controles os gêmeos em que nenhum contexto distingue a intenção. Este filtro rígido não deve ser instalado como seletor padrão: o ensaio demonstra sua perda de recuperação.
