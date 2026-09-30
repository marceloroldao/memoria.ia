# Contraste entre origem e destino temporal — 30/09/2026

O motor experimental ganhou a leitura `temporal_nodule_contrast`. Ela expõe
o que cada par temporal testemunha: o nódulo aparece no destino e já estava
na origem, ou aparece no destino sem estar naquela origem? Essa distinção
não muda pesos, candidatos ou seleção. Não classifica verdade.

## Contrato implementado

Para cada candidato retornado por `associated_nodules(..., channel="temporal")`,
a nova leitura mantém o recall original e retorna:

- símbolos do candidato e largura da pista primária;
- IDs das raízes de origem/destino e captura de cada par testemunha;
- todas as posições contíguas do candidato na origem e no destino;
- posições da consulta inteira na origem;
- contagens separadas de pares `introduced_in_pair` e `carried_in_pair`.

Os spans são intervalos de símbolos `[início, fim)`, com fim exclusivo. São
posições em codepoints no adaptador Unicode e em bytes no adaptador UTF-8.
São preservados ordem, símbolos repetidos e ocorrências sobrepostas.

`introduced_in_pair` significa apenas ausente naquela origem e presente naquele
destino; não significa conteúdo nunca visto, conhecimento novo ou resposta
correta. `carried_in_pair` significa presente em ambos. As contagens são dos
pares já exibidos e não acrescentam votos, peso ou capturas independentes.

A consulta aceita hierarquia, limite e `include_shorter`. Conserva a ambiguidade
e o truncamento do recall, não enumera alternativas ocultas pelo limite e não
tem um novo seletor. Leitura/reabertura dão igualdade completa. A expansão das
raízes é reutilizada somente dentro dessa consulta, sem novo estado persistido.

## Hipótese testada e rejeitada como veto

Os três lotes textuais mostram que todas as seleções únicas incorretas eram
fragmentos já presentes na origem. Testamos, exclusivamente no script avaliador,
a proposta de suspender uma seleção única em `NODULE_RECALL` se todos os seus
pares transportassem o nódulo e nenhum o introduzisse. O veto usa apenas o
contraste, sem rótulos de resposta, vocabulário, LLM ou porcentagem fixa.

| Medida | 20260930 | 20261004 | Novo lote 20261006 |
|---|---:|---:|---:|
| Seleções textuais incorretas antes | 6 | 10 | 8 |
| Incorretas restantes com veto hipotético | 0 | 0 | 0 |
| Incorretas em ausência antes | 2/24 | 6/24 | 4/24 |
| Respostas corretas antes / após veto | 8/28 / 8/28 | 8/28 / 8/28 | 8/28 / 8/28 |
| Controles válidos bloqueados pelo veto | 8/24 | 8/24 | 8/24 |

As quatro falhas adicionais por lote são o desafio de caixa; suspender essas
saídas não produz a resposta correta. Os cenários de contexto envolto continuam
ambíguos. O seed 20261006 foi executado após fixar a proposta; muda nomes/códigos
nas mesmas famílias de cenários, não testa conversação real.

## Por que o veto perde evocação válida

Os 24 controles positivos são três famílias de pares opacos: alvo ausente das
duas origens; alvo presente nas duas; e alvo presente só em uma. Cada família
usa quatro tamanhos de contexto novo e uma renomeação bijetiva dos símbolos.
São os mesmos 24 controles em cada relatório, não 72 independentes.

Na família transportada, cada origem contém `(7,8,9)` antes da pista `(1,2,3)`;
o evento seguinte contém `(7,8,9)` novamente. Duas capturas distintas registram
esses pares. A consulta inédita contém a pista, sem o alvo. O motor evoca
`(7,8,9)` como candidato único, sustentado por dois pares temporais. Isso é uma
transferência estrutural válida, mesmo sem novidade no destino.

O veto bloquearia todos os oito casos dessa família. Preserva os outros 16,
inclusive os mistos e os contextos longos. Portanto, novidade no par também
não serve, sozinha, para decidir se uma evocação deve ser escolhida. As rotas
transportadas continuam visíveis e elegíveis no motor.

## Validação

Seis testes novos verificam spans exatos com repetições e sobreposição, origem/destino mistos,
consulta inteira, replay idempotente, renomeação, isolamento entre hierarquias,
limites/competição, reabertura e seleção inalterada. Os 59 testes anteriores do
gerador passaram localmente. O probe verifica os mesmos contratos nos lotes.
Todos os campos originais dos 112 casos dos dois scorecards anteriores coincidem
com os relatórios publicados antes desta etapa.

```sh
python -m unittest discover -s tests -p test_temporal_nodule_contrast.py
python scripts/trajectory_transition_contrast_probe.py --seed 20260930
python scripts/trajectory_transition_contrast_probe.py --seed 20261004
python scripts/trajectory_transition_contrast_probe.py --seed 20261006
```

Resultados fictícios completos:
`benchmark-results/trajectory-transition-contrast-{development,heldout,reserved}.json`.
O processo retorna zero se os contratos de integridade passam; a qualidade
continua `UNRESOLVED` e o scorecard original continua `FAIL`. Não há dados
privados, mudança do OFF.IA ou resolução dos três controles pessoais nativos.

A próxima investigação pode comparar quais pistas distinguem os destinos e
quais acompanham vários destinos, usando estas mesmas testemunhas. A seleção
precisa preservar os controles positivos de evocação transportada e de contexto
novo, além de resolver ausência. O PR permanece rascunho.
