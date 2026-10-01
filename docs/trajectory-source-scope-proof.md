# Escopo da origem completa, 30/09/2026

## Resultado

Os cinco lotes passam em **150/150**, com **54/54 respostas corretas**, ausência
84/84, conflitos 12/12 e zero hipóteses indevidas. O modo `--strict-quality`
retorna zero em todos. A pergunta original agora conserva seu destino observado,
enquanto a segunda superfície com dois destinos continua sem escolha única.

| Seed | Revisão anterior | Nova revisão | Hipóteses indevidas |
| --- | --- | --- | --- |
| 20260930 | 146/150, 50/54 respostas | 150/150, 54/54 | 0 |
| 20261009 | 146/150, 50/54 respostas | 150/150, 54/54 | 0 |
| 20261010 | 146/150, 50/54 respostas | 150/150, 54/54 | 0 |
| 20261012 | 146/150, 50/54 respostas | 150/150, 54/54 | 0 |
| 20261013 | Não executado antes | 150/150, 54/54 | 0 |

O seed 20261013 foi executado após fixar o código e os controles adversariais.
Os mesmos 50 critérios opacos se repetem nos lotes; Unicode/UTF-8 representam
os mesmos textos. O resultado verifica estas famílias sintéticas, não 750
casos independentes de uso real nem generalização para novas famílias.

## Condições da hipótese opcional

O código conserva a revisão de sufixos e exige uma única raiz de destino na
evocação exata/embutida, sem truncamento. Todos os candidatos visíveis precisam
ser partes dessa raiz. Uma testemunha de nódulo com destino diferente só pode
ficar fora da hipótese se, para esse mesmo nódulo:

1. sua origem também tiver testemunha separada chegando à raiz selecionada;
2. sua origem completa não estiver contida na consulta;
3. sua origem não contiver nenhuma das pistas completas que sustentam a raiz.

Assim, o conflito de uma pista completa distinta não é automaticamente herdado
pela pergunta original. Esta é uma distinção por símbolos e relações observadas;
não há conceito de sujeito, sinônimo, equivalência de caixa ou interpretação de
verdade. O destino da variação precisa ter sido observado, não inferido por aparência.

O motivo é `SOURCE_SCOPED_ROOT_DESTINATION` quando há testemunhas fora do escopo.
`scoped_out_witnesses` expõe suas tuplas `(origem, destino, captura)` para inspeção.
Elas continuam na evidência integral de `generation`, com os mesmos pesos e IDs.
Sem esse contraste, o motivo anterior `OBSERVED_ROOT_DESTINATION_CONTEXT` permanece.

Não mudam candidatos, `generate().selected`, pesos, conteúdo, observações ou
snapshots. Nenhuma consulta, hipótese ou saída é automaticamente ensinada.
Os 600 GenerationResults completos dos quatro lotes anteriores são idênticos
na comparação local, incluindo testemunhas, pesos, ordenação e truncamento.
Relatórios históricos permanecem disponíveis, sem sobrescrever FAIL anteriores.

## Proteções e mudança de contrato

Uma fonte que só testemunhou o destino rival não pode ser descartada. Uma origem
envolvente que contém a pista completa original continua concorrente, mesmo
quando testemunhou ambos os destinos. Um destino completo distinto entre os
candidatos impede consolidação; duas raízes evocadas e truncamento também.

O teste anterior que exigia abstenção da pergunta original no caso de duas pistas
completas distintas falhou na primeira execução da revisão, como esperado pela
mudança proposta. Foi reformulado para verificar o novo escopo, exigir a hipótese
do destino original, manter a seleção padrão vazia e conferir o endereço da
testemunha de conflito. As consultas da segunda superfície continuam exigindo
ambos os destinos e abstenção; nenhuma falha foi retirada do scorecard.

Quatro testes adversariais adicionais verificam falta de suporte separado,
origem contendo a pista completa, prefixo novo com renomeação bijetiva e destinos
completos distintos entre famílias de evocação. Todos usam leitura sem mutação
e igualdade após reabertura. O último controle usa destinos envoltos distintos
para tornar o nódulo recorrente realmente disponível; a primeira montagem com
destino repetido idêntico não evocava esse candidato e não verificava competição.
Isso também limita a conclusão: a política só examina evidência que foi recuperada.

## Validação e reprodução

Localmente: 18 testes da hipótese, 59 do gerador e quatro do avaliador passaram.
Os quatro gates anteriores (20260930/20261004/20261007/20261008) permanecem PASS
52/52, com 24/28 respostas corretas, ausência 24/24, conflitos 4/4 e os mesmos
24 controles opacos preservados. As quatro variações de caixa não observadas
desses gates continuam sem resposta; não foram aprendidas automaticamente.

`python scripts/trajectory_observed_variant_probe.py --seed 20261013 --strict-quality`

O formato v3 identifica `hypothesis_revision: source-scoped-root-context-v1`.
O CI executa os cinco seeds e exige qualidade estrita no novo lote reservado.
Relatórios fictícios completos:
`benchmark-results/trajectory-source-scope-{development,heldout,prior-reserved,previous-reserved,reserved}.json`.

O pytest local continua indisponível; a regressão completa está no workflow.
Os resultados não garantem segurança factual, recuperação de todas as rotas,
equivalência linguística ou inteligência geral. OFF.IA não recebe a política;
os três gates pessoais nativos continuam pendentes e o PR permanece draft.
