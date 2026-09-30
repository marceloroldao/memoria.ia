# Especificidade da pista e filtro de cobertura — 30/09/2026

**A proposta de filtro foi rejeitada como política do motor.** Ela suspende as
seleções incorretas dos lotes textuais, mas também suspende evocações estruturais
válidas quando a mesma pista aparece em contexto novo mais comprido. O motor e
seu `selected` permanecem inalterados. A qualidade de resposta segue pendente.

## Diagnóstico

`scripts/trajectory_query_specificity_probe.py` reproduz as 56 consultas de cada
lote do scorecard textual. Para cada candidato de associação, registra largura
da pista primária, fração da consulta coberta por ela e cada par de payloads/captura
testemunha. Para a origem de cada par, mede também o maior trecho contíguo comum
à consulta e se contém a consulta inteira. Trechos disjuntos não são somados;
repetições e ordem são preservadas.

Os candidatos únicos incorretos dos três lotes são ativados por pistas de apenas
dois ou três símbolos. A cobertura primária fica entre aproximadamente 9,5% e
20%. Maior sobreposição com o payload de origem não significa que toda essa
sobreposição sustenta uma ligação ao destino: por exemplo, a consulta com caixa
alterada compartilha nove símbolos com a origem, mas a pista ligada tem três.

A ablação aplica **fora do motor** a proposta: suspender uma seleção única em
`NODULE_RECALL` se largura da pista / comprimento da consulta estiver abaixo de
um limiar. Preserva candidatos, pesos e modos; não promove um concorrente a
resposta. Os rótulos esperados entram somente na contagem posterior de acertos,
nunca no veto. As demais famílias de geração não são filtradas.

## Contraste necessário

Quatro entradas de inteiros opacos aprendem a relação do nódulo `(1,2,3)` com
`(7,8,9)`. O controle consulta a mesma pista com contexto inédito de 1, 4, 8 ou
16 símbolos em cada lado. O motor evoca `(7,8,9)` como saída única nos quatro
casos; o alvo é um nódulo intermediário e não uma raiz de payload inteiro.

Os quatro casos são repetidos com uma renomeação bijetiva dos símbolos, totalizando
oito controles. A cobertura passa de 3/5 para 3/11, 3/19 e 3/35, embora a pista,
a relação aprendida e as testemunhas continuem as mesmas. O efeito do limiar é
idêntico após renomeação. Isso mede transferência estrutural, não verdade factual.

## Resultados

O lote 20261005 foi executado depois da proposta, sem ajustar os limiares a ele.
Muda nomes/códigos fictícios e mantém as mesmas famílias; não é conversação real.

| Limiar | Seleções textuais incorretas restantes: 20260930 / 20261004 / 20261005 | Evocações opacas válidas suspensas |
|---|---|---:|
| 0 | 6 / 10 / 6 | 0/8 |
| 0,25 | 0 / 0 / 0 | 4/8 |
| 0,50 | 0 / 0 / 0 | 6/8 |
| 0,75 | 0 / 0 / 0 | 8/8 |
| 1,00 | 0 / 0 / 0 | 8/8 |

Cada lote continua com somente 8/28 respostas corretas selecionadas, em todos os
limiares. As falhas de contexto envolto continuam ambíguas. No limiar zero,
seleções incorretas em ausência são 2/24, 6/24 e 2/24; as demais quatro falhas por
lote são o desafio de caixa. O filtro melhora abstenção nesse corpus, mas não
ensina o sistema a responder e perde transferência estrutural.

Uma pista legítima ocupa 3/35 da consulta, menos que a menor cobertura incorreta
observada. Portanto, um corte global nessa razão não separa esses dois tipos de
casos sem perdas. Cobertura é um diagnóstico; não foi adotada como confiança.

Relatórios completos fictícios:
`benchmark-results/trajectory-query-specificity-{development,heldout,reserved}.json`.
Cada relatório inclui os mesmos oito controles opacos, não oito novos por lote.

## Verificação e limites

Três testes verificam ordem/trechos disjuntos, símbolos repetidos e perda de
transferência após renomeação. Os lotes verificam leitura sem aprendizado,
reabertura com igualdade completa dos resultados e dos novos diagnósticos. O
processo retorna zero quando esses contratos passam; `quality_status` permanece
`UNRESOLVED`. O scorecard original continua reprovado.

```sh
python -m unittest discover -s tests -p test_trajectory_query_specificity_probe.py
python scripts/trajectory_query_specificity_probe.py --seed 20260930
python scripts/trajectory_query_specificity_probe.py --seed 20261004
python scripts/trajectory_query_specificity_probe.py --seed 20261005
```

O diagnóstico lê apenas as testemunhas já retornadas, sujeitas aos limites de
candidatos da geração; não afirma enumerar toda a memória. Unicode e bytes UTF-8
têm comprimentos diferentes, portanto razões não são comparáveis entre modalidades
como uma confiança universal. Não há limiar instalado, regra semântica, LLM,
dados privados, alteração do OFF.IA ou resolução dos três gates nativos pendentes.

A próxima hipótese deve considerar a pista na sua região/ocorrência e a evidência
que distingue destinos, mantendo um controle positivo de transferência com
contexto novo. Aumentar apenas o tamanho exigido da pista não resolve o problema.
