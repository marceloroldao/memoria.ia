# Origem conservada e destino de raiz, 30/09/2026

## Resultado da revisão opcional

Nos quatro lotes, os critérios passam a **146/150**, as respostas corretas a
**50/54** e as hipóteses indevidas a **zero**. O gate completo permanece **FAIL**:
quatro consultas textuais da pergunta original ficam sem resposta depois de
observar um destino conflitante para sua segunda superfície. Essa interferência
continua pendente; não foi removida do denominador nem tratada como acerto.

| Seed | Antes: critérios / indevidas | Agora: critérios / indevidas | Respostas |
| --- | --- | --- | --- |
| 20260930 | 118/150 / 12 | 146/150 / 0 | 50/54 |
| 20261009 | 120/150 / 10 | 146/150 / 0 | 50/54 |
| 20261010 | 118/150 / 12 | 146/150 / 0 | 50/54 |
| 20261012 | Não executado antes | 146/150 / 0 | 50/54 |

O novo seed 20261012 foi executado depois de fixar o código e os testes.
O seed 20261011 foi usado durante desenvolvimento e teve o mesmo resultado
146/150; não é apresentado como reserva. Os critérios opacos são os mesmos
50 em todos os lotes, e os adaptadores Unicode/UTF-8 representam os mesmos textos.

## Política estrutural

`contextual_route_hypothesis` continua retornando o `GenerationResult` original.
Não altera `generate().selected`, pesos, associação ou observações; não normaliza
caixa e não aprende consultas nem saídas geradas.

Em COMBINED_RECALL não truncado, uma hipótese pode consolidar a raiz observada
somente quando os destinos da evocação exata/embutida formam uma única raiz,
todos os candidatos são trechos contidos nessa raiz e cada testemunha de nódulo
chega à mesma raiz de destino. Identidade de destino é necessária: compartilhar
um fragmento de texto não autoriza descartar outro resultado observado.
O motivo exposto é `OBSERVED_ROOT_DESTINATION_CONTEXT`.

Em NODULE_RECALL, o contexto central comum continua obrigatório. Acrescentamos
o maior sufixo comum das origens, limitado a `max_context`, como âncora ordenada
quando tem pelo menos `min_context` símbolos. A posição na consulta deve ser
igual ou posterior à posição do contexto central. As remoções de afixos de
destinos transportados usam exatamente as mesmas testemunhas e percorrem todos
os caminhos de remoção, sem favorecer a ordem numérica dos símbolos. A âncora
adicional aparece em `shared_source_contexts` se não estiver contida no contexto.

Isso preserva, por exemplo, o final comum de duas origens cujo início varia.
Um trecho central genérico sozinho deixa de sustentar a hipótese. A sequência
de símbolos da âncora é aprendida; o motor não sabe que ela representa um sujeito.

## Contrastes observados

Em cada lote: ausência 84/84, conflitos da variação 12/12 preservados,
perguntas sem resposta observada permanecem sem hipótese, e os pares aprendidos
e repetidos têm 18/18 respostas corretas por etapa. Conteúdo repetido não cria
novas raízes nem votos adicionais. Os quatro erros restantes são abstenções
da pergunta original na etapa de conflito, com os alvos ainda entre candidatos.

Os quatro gates anteriores, seeds 20260930/20261004/20261007/20261008, continuam
PASS 52/52: 24/28 respostas corretas, ausência 24/24, conflitos 4/4, controles
opacos 24/24. As quatro variações de caixa não observadas desses lotes continuam
sem resposta. A melhoria nova exige observar a variação seguida do destino;
não demonstra equivalência de caixa aprendida de forma geral.

Comparação local dos três lotes antigos de variação: os **450 GenerationResults**
completos permanecem idênticos, incluindo candidatos, pesos, evidência e seleção.
Somente a hipótese opcional muda. Os relatórios anteriores não foram sobrescritos.

## Tentativas rejeitadas

A primeira proteção de sufixo também exigia o marcador transportado do contexto
envolvente e reduziu o gate anterior de 52/52 a 40/52 (respostas 24/28 a 12/28).
Foi rejeitada. Remover os afixos transportados preservou as respostas anteriores.

Consolidar a raiz sem conservar uma âncora curta adicional recuperou respostas
das variações, mas manteve 12/10/12 hipóteses indevidas: 134/150, 136/150 e 134/150.
O final conservado pode ser menor que a pista central; descartá-lo usando a largura
da pista perdia justamente essa informação. A revisão usa o limite estrutural
`min_context` já existente, não um limiar textual ou vocabulário especial.

## Reprodução e limites

`python scripts/trajectory_observed_variant_probe.py --seed 20261012 --strict-quality`

Retorna **1**, pois 146/150 ainda não satisfaz todos os critérios. Sem o modo
estrito, o workflow verifica integridade e informa FAIL de qualidade. O formato
v2 identifica `hypothesis_revision: source-ending-root-context-v1` e distingue
mudança de política opcional de seleção padrão inalterada.

Localmente passaram 14 testes da hipótese (quatro novos), 59 testes do gerador e
quatro do avaliador. Os novos testes verificam raiz observada, prefixo novo,
sufixo conservado, renomeação bijetiva, ordem, destinos distintos e truncamento,
com leitura sem mutação e paridade fria. A regressão pytest depende do CI pois
pytest não está instalado localmente.

Relatórios fictícios completos:
`benchmark-results/trajectory-source-ending-{development,heldout,prior-reserved,reserved}.json`.
Esta proteção cobre finais conservados; variações de terminação, distinções
internas, limites de contexto e múltiplos destinos ainda exigem investigação.
Não se afirma ausência geral de erro, acurácia real ou equivalência a uma LLM.
OFF.IA não recebe a política; três gates pessoais nativos seguem pendentes, PR draft.
