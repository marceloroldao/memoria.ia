# Contexto observado nas rotas únicas — 30/09/2026

Esta revisão aplica o contexto observado também às hipóteses de rotas únicas
em `NODULE_RECALL`. A geração padrão, os candidatos e os pesos ficam preservados.

## Mudança

Antes, `contextual_route_hypothesis` aceitava imediatamente uma saída única
do gerador. Assim, as verificações de contexto eram usadas na consolidação,
mas não nos fragmentos únicos responsáveis pelos erros de ausência.

Agora a rota única passa pela mesma busca do contexto comum nas origens dos
pares testemunhas. Esse contexto precisa aparecer na consulta, depois de retirar
afixos transportados com exatamente as mesmas testemunhas e mantendo a pista.
O próprio alvo pode ser esse afixo quando a rota já era única. Isso permite
evocar um nódulo transportado em contexto novo, sem exigir novidade no destino.

Rotas com candidatos concorrentes continuam exigindo um candidato introduzido
que consolide apenas partes contidas ou contexto transportado dos mesmos pares.
As famílias temporal de raiz, raiz embutida e continuação não são alteradas.
Eco, truncamento e destinos distintos continuam sem consolidação.

A hipótese retorna `SOURCE_CONTEXT_SUPPORTED_ROUTE` para uma rota de nódulo
única sustentada pelo contexto. Quando o contexto não corresponde à consulta,
retorna hipótese vazia com `UNMATCHED_SHARED_SOURCE_CONTEXT`, mantendo a geração
original e os contextos encontrados para inspeção. Isso não apaga uma associação
nem reduz seus pesos.

## Validação preparada

Foram acrescentados três testes aos sete anteriores: fragmento único genérico
sem resposta, mudança de caixa sem normalização e evocação transportada com
contexto longo e renomeação dos símbolos. Os 24 controles positivos anteriores
continuam no probe.

O workflow mantém os seeds 20260930, 20261004 e 20261007, e acrescenta o seed
20261008 depois de fixar esta revisão, com `--strict-quality`. Esse parâmetro
retorna código 1 se qualquer critério obrigatório da hipótese falhar. Os quatro
desafios de caixa por lote continuam fora desses critérios: ausência de resposta
nesses desafios não é acerto de generalização linguística.

O ambiente local está indisponível nesta etapa. A validação será feita pelo
workflow do PR; não há execução local nem resultados novos aprovados ainda.
Os relatórios anteriores correspondem à implementação `7d77018` e continuam
registrados como histórico, com seus gates FAIL.

## Limites e próximo passo

O contexto comum usa o limite existente `max_context` e as testemunhas do recall
exposto. Pode recusar evocação útil quando a experiência só oferece contexto
específico. Os controles positivos exercem famílias determinadas, não garantem
transferência universal. Sem vocabulário de domínio, LLM, rótulos de resposta no
motor ou reinserção de saídas.

Esta etapa não altera `generate(...).selected`, não ativa a hipótese no OFF.IA
e não resolve os três gates pessoais nativos pendentes. O PR permanece rascunho.
