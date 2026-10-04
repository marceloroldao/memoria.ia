# Ablação da fronteira entre contexto observado e corpo

Este experimento continua o transporte de contexto observado sem modificar o motor, os seletores anteriores, o runtime nativo ou OFF.IA. A pergunta é mais restrita: **se contexto e corpo já aparecem nas observações, a discriminação de raízes sobrevive quando removemos apenas a fronteira entre essas duas partes?**

Os destinos, contextos, corpos, valores e contratos do avaliador são mantidos idênticos entre os modos. Só muda a origem:

- **explicit**: `prefixo + contexto + separador único + corpo + sufixo`;
- **absent**: `prefixo + contexto + corpo + sufixo`;
- **ambiguous**: o separador usa um símbolo que também aparece dentro do corpo reservado, portanto seu valor não identifica unicamente o corte.

O leitor continua sendo `checked_boundary_packet`. Nenhuma resposta é autorizada: todos os pacotes mantêm `answer:null`, `qualified:false`. As sementes 20261121 e 20261122, cada uma também sob bijeção de símbolos, produziram os mesmos totais.

## Resultado principal

| Fronteira | Casos | Passaram | Respostas únicas corretas | Conflitos preservados | Ausências vazias | Alvos retidos | Falsas hipóteses únicas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| explícita | 56 | 56 | 22/22 | 2/2 | 32/32 | 24/24 | 0 |
| ausente | 56 | 34 | 0/22 | 2/2 | 32/32 | 24/24 | 0 |
| ambígua | 56 | 34 | 0/22 | 2/2 | 32/32 | 24/24 | 0 |
| total | 168 | 124 | 22/66 | 6/6 | 96/96 | 72/72 | 0 |

O contraste é importante: remover ou tornar ambígua a fronteira **não faz o leitor perder os destinos corretos**. Em todos os 72 casos positivos/conflitantes, os alvos continuam presentes. O que desaparece nos 44 casos únicos não explícitos é a autorização estrutural para colapsar os candidatos em uma única hipótese. O leitor abstém-se em vez de escolher arbitrariamente.

Isso separa dois problemas que antes estavam misturados:

1. **recuperação de raízes**: funciona mesmo sem uma fronteira explícita nesta bateria;
2. **identificação de uma decomposição única contexto|corpo**: ainda depende de evidência de fronteira suficiente.

A ablação portanto falsifica a interpretação forte de que “contexto observado basta”. O contexto ajuda a localizar as raízes, mas a fronteira entre partes também carrega informação estrutural.

## Controles cruzados

Os controles cruzados são contados separadamente:

| Fronteira | Controles | Respostas únicas | Conflitos |
| --- | ---: | ---: | ---: |
| explícita | 6/6 | 4/4 | 2/2 |
| ausente | 2/6 | 0/4 | 2/2 |
| ambígua | 6/6 | 4/4 | 2/2 |

A diferença entre `absent` e `ambiguous` nesses controles não restaura a generalização reservada: o modo ambíguo ainda fica em 0/22 respostas únicas na bateria principal. Ele apenas conserva rotas específicas nos pares cruzados já observados. Portanto não deve ser lido como descoberta de uma fronteira geral.

Repetir pares idênticos não cria novos payloads nem altera os conjuntos de candidatos. A adição posterior de um valor rival preserva ambas as raízes e mantém a hipótese única suspensa. A bijeção de símbolos preserva os resultados em todos os modos.

## Interpretação arquitetural

Este resultado favorece uma política conservadora para a Memoria.ia: **retenção de alternativas antes de colapso**. Quando várias segmentações observacionalmente compatíveis explicam a consulta, aumentar repetição não deve virar “confiança”. A memória pode carregar todas as raízes compatíveis e continuar sem resposta única até surgir uma observação que diferencie os cortes.

Isso está alinhado com o princípio do projeto de não impor fato, papel ou semântica rigidamente desde a ingestão. A estrutura pode acumular evidência ao longo do tempo, mas não deve transformar ambiguidade de segmentação em certeza.

## Próxima investigação

O próximo teste não deve simplesmente recolocar um separador fixo. A próxima hipótese falsificável é: **variação observada de comprimentos e posições pode fazer os cortes convergirem sem marcador dedicado?**

Para isso, preservar os mesmos destinos e introduzir demonstrações em que:

- o comprimento do contexto varia;
- o comprimento do corpo varia independentemente;
- apenas uma decomposição continua consistente entre todas as cópias para os destinos;
- um controle gêmeo mantém duas decomposições igualmente compatíveis;
- repetições não contam como novas evidências independentes;
- uma rival posterior deve reabrir conflito se suportar outro corte.

O critério de sucesso não é “responder mais”. É recuperar os mesmos alvos e produzir hipótese única **somente quando todas as fronteiras rivais forem eliminadas por observações independentes**.

## Reprodução

- `python scripts/trajectory_context_boundary_ablation_probe.py --seed 20261121`
- `python scripts/trajectory_context_boundary_ablation_probe.py --seed 20261122`
- `python -m unittest discover -s tests -p test_trajectory_context_boundary_ablation_probe.py`

A execução de referência foi o workflow **trajectory generation proof** run `37175657334`; os dois jobs passaram e todos os sete workflows aplicáveis do commit passaram. O workflow experimental separado permaneceu pulado conforme configuração.

Resumos preservados em:

- `benchmark-results/trajectory-context-boundary-ablation-development.json`
- `benchmark-results/trajectory-context-boundary-ablation-reserved.json`

Os relatórios completos permanecem reproduzíveis pelo script e ficaram registrados nos logs da execução de referência.
