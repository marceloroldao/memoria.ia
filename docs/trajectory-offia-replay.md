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
| Modos após união anterior: só nódulo / só raiz / ambos / eco | 9 / 18 / 30 / 11 |
| Modos com recuo a pistas menores: só nódulo / só raiz / ambos / eco | 14 / 17 / 31 / 6 |
| Modos após recuo de raiz embutida sem sucessor: só nódulo / só raiz / ambos / eco | 13 / 17 / 32 / 6 |
| Consultas com raiz menor ligada além da maior / destino adicional | 1 / 1 |
| Novos destinos na geração / novos casos ambíguos / novos truncamentos | 1 / 0 / 0 |
| Ambos com destinos disjuntos / algum destino comum | 31 / 1 |
| Consultas com ambiguidade, antes / agora | 47 / 53 |
| Consultas com truncamento, antes / agora | 13 / 15 |
| Saídas únicas diferentes de eco, antes / agora | 10 / 9 |
| Consultas com rotas recorrentes / ambíguas, antes / agora | 39 / 27 → 45 / 33 |
| Liderança estrutural sem empate / entre duas ou mais capturas, agora | 35 / 6 |
| Máximo de capturas independentes para uma rota | 5 |

Uma segunda passagem consulta **cada entrada original antes de aprendê-la**.
Ela usa a mesma tabela fixa de endereços opacos para tokens, mas cada consulta
vê somente as observações anteriores. Das 99 consultas online, antes do recuo
a pistas menores houve 53 ecos, 4 só continuações, 12 combinações de
continuação e evocação, 22 só evocações de nódulo e 8 combinações de
evocações. Agora são 40 ecos, 4 continuações, 12 combinações com continuação,
35 evocações de nódulo e 8 combinações de evocações. São 57 consultas
ambíguas, 9 truncadas e 2 saídas estruturais únicas diferentes de eco
(antes: 44, 8 e 2). O recuo substitui 13 ecos por evocações em entradas
reais, mas não existe rótulo de resposta para avaliá-las. Esses números
medem modos de operação, não acertos.

A medição `route_stability` encontra um primeiro colocado estrutural em 35
consultas, mas somente 6 deles são testemunhados em duas ou mais capturas.
Esse contraste impede interpretar automaticamente o maior peso como consenso.
Detalhes e controles estão na
[prova de estabilidade](trajectory-stability-proof.md).

O recuo da raiz embutida alterou uma das 68 consultas inéditas: ela agora
exibe candidatos tanto de nódulo recorrente quanto de raiz contida, em vez
de mostrar apenas o nódulo. As 99 consultas cronológicas e a avaliação do
único par explícito não mudaram. Esse novo candidato também pode ser uma
distração; o export não tem rótulos suficientes para medir acurácia.

Na comparação seguinte, manter também raízes menores **já ligadas** acrescentou
um destino em uma das 68 consultas inéditas. Nenhum modo, seleção, contagem de
ambiguidade ou truncamento mudou: a consulta já tinha alternativas. As 99
consultas cronológicas e o único par explícito mantiveram seus agregados.
Essa rota adicional tem testemunha de ordem na captura; o export não informa
se ela seria uma resposta adequada.

O export contém **um** `reply_to` explícito resolúvel. Ele foi usado **só
depois** do aprendizado para conferir a evocação; não foi passado a `observe`
nem a `generate`. Sua pergunta de origem e o destino observado aparecem uma
vez cada. Em uma consulta inédita que contém a pergunta inteira, a execução
sem a nova evocação de raiz embutida deu `ECHO`; com ela, o destino observado
apareceu como candidato único (`EMBEDDED_TEMPORAL_RECALL`), sem ambiguidade
ou truncamento. Um prefixo inédito terminado na mesma pergunta também evoca
esse destino. O modo indica sucessão testemunhada na mesma captura, não
confirma que o destino seja uma resposta verdadeira.

O único par vinculado está nas **duas últimas observações** do export. Na
passagem cronológica, consultar a pergunta envolta em um contexto novo logo
após a origem ainda dá `ECHO`; antes de aprender o destino também dá `ECHO`.
Somente depois de observar o destino ela produz o candidato único. Portanto,
esse par comprova recuperação de uma sequência já observada, **não** previsão
de uma resposta ainda não vista ou estabilidade após futuras entradas. A
[prova cronológica sintética](trajectory-episode-proof.md#prova-cronológica-de-evocação)
verifica o comportamento online com novos contextos e uma entrada interposta.

Entre as nove consultas sobre payloads com cópias, três expõem as duas
famílias de rotas, quatro evocam só nódulo recorrente e duas dão eco. As cópias
não reforçaram pesos. As 10 saídas únicas anteriores caíram para 9 porque
alternativas antes encobertas agora impedem uma seleção estrutural única.
Isso não é uma medida de acerto: só um par possui avaliação explícita, e as
demais rotas podem ser irrelevantes. A raiz inteira aparece primeiro, porém
o método preserva os concorrentes e não soma os pesos de famílias diferentes.
A ordenação entre famílias ainda não foi calibrada; mais alternativas podem
ser distrações, e duas consultas adicionais sinalizam truncamento.

Isso prova uma capacidade estrutural pequena no host Python, com um caso real
rotulado pelo export. O aplicativo OFF.IA não usa esse gerador, o gate pessoal
nativo ainda tem três casos pendentes, e não há evidência de compreensão
factual, desempenho geral em diálogos ou processamento em segundo plano.
