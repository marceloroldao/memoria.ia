# Candidatos por divisão e consenso conservador

Este experimento reutiliza o aprendizado de dois campos anterior. A mudança está na leitura: avalia cada divisão válida da consulta pelo separador aprendido e conserva as raízes inteiras que correspondem a cada par de trechos. A forma anterior descartava todos esses candidatos quando havia mais de uma divisão. O motor e os seletores anteriores permanecem inalterados.

Cada candidato recebe as posições do separador, os trechos consultados e as testemunhas dos quadros. Uma divisão com trechos vazios é inválida; quadros com veto por âncora interna continuam excluídos. A leitura conserva as rotas anteriores e une as novas, sem atribuir votos ao número de divisões ou testemunhas.

## Decisão e controles

| Situação | Candidatos conservados | Hipótese |
| --- | --- | --- |
| Uma divisão encontra raiz; outra divisão válida não encontra | A raiz encontrada | Suspensa: suporte parcial |
| Duas divisões encontram raízes diferentes | Ambas as raízes | Suspensa: conflito |
| Todas as divisões válidas convergem para uma raiz | Uma raiz e todas as correspondências | A raiz inteira observada |
| Nenhuma divisão encontra raiz | Nenhum | Vazia |

Os controles são executados com e sem renomeação: **8/8 PASS** nas sementes 20261101 e 20261102. Os oito casos têm denominador próprio e não foram adicionados à bateria de 72. Um teste adicional observa uma segunda raiz depois da primeira: o estado passa de suporte parcial para conflito, preservando a raiz anterior. Mais observações não são tratadas automaticamente como maior certeza.

No controle de consenso, o destino repete a concatenação dos dois campos com o mesmo separador. Ambas as divisões produzem a mesma raiz observada, embora a política anterior recusasse a consulta. Isso comprova estabilidade do resultado nas divisões avaliadas, não o papel semântico correto de cada trecho.

## Comparação na bateria anterior

O contrato de nove consultas nos quatro cenários permanece **66/72 FAIL**, com **14/20** respostas corretas, **4/4** conflitos preservados, **48/48** ausências vazias e zero seleções únicas indevidas por lote. As sementes mudam apenas os endereços opacos, e as versões renomeadas são controles correlacionados.

Nos seis positivos com separador ambíguo, a leitura agora conserva uma raiz candidata e informa a divisão sustentada. A hipótese continua vazia porque outra divisão válida não tem suporte. As seis respostas esperadas permanecem falhas de cobertura; não foram convertidas em ausências corretas. Esta etapa melhora a exposição da incerteza, sem alegar ganho na contagem principal.

Os contraexemplos anteriores sem marcação interna permanecem pendentes. Um teste mantém explicitamente a seleção indevida anterior quando não há um quadro de dois campos. Essa hipótese é identificada como `PRIOR_SELECTOR_HYPOTHESIS_ONLY`; não recebe o rótulo de consenso entre divisões. Não reinterpretamos o resultado 76/84 do estudo sem marcação nem o 146/168 da bateria original.

## Validação e limites

Relatórios completos: `benchmark-results/trajectory-analogy-alignment-{development,reserved}.json`. Contêm a política anterior, candidatos, posições, trechos, correspondências por divisão, quadros, testemunhas e proveniência das observações. Candidatos e testemunhas são verificados contra as raízes observadas. Cada leitura verifica restauração, aprendizagem inalterada e geração padrão inalterada.

Sete novos testes verificam suporte parcial, conflito entre divisões, consenso em uma raiz, entrada incremental de um rival, denominador e falhas anteriores preservados, renomeação/controle vazio e distinção entre hipótese anterior e consenso. Os 60 testes locais de analogia passaram. O modo `--strict-quality` retorna 1 para o FAIL da bateria principal; a CI verifica integridade sem declarar qualidade aprovada.

O consenso cobre somente as divisões e quadros enumerados. Não descobre interpretações sem separador aprendido, não resolve campos latentes não observáveis e não torna as rotas antigas semanticamente seguras. Uma divisão sem raiz pode indicar falta de observações; por isso não é descartada para autorizar a outra. A exigência de três exemplos distintos e o veto de âncoras internas continuam conservadores, com perdas de cobertura já documentadas.

Runtime nativo e OFF.IA continuam inalterados; os três gates pessoais nativos seguem pendentes. Não há garantia de eficiência da enumeração de trios, substrings e raízes. Próximo passo: avaliar repetição de uma das pistas entre demonstrações e a combinação de quadros específicos e amplos, mantendo a mesma representação explícita de suporte e conflito.
