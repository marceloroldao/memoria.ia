# Replay estrutural de um export do OFF.IA

Em 28/09/2026, executamos o experimento Python com um export real de entradas
do OFF.IA, apenas para leitura. O script não publica textos pessoais, IDs da
origem nem o JSON original. Reproduzir com um arquivo local autorizado:

```sh
python scripts/trajectory_private_replay.py --export /caminho/privado/export.json
```

Sem `--export`, o script executa um exemplo sintético que também roda no CI.
O adaptador tokeniza aproximadamente como a versão nativa v1, dobra caixa e
atribui endereços inteiros opacos aos tokens. A equivalência exata com a
tokenização do APK não foi demonstrada. O replay preserva a ordem do export,
separa as capturas e alimenta o experimento somente com as entradas do usuário.
As cópias exatas normalizadas criam ocorrências sem voto de aprendizado.

| Medida agregada | Resultado |
| --- | ---: |
| Observações estruturais / capturas | 99 / 28 |
| Payloads normalizados distintos | 68 |
| Ocorrências duplicadas sem reforço | 31 |
| Payloads distintos que têm cópias | 9 |
| Endereços opacos de tokens | 140 |
| Consultas inéditas com prefixo e sufixo, uma por payload distinto | 68 |
| Modos antes da união: nódulo recorrente / raiz embutida / eco | 39 / 18 / 11 |
| Modos após a união: só nódulo / só raiz / ambos / eco | 9 / 18 / 30 / 11 |
| Ambos com destinos disjuntos / algum destino comum | 29 / 1 |
| Consultas com ambiguidade, antes / depois | 38 / 47 |
| Consultas com truncamento, antes / depois | 7 / 13 |
| Saídas únicas diferentes de eco, antes / depois | 19 / 10 |

O export contém **um** `reply_to` explícito resolúvel. Ele foi usado **só
depois** do aprendizado para conferir a evocação; não foi passado a `observe`
nem a `generate`. Sua pergunta de origem e o destino observado aparecem uma
vez cada. Em uma consulta inédita que contém a pergunta inteira, a execução
sem a nova evocação de raiz embutida deu `ECHO`; com ela, o destino observado
apareceu como candidato único (`EMBEDDED_TEMPORAL_RECALL`), sem ambiguidade
ou truncamento. Um prefixo inédito terminado na mesma pergunta também evoca
esse destino. O modo indica sucessão testemunhada na mesma captura, não
confirma que o destino seja uma resposta verdadeira.

Entre as nove consultas sobre payloads com cópias, três agora expõem as duas
famílias de rotas, uma evoca só nódulo recorrente e cinco dão eco. As cópias
não reforçaram pesos. As 19 saídas únicas anteriores caíram para 10 porque
alternativas antes encobertas agora impedem uma seleção estrutural única.
Isso não é uma medida de acerto: só um par possui avaliação explícita, e as
demais rotas podem ser irrelevantes. A raiz inteira aparece primeiro, porém
o método preserva os concorrentes e não soma os pesos de famílias diferentes.
A ordenação entre famílias ainda não foi calibrada; mais alternativas podem
ser distrações, e seis consultas adicionais sinalizam truncamento.

Isso prova uma capacidade estrutural pequena no host Python, com um caso real
rotulado pelo export. O aplicativo OFF.IA não usa esse gerador, o gate pessoal
nativo ainda tem três casos pendentes, e não há evidência de compreensão
factual, desempenho geral em diálogos ou processamento em segundo plano.
