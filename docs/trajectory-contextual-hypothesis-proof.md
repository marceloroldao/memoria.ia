# Hipótese contextual com testemunhas do mesmo destino — 30/09/2026

O experimento ganhou a consulta opcional `contextual_route_hypothesis`.
Nos três lotes textuais, a hipótese retorna a resposta esperada em **24/28**
consultas de resposta, contra **8/28** seleções corretas do gerador padrão.
O gate de qualidade permanece **FAIL**: as seleções indevidas em ausência não
foram resolvidas. A seleção padrão e o OFF.IA não usam esta consulta.

## Consolidação implementada

Em experiências envoltas em contexto, a resposta recorrente e fragmentos como
`: `, `r0: `, `r1: ` aparecem entre os candidatos. Esses fragmentos podem ter
as mesmas testemunhas de destino que a resposta, em vez de representar outro
resultado temporal. A nova consulta preserva o `GenerationResult` completo e
expõe uma hipótese provisória separada.

Uma consolidação exige todos estes contratos:

1. O modo é `NODULE_RECALL`, sem truncamento. Rotas de outras famílias permanecem
   como antes. Uma saída única já existente é exposta como hipótese; eco é ausência.
2. Um candidato está ausente da origem de pelo menos um par testemunha. Cada
   concorrente precisa ser um trecho contido nele ou um trecho transportado
   em todos os seus próprios pares.
3. As testemunhas de cada concorrente são subconjunto das testemunhas desse
   candidato, incluindo origem, destino e captura. Um resultado de outro evento
   não é tratado como contexto equivalente.
4. O contexto comum observado nas origens, ao redor da pista primária, precisa
   aparecer inteiro na consulta. Sua extensão é limitada por `max_context`.
   Afixos transportados com exatamente as mesmas testemunhas podem ser removidos
   dessa comparação, desde que a pista primária permaneça. Todos os caminhos de
   remoção são considerados, sem preferência pelo valor numérico dos símbolos.
5. Somente um candidato pode satisfazer a consolidação. Dois trechos introduzidos
   não contidos um no outro continuam concorrentes, mesmo no mesmo destino.

Não há tokenização, regra de nomes/códigos, limiar de porcentagem, rótulo de
verdade ou reforço novo. A consulta retorna `hypothesis`, `reason`,
`contextual_fragments`, `shared_source_contexts` e a geração original. Nenhum
candidato é apagado; os campos originais e `generate(...).selected` não mudam.

## Tentativa intermediária que falhou

A consolidação somente por testemunhas recuperou a resposta para uma consulta
de sujeito ausente no cenário envolto. Isso seria uma nova seleção indevida.
Exigir o contexto observado da pista impede essa consolidação: a pista curta
compartilhada não autoriza usar a experiência de outro sujeito. Essa tentativa
não foi adotada, e não foi contada como validação do resultado final.

Uma primeira versão desse requisito exigia também o afixo transportado `: `
antes da pergunta, recusando a consulta simples. O contraste já implementado
permite identificar e retirar esse afixo da comparação estrutural, com as mesmas
testemunhas e sem regra sobre pontuação. A resposta ainda pode conter um afixo,
por exemplo `: Daro: 791.`; o avaliador verifica a resposta completa como substring,
não a qualidade da apresentação nem a correção de todo texto adicional.

## Resultados finais

Cada lote contém 28 consultas de resposta, 24 de ausência e quatro de conflito.
Quatro desafios de caixa estão fora dos 52 critérios obrigatórios. O seed
20261007 foi executado após fixar os contratos, mantendo as mesmas famílias
com nomes/códigos fictícios novos. Não é avaliação em conversas reais.

| Medida | 20260930 | 20261004 | 20261007 |
|---|---:|---:|---:|
| Resposta correta selecionada pelo gerador padrão | 8/28 | 8/28 | 8/28 |
| Resposta correta na hipótese opcional | 24/28 | 24/28 | 24/28 |
| Abstenção em ausência na hipótese | 22/24 | 18/24 | 20/24 |
| Seleções indevidas em ausência | 2 | 6 | 4 |
| Desafios de caixa com hipótese incorreta | 4 | 4 | 4 |
| Conflitos preservados sem hipótese única | 4/4 | 4/4 | 4/4 |
| Critérios obrigatórios da hipótese satisfeitos | 50/52 | 46/52 | 48/52 |
| Gate de qualidade da hipótese | FAIL | FAIL | FAIL |

As novas hipóteses corretas são consultas de experiências envoltas e dos dois
sujeitos. Os controles de sujeito ausente nesses cenários continuam sem hipótese.
As saídas únicas incorretas anteriores, em perguntas sem relação ou com caixa
alterada, permanecem: essa consolidação não é um veto das rotas já únicas.

Os 24 controles de transferência opaca passaram: três famílias (introduzido,
transportado e misto), quatro comprimentos de contexto e renomeação. São os
mesmos controles em cada lote, não 72 independentes. O teste específico da
consolidação também usa renomeação que inverte a ordem numérica dos símbolos.

## Verificação e limitações

Sete testes novos verificam hipótese sem perda de candidatos, consulta inédita
com prefixo, sujeito ausente, destinos conflitantes, dois trechos novos no mesmo
destino, truncamento/eco, renomeação e os 24 controles positivos. Os 59 testes
anteriores passaram localmente. Os probes verificam estado inalterado, geração
padrão idêntica antes/depois e igualdade completa após reabertura. Todos os campos
originais dos 112 casos dos dois scorecards anteriores coincidiram com os dados
publicados antes desta etapa.

```sh
python -m unittest discover -s tests -p test_contextual_route_hypothesis.py
python scripts/trajectory_contextual_hypothesis_probe.py --seed 20260930
python scripts/trajectory_contextual_hypothesis_probe.py --seed 20261004
python scripts/trajectory_contextual_hypothesis_probe.py --seed 20261007
```

Dados fictícios completos:
`benchmark-results/trajectory-contextual-hypothesis-{development,heldout,reserved}.json`.
O processo retorna zero quando os contratos de integridade passam; isso não
aprova o gate de qualidade mostrado no relatório.

O contexto comum é uma hipótese estrutural conservadora: contexto estável
adicional pode impedir consolidação, e um trecho transportado pode ser informação
útil. Por isso ele permanece disponível na geração original. A busca considera
somente o recall exposto, com seus limites. Não foram medidos custo/RAM em grande
escala, Android ou dados multimodais reais. Sem integração ao OFF.IA e sem resolver
os três gates pessoais nativos pendentes; o PR permanece rascunho.

A próxima etapa deve tratar as rotas já únicas sem confundir contexto novo com
ausência e sem perder evocação transportada. Esta etapa melhora a hipótese de
resposta em contexto, mas não torna o sistema um respondedor confiável.
