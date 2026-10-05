# Compatibilidade entre corte, moldura e raiz observada

Continuação de `be9d814`, cuja CI passou nos sete workflows aplicáveis (run `37179757341`). A bateria anterior permanece **148/160 FAIL**. Este incremento adiciona um diagnóstico de leitura; não modifica o motor, os leitores anteriores, o runtime nativo ou OFF.IA.

## A distinção que faltava

Uma comparação envolve três elementos: **uma moldura aprendida, um corte na consulta e uma raiz observada**. O diagnóstico registra cópias exatas, multiplicidade, ordem/sobreposição e compatibilidade com as partes fixas da moldura. Cada resultado conserva endereço da raiz e IDs das suas ocorrências.

- `SUPPORTED_OBSERVED_ROOT`: esta raiz satisfaz as duas cópias e a moldura neste corte.
- `INCOMPATIBLE_OBSERVED_ROOT`: esta raiz não satisfaz esse contrato; registra o motivo observável.
- Corte `SUPPORTED`: existe ao menos uma raiz com suporte.
- Corte `UNKNOWN`: não existe raiz observada com suporte; **o corte não é excluído**.

Incompatibilidade é condicional à raiz e à moldura. Não é uma declaração de que toda raiz possível contradiz o corte. Por isso este diagnóstico não introduz um estado global `CONTRADICTED`, nem transforma ausência em evidência negativa. Tampouco estabelece verdade factual ou intenção de resposta. Molduras com o mesmo layout são agrupadas no diagnóstico; testemunhas permanecem endereçáveis e não viram votos.

As raízes comparadas possuem o prefixo/sufixo de destino observado na moldura. Os outros payloads ficam fora dessas comparações, mas os candidatos do leitor anterior são preservados integralmente. O diagnóstico não é um filtro de candidatos.

## Controle sequencial

Seeds 20261125/20261126, cada um incluindo bijeção, reutilizam as origens de comprimentos cruzados do fixture anterior. Começamos com três pares e uma raiz reservada isolada. Depois repetimos uma demonstração, observamos uma raiz rival em outro corte e repetimos a rival. A consulta reservada nunca é ingerida. O controle de corpo desconhecido deve continuar vazio.

| Destino | Primeiro estado | Depois da rival |
| --- | --- | --- |
| cópias separadas | cortes 2, 4 e 5 desconhecidos; corte 3 sustentado | corte 4 passa a sustentado; cortes 2 e 5 permanecem desconhecidos |
| cópias adjacentes | os quatro cortes sustentam a mesma raiz | os quatro cortes sustentam ambas as raízes |

No destino separado, a primeira raiz era incompatível com o corte 4 e continua sendo incompatível depois da intervenção. Entretanto, a nova raiz sustenta o corte 4. **Uma incompatibilidade particular não autorizava eliminar aquela interpretação globalmente.** Ambas as raízes permanecem disponíveis e a hipótese única fica suspensa. Os dados não eliminam cortes desconhecidos nem identificam uma fronteira única no controle adjacente.

Repetir a demonstração mantém layouts, suporte e candidatos. Repetir a rival adiciona seu ID de ocorrência ao mesmo payload, sem novas alternativas. Cada leitura verifica paridade após restauração, estado de aprendizado e geração inalterados.

## Resultados e limites

Cada seed reproduz **28/32 FAIL**, com 4/8 hipóteses estruturais corretas, 8/8 conflitos preservados, 16/16 ausências vazias, 16/16 casos com todos os alvos retidos e zero falsas hipóteses únicas nesta bateria. As quatro falhas são as hipóteses únicas suspensas nos dois primeiros estados do destino separado, incluindo renomeações. Não há aumento de qualidade do leitor: ele é o mesmo. Este denominador não substitui as baterias anteriores 148/160, 124/168, 98/126 ou os gates pessoais nativos.

Todos os pacotes e diagnósticos conservam `answer:null`, `qualified:false`; `excluded_cuts` permanece vazio. Os fixtures são opacos, correlacionados e estreitos. A comparação usa cópias exatas e molduras demonstradas; não mede compreensão geral, refutação semântica ou melhoria por tentativa e erro no mundo físico. Não foi criado um contrato de observações negativas.

Sete testes novos verificam incompatibilidade particular, suporte tardio sem perda da primeira raiz, equivalência adjacente, repetição/proveniência, violações de cópia/ordem/layout, bijeção/paridade e manutenção do FAIL. Regressões locais: **231 passed, 1 optional BDR skip**. Compilação Python e `git diff --check` passaram. Os dois seeds reproduziram os totais; o modo estrito retornou 1 como esperado. O resumo de desenvolvimento, seus motivos/proveniência e o hash do relatório completo foram reproduzidos exatamente. Validação remota de `6bf511c`: seis workflows aplicáveis passaram; o job `native-bridge` da prova também passou. O job `proof` foi cancelado aproximadamente dez minutos após seu início, durante a etapa de comprimentos cruzados, antes de executar este diagnóstico e as regressões finais. O workflow tinha limite de dez minutos; essa execução não valida as etapas puladas. Run: [37380015148](https://github.com/marceloroldao/memoria.ia/actions/runs/37380015148). O incremento seguinte amplia apenas o orçamento desse job para vinte minutos e reexecuta todos os controles.

## Reprodução

```
python -m unittest discover -s tests -p test_trajectory_cut_compatibility_probe.py
python scripts/trajectory_cut_compatibility_probe.py --seed 20261125 --summary
python scripts/trajectory_cut_compatibility_probe.py --seed 20261126 --summary
python scripts/trajectory_cut_compatibility_probe.py --seed 20261126 --summary --strict-quality
```

O modo estrito retorna 1. Sem `--summary`, o script emite o relatório completo, incluindo pacotes, slots, molduras, ocorrências e proveniência. Resumos com motivos por raiz, IDs de ocorrência e SHA256 do relatório completo ficam em `benchmark-results/trajectory-cut-compatibility-{development,reserved}.json`.

## Próxima investigação

Testar o vínculo entre uma moldura e sua situação de observação: conservar a região/origem de cada testemunha e evitar que uma cópia estruturalmente compatível seja tratada como intenção de resposta universal. Usar situações observacionalmente distinguíveis e um controle gêmeo idêntico com papéis ocultos apenas no avaliador. A ambiguidade do gêmeo deve continuar explícita; não inserir seus rótulos na ingestão nem transformar repetição em seleção factual.
